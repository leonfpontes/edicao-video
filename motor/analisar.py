"""`analisar`: normaliza o vídeo, transcreve (Whisper, tempo por palavra), rastreia o rosto e escreve o rascunho do EDL."""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .cena import DICA_TOUR, aplicar_cena, dirigir_cena, ler_cena, resumo_cena, tour_pela_casa
from .config import FPS, MODELOS
from .cor import igualar_clipes
from .diretor import aplicar as aplicar_diretor
from .diretor import dirigir, montar_gancho, resumo_diretor
from .estilos import PRESETS
from .marca import CFG, ativar
from .pausas import aparar_palavras, volume_db
from .tour import dirigir_tour
from .util import probe, sh, tem_audio


def normalizar(src, dst, estabilizar=False):
    """30 fps constante, SDR bt709, lado maior <= 1920, áudio 48 kHz começando em zero."""
    v, _ = probe(src)
    vf = []
    if v.get("color_transfer") in ("arib-std-b67", "smpte2084"):  # HDR do iPhone
        vf.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                  "zscale=t=bt709:m=bt709:r=tv")
    if estabilizar:  # vídeo de mão (dia a dia): tira o tremor em duas passadas (vid.stab). O zoom adaptativo
        # (optzoom=2) aproxima só o necessário em cada trecho para nenhuma borda aparecer; nunca estica a borda.
        trf = Path(dst).with_suffix(".trf")
        sh(["ffmpeg", "-y", "-i", str(src), "-vf", ",".join(vf + [f"vidstabdetect=shakiness=6:accuracy=12:result={trf}"]),
            "-f", "null", "-"])
        vf.append(f"vidstabtransform=input={trf}:smoothing=18:optzoom=2:zoomspeed=0.2:crop=black:interpol=bicubic")
    vf += [f"fps={FPS}", "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))'", "format=yuv420p"]
    sh(["ffmpeg", "-y", "-fflags", "+genpts", "-i", str(src), "-vf", ",".join(vf),
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-g", "30",
        "-af", "aresample=48000:async=1", "-ac", "1", "-c:a", "pcm_s16le",
        "-avoid_negative_ts", "make_zero", str(dst)])



def conferir_estabilizado(cfr, passo=15):
    """Depois de estabilizar, nenhum quadro pode ter faixa sem imagem na borda (a estabilização preenche com preto)."""
    from .qa import borda_ruim
    cap, i, ruins = cv2.VideoCapture(str(cfr)), 0, []
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % passo == 0:
            _, f = cap.retrieve()
            if borda_ruim(f):
                ruins.append(round(i / FPS, 1))
        i += 1
    if ruins:
        print(f"  AVISO: borda sem imagem depois de estabilizar em {len(ruins)} ponto(s) (ex.: {ruins[:5]} s). "
              "O render acusa \"borda esticada\"; não entregue assim.", flush=True)
    return ruins

def juntar_clipes(srcs, pasta, dst, estabilizar=False):
    """Vários vídeos do dia a dia em sequência: normaliza cada um e emenda num único arquivo no tamanho
    do primeiro (cobrindo, sem tarja). Devolve os clipes com seus tempos no arquivo emendado."""
    partes, clipes, t = [], [], 0.0
    for i, s in enumerate(srcs):
        c = pasta / f"clipe_{i:02d}.mov"
        normalizar(s, c, estabilizar)
        _, d = probe(c)
        partes.append((c, d))
        clipes.append({"arquivo": s.name, "ini": round(t, 3), "fim": round(t + d, 3)})
        t += d
    v0, _ = probe(partes[0][0])
    W, H = v0["width"], v0["height"]
    ins, fc = [], []
    for i, (c, d) in enumerate(partes):
        ins += ["-i", str(c)]
        fc.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                  f"fps={FPS},format=yuv420p,trim=0:{d:.4f},setpts=PTS-STARTPTS[v{i}]")
        if tem_audio(c):
            fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,apad,atrim=0:{d:.4f}[a{i}]")
        else:  # clipe mudo: silêncio do mesmo tamanho para a emenda não desalinhar
            fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{d:.4f}[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(partes))) + f"concat=n={len(partes)}:v=1:a=1[v][a]")
    sh(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-g", "30", "-c:a", "pcm_s16le", str(dst)])
    for c, _ in partes:
        c.unlink()
    return clipes


def transcrever(video, modelo):
    from faster_whisper import WhisperModel
    # decodifica com o ffmpeg (evita depender da versão do PyAV)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(audio, language="pt", word_timestamps=True, vad_filter=False,
                           initial_prompt=CFG.get("vocabulario", ""), condition_on_previous_text=False)
    palavras = []
    for s in segs:
        for w in s.words:
            txt = w.word.strip()
            if txt:
                palavras.append({"t": txt, "ini": round(w.start, 3), "fim": round(w.end, 3), "p": round(w.probability, 2)})
    return palavras


def rastrear_rosto(video):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(MODELOS / "blaze_face_short_range.tflite")),
        min_detection_confidence=0.5))
    cap = cv2.VideoCapture(str(video))
    W, H = int(cap.get(3)), int(cap.get(4))
    amostras, n = [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if n % (FPS // 2) == 0:
            _, f = cap.retrieve()
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            r = det.detect(img).detections
            if r:
                b = max(r, key=lambda d: d.bounding_box.width).bounding_box
                amostras.append([round(n / FPS, 2), round((b.origin_x + b.width / 2) / W, 4),
                                 round((b.origin_y + b.height / 2) / H, 4), round(b.height / H, 4)])
        n += 1
    cap.release()
    det.close()
    if not amostras:
        amostras = [[0, 0.5, 0.35, 0.2]]
    return {"w": W, "h": H, "quadros": n, "amostras": amostras}


def rosto_por_clipe(rosto, clipes):
    """Cada clipe começa e termina com o próprio rosto (ou centralizado, se não houver rosto), para o
    enquadramento de um clipe não 'escorregar' para a posição do clipe vizinho."""
    am = rosto["amostras"]
    novas = []
    for c in clipes:
        dentro = [x for x in am if c["ini"] <= x[0] < c["fim"]]
        if not dentro:
            dentro = [[c["ini"], 0.5, 0.45, 0.2]]
        novas += [[c["ini"]] + dentro[0][1:]] + dentro + [[round(c["fim"] - 0.01, 2)] + dentro[-1][1:]]
    rosto["amostras"] = sorted(novas)
    rosto["clipes_ini"] = [c["ini"] for c in clipes]
    return rosto


def rascunho_edl(fonte_cfr, palavras, silencio_min=0.35, respiro=0.08, dur=None, clipes=None):
    """Um segmento por trecho de fala contínua; pausas >= silencio_min são cortadas.
    Clipe sem fala (vídeo do dia a dia, só imagem) entra inteiro, como um segmento."""
    if clipes is None:
        clipes = [{"ini": 0.0, "fim": dur or (palavras[-1]["fim"] if palavras else 0.0)}]
    out = []
    for c in clipes:
        ws = [w for w in palavras if c["ini"] <= (w["ini"] + w["fim"]) / 2 < c["fim"]]
        if not ws:
            out.append({"id": len(out), "ini": round(c["ini"], 3), "fim": round(c["fim"], 3),
                        "zoom": 1.0, "transicao": None, "texto": "(sem fala)"})
            continue
        # silêncio no meio de uma palavra (motor/pausas.py): vira duas meias palavras para o corte pular a pausa
        ws = [m for w in ws for m in ([dict(w, fim=w["pausa"][0]), dict(w, t="", ini=w["pausa"][1])] if w.get("pausa") else [w])]
        segs, cur = [], None
        for i, w in enumerate(ws):
            if cur and w["ini"] - ws[i - 1]["fim"] < silencio_min:
                cur["fim"] = w["fim"]
                cur["texto"] += (" " + w["t"]) if w["t"] else ""
            else:
                if cur:
                    segs.append(cur)
                cur = {"ini": w["ini"], "fim": w["fim"], "texto": w["t"] or "…"}
        segs.append(cur)
        for s in segs:
            ini = max(c["ini"], s["ini"] - respiro)
            fim = min(s["fim"] + respiro + 0.04, c["fim"])
            if out and ini < out[-1]["fim"]:
                ini = out[-1]["fim"]
            out.append({"id": len(out), "ini": round(ini, 3), "fim": round(fim, 3),
                        "zoom": 1.0, "transicao": None, "texto": s["texto"]})
    edl = {
        "marca": CFG["id"],
        "fonte": str(fonte_cfr),
        "formato": "vertical",
        "segmentos": out,
        "zooms": [],
        "fundo": {"tipo": "original", "imagem": None, "parallax": True, "sombra": True},
        "cor": {"contraste": 1.05, "saturacao": 1.06, "calor": 0.03, "nitidez": 0.25},
        "audio": {"denoise": True, "denoise_db": 10, "presenca_db": 1.0, "loudness": -16, "sfx_transicoes": True},
        "legendas": {"ativo": bool(palavras), "palavras_por_bloco": 3, "posicao_y": 0.68, "maiusculas": False,
                     "enfase": [], "correcoes": {}},
        "elementos": [],
        "marca_dagua": True,
        "barra_progresso": True,
        "cta": dict({"ativo": True, "duracao": 3.5}, **CFG.get("cta", {})),
    }
    # padrões da marca (ex.: @leopontesrp sem vinheta, sem CTA, com trilha)
    for k, v in CFG.get("padroes_edl", {}).items():
        edl[k] = dict(edl[k], **v) if isinstance(v, dict) and isinstance(edl.get(k), dict) else v
    return edl


def cmd_analisar(a):
    ativar(a.marca)
    print(f"Marca: {CFG['nome']}", flush=True)
    srcs = [Path(v).resolve() for v in a.video]
    src = srcs[0]
    pasta = Path(a.pasta or src.parent / f"{src.stem}_edicao").resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    cfr = pasta / "fonte_cfr.mov"
    # a normalização é refeita se os vídeos, a ordem ou a estabilização mudarem
    receita = {"arquivos": [str(s) for s in srcs], "estabilizar": a.estabilizar}
    rp = pasta / "clipes.json"
    antiga = json.load(open(rp)) if rp.exists() else {"arquivos": [str(src)], "estabilizar": False}
    clipes = antiga.get("clipes")
    if (not cfr.exists() or cfr.stat().st_mtime < max(s.stat().st_mtime for s in srcs)
            or {k: antiga.get(k) for k in receita} != receita):
        print("1/3 normalizando…", flush=True)
        for c in pasta.glob("palavras_*.json"):
            c.unlink()
        if len(srcs) == 1:
            normalizar(src, cfr, a.estabilizar)
            clipes = None
        else:
            clipes = juntar_clipes(srcs, pasta, cfr, a.estabilizar)
        json.dump(dict(receita, clipes=clipes), open(rp, "w"), ensure_ascii=False, indent=1)
        if a.estabilizar:
            conferir_estabilizado(cfr)
    _, dur = probe(cfr)
    clipes = clipes or [{"arquivo": src.name, "ini": 0.0, "fim": round(dur, 3)}]
    cache = pasta / f"palavras_{Path(a.modelo).name}.json"  # --modelo pode ser uma pasta local com o modelo
    if a.sem_fala:  # vídeo só de imagem (ou fala que não deve virar legenda): pula o Whisper
        palavras = []
    elif cache.exists():
        palavras = json.load(open(cache))
    else:
        print(f"2/3 transcrevendo com Whisper ({a.modelo})…", flush=True)
        palavras = transcrever(cfr, a.modelo)
        json.dump(palavras, open(cache, "w"), ensure_ascii=False)
    aparadas = 0
    if palavras and not getattr(a, "sem_aparar", False):  # o Whisper estica a palavra sobre a pausa: o áudio acerta
        palavras, aparadas = aparar_palavras(palavras, volume_db(cfr))
    print("3/3 rastreando rosto…", flush=True)
    rosto = rastrear_rosto(cfr)
    if len(clipes) > 1:
        rosto = rosto_por_clipe(rosto, clipes)
    cor_clipes = igualar_clipes(cfr, clipes) if len(clipes) > 1 else None
    json.dump({"marca": CFG["id"], "editor": __version__, "duracao": dur, "palavras": palavras, "rosto": rosto, "clipes": clipes,
               "cor_clipes": cor_clipes}, open(pasta / "analise.json", "w"), ensure_ascii=False)
    estilo = getattr(a, "estilo", None)
    silencio = PRESETS[estilo]["edl"].get("corte_pausa_max", 0.35) if estilo else 0.35
    edl = rascunho_edl(cfr, palavras, silencio_min=silencio, dur=dur, clipes=clipes)
    if estilo:
        edl["estilo"] = estilo
        for k in ("legendas", "audio"):
            if k in PRESETS[estilo]["edl"]:
                edl[k] = dict(edl[k], **PRESETS[estilo]["edl"][k])
    plano = None
    if palavras and not getattr(a, "sem_diretor", False):
        print("Diretor: vícios, tomadas repetidas, ênfases, zooms, gancho e elementos…", flush=True)
        plano = dirigir(palavras, cfr, estilo)
        edl = aplicar_diretor(edl, plano, palavras, rosto.get("clipes_ini", [0.0]) if isinstance(rosto, dict) else [0.0],
                                 alternar=CFG.get("diretor", {}).get("alternar_zoom", True))
        if CFG.get("diretor", {}).get("gancho_automatico", True):
            edl = montar_gancho(edl, plano, palavras)
        if not getattr(a, "sem_cena", False):
            print("Cena: gestos, cabeça e câmera…", flush=True)
            cena = ler_cena(cfr)
            json.dump(cena, open(pasta / "cena.json", "w"), ensure_ascii=False)
            tour, linhas_tour = tour_pela_casa(cena, dur), []
            if tour:  # câmera andando pelo ambiente: capítulos por cômodo, rótulos presos ao que ele aponta, luz igualada
                edl.setdefault("cor", {})["igualar_luz"] = True
                edl, linhas_tour = dirigir_tour(cena, palavras, edl)
            pc = dirigir_cena(cena, palavras, edl["segmentos"], calmo=CFG.get("diretor", {}).get("calmo", False))
            edl = aplicar_cena(edl, pc, palavras)
            plano["cena"] = resumo_cena(cena)
            if tour:
                plano["cena"] += "\n" + DICA_TOUR.format(p=round(tour * 100)) + ("\n" + "\n".join(linhas_tour) if linhas_tour else "")
        json.dump(plano, open(pasta / "diretor.json", "w"), ensure_ascii=False, indent=1)
    json.dump(edl, open(pasta / "edl.json", "w"), ensure_ascii=False, indent=1)
    with open(pasta / "transcricao.txt", "w") as f:
        f.write(f"# {', '.join(s.name for s in srcs)} — {dur:.1f}s, {len(palavras)} palavras. "
                "[id] ini–fim  texto  (? = palavra com baixa confiança)\n")
        if len(clipes) > 1:
            f.write("# Clipes: " + " · ".join(f"{c['arquivo']} {c['ini']:.2f}–{c['fim']:.2f}" for c in clipes) + "\n")
        if not palavras:
            f.write("# Sem fala: legendas desligadas; cada clipe entra inteiro. Corte pelo ritmo da imagem e da música.\n")
        for s in edl["segmentos"]:
            f.write(f"[{s['id']:03d}] {s['ini']:7.2f}–{s['fim']:7.2f}  {s['texto']}\n")
        if plano:
            f.write("\n" + resumo_diretor(plano) + "\n")
        baixas = [w for w in palavras if w["p"] < 0.5]
        if baixas:
            f.write("\n# Baixa confiança: " + ", ".join(f"{w['t']}@{w['ini']:.1f}" for w in baixas) + "\n")
    if aparadas:
        print(f"Pausas: {aparadas} palavras esticadas sobre silêncio foram acertadas pelo áudio (--sem-aparar desliga)")
    if plano:
        print(resumo_diretor(plano))
    print(f"Pronto: {pasta}/transcricao.txt e edl.json ({len(edl['segmentos'])} segmentos)")

