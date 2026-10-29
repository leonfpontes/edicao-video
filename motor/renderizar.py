"""`renderizar`: aplica o EDL ao vídeo (cortes, enquadramento, fundo, elementos, legendas, vinheta, CTA e áudio)."""
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .audio import gerar_sfx, loudnorm_2a, medir_loudnorm
from .bibliotecas import musica_do_edl
from .camera import Camera, Rosto, matriz_enquadre, transicao, zoom_em
from .config import FORMATOS, FPS
from .cor import aplicar_cor, lut_cor
from .elementos import Elementos
from .fundo import FundoMarca
from .graficos import blend, cobrir, pil2np, sombra
from .guarda import conferir_auditoria, conferir_edl
from .legendas import Legendas
from .marca import CFG, CORES, ErroDeMarca, ativar, logo_marca, padrao, registrar, tem_logo
from .segmentacao import Segmentador
from .util import bgr, sh, tem_audio
from .vinhetas import cartao_cta, quadro_intro


def cmd_renderizar(a):
    edl_p = Path(a.edl).resolve()
    pasta = edl_p.parent
    edl = json.load(open(edl_p))
    if not edl.get("marca"):
        raise ErroDeMarca("o edl.json não diz a marca (\"marca\"): rode `analisar --marca <marca>` de novo")
    ativar(edl["marca"])
    an = json.load(open(pasta / "analise.json"))
    conferir_edl(edl, an, pasta)
    print(f"Marca: {CFG['nome']}", flush=True)
    W, H = FORMATOS[edl.get("formato", "vertical")]
    src = edl["fonte"]
    mus_edl = dict(padrao(edl, "musica", {}) or {})
    if mus_edl.get("arquivo") and not Path(mus_edl["arquivo"]).expanduser().is_absolute() and (pasta / mus_edl["arquivo"]).exists():
        mus_edl["arquivo"] = str(pasta / mus_edl["arquivo"])
    trilha, faixa = musica_do_edl(mus_edl)

    # 1) segmentos quantizados na grade de quadros (áudio e vídeo cortam no mesmo ponto).
    #    A ordem do EDL é a ordem do vídeo; um segmento com "gancho": true repete um trecho no início.
    segs = list(edl["segmentos"])
    q = lambda t: round(t * FPS) / FPS
    for s in segs:
        s["qa"], s["qb"] = q(s["ini"]), q(s["fim"])
    segs = [s for s in segs if s["qb"] - s["qa"] >= 2 / FPS]
    for i in range(1, len(segs)):
        if not segs[i].get("gancho") and not segs[i - 1].get("gancho") and segs[i]["qa"] >= segs[i - 1]["qa"]:
            segs[i]["qa"] = max(segs[i]["qa"], segs[i - 1]["qb"])
    keep = [(s["qa"], s["qb"]) for s in segs]
    o = 0.0
    for s in segs:
        s["o"] = o
        o += s["qb"] - s["qa"]
    dur_fala = o
    cta = padrao(edl, "cta", {})
    if cta.get("ativo") and not cta.get("chamada"):
        sys.exit("CTA ligado sem 'chamada' (e 'url'): preencha o cta no edl.json ou desligue com \"ativo\": false")
    dur_cta = cta.get("duracao", 3.5) if cta.get("ativo") else 0
    intro = padrao(edl, "intro", {"ativo": True})
    dur_intro = round(intro.get("duracao", 2.2) * FPS) / FPS if intro.get("ativo", True) else 0.0
    total = dur_intro + dur_fala + dur_cta

    def map_out(t):
        normais = [s for s in segs if not s.get("gancho")]
        for s in normais:
            if s["qa"] <= t < s["qb"]:
                return s["o"] + t - s["qa"]
        depois = [s for s in normais if s["qa"] > t]
        return min(depois, key=lambda s: s["qa"])["o"] if depois else dur_fala

    # 2) componentes
    rosto = Rosto(an["rosto"])
    fundo = edl.get("fundo", {})
    tipo_fundo = fundo.get("tipo", "original")
    seg_ia = Segmentador() if tipo_fundo != "original" else None
    fundo_vivo = FundoMarca(W, H, fundo.get("variante", "marinho"))
    bg_img = cobrir(cv2.imread(str(registrar(fundo["imagem"]))), int(W * 1.2), int(H * 1.2)) if tipo_fundo == "imagem" else None
    cor = edl.get("cor", {})
    luts = lut_cor(cor)
    leg = Legendas(an["palavras"], edl.get("legendas", {}), W, H, keep) if edl.get("legendas", {}).get("ativo", True) else None
    els = Elementos(edl.get("elementos", []), W, H, map_out, an["palavras"])
    zooms = edl.get("zooms", [])
    marca = None
    barra = padrao(edl, "barra_progresso", True)
    if padrao(edl, "marca_dagua", True) and tem_logo():
        marca, _ = sombra(pil2np(logo_marca(CFG.get("marca_dagua_alt", 80))), 6, 0.5, (0, 3))
    TRN = int(FPS * edl.get("duracao_transicao", 0.3))
    interp = cv2.INTER_CUBIC

    tmp_v = pasta / "_video.mp4"
    final = pasta / (edl.get("saida") or "final.mp4")
    if a.so_audio:  # refaz só o áudio, reaproveitando o vídeo já renderizado
        shutil.copy(final, tmp_v)
    else:
        enc = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-c:v", "libx264", "-preset", "ultrafast" if a.rapido else "medium", "-crf", "18",
               "-pix_fmt", "yuv420p", str(tmp_v)]
        proc = subprocess.Popen(enc, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

        cap = cv2.VideoCapture(src)
        w0, h0 = int(cap.get(3)), int(cap.get(4))
        t0 = time.time()
        n_src = n_out = 0
        ultimo = None  # último quadro-base do trecho anterior (para as transições)
        ultimo_src = -10
        camera = Camera()

        def acabamento(out, t_out, t_src):
            els.desenhar(out, t_out)
            if leg:
                bi = leg.bloco_em(t_src)
                if bi is not None:
                    img = leg.render(bi, t_src)
                    blend(out, img, W / 2 - img.shape[1] / 2, H * leg.cfg.get("posicao_y", 0.68))
            if marca is not None and not els.ativo(t_out, "titulo"):
                blend(out, marca, W - marca.shape[1] - 30, H * CFG.get("marca_dagua_y", 0.115) if H > W else 40, 0.85)
            if barra:
                cv2.rectangle(out, (0, 0), (int(W * (t_out + dur_intro) / total), 6), bgr(CORES["champanhe"]), -1)
            els.desenhar(out, t_out, "pos")  # efeitos de quadro inteiro (grão, vinheta, glitch…) por cima de tudo

        # vinheta de abertura (igual em todos os vídeos)
        cache_intro = {}
        for k in range(int(round(dur_intro * FPS))):
            out = quadro_intro(W, H, k / FPS, fundo_vivo, cache_intro, dur_intro)
            proc.stdin.write(out.tobytes())
            n_out += 1
            ultimo = out
        clipes_ini = an.get("rosto", {}).get("clipes_ini", [0.0])
        clipe_de = lambda t: sum(1 for c in clipes_ini[1:] if t >= c)
        for si, s in enumerate(segs):
            a_idx, b_idx = int(round(s["qa"] * FPS)), int(round(s["qb"] * FPS))
            if si and clipe_de(s["qa"]) != clipe_de(segs[si - 1]["qa"]):
                camera = Camera()  # outra cena: o enquadramento começa no lugar certo, sem deslizar
            if a_idx < n_src or a_idx - n_src > FPS * 20:  # trecho anterior (gancho) ou salto longo: busca direta
                cap.set(cv2.CAP_PROP_POS_FRAMES, a_idx)
                n_src = a_idx
            while n_src < a_idx:
                cap.grab()
                n_src += 1
            base = None
            for fi in range(a_idx, b_idx):
                ok, f = cap.read()
                n_src += 1
                if not ok:
                    break
                t_src, t_out = fi / FPS, n_out / FPS - dur_intro
                zb, face = camera.passo(s.get("zoom", 1.0), rosto.em(t_src))
                respira = 1 + 0.02 * math.sin((t_out + dur_intro) * 0.3)  # aproximação lenta e contínua
                zf, tremor = zoom_em(t_src, zooms, s["qb"])
                z = zb * respira * zf
                M = matriz_enquadre(w0, h0, W, H, z, face, tremor)
                br = els.broll(t_out)
                if br is not None:
                    base = br
                else:
                    base = cv2.warpAffine(f, M, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE)
                    if seg_ia:
                        if fi != ultimo_src + 1:
                            seg_ia.reset() if seg_ia.rvm is not None else None
                        alfa, frente = seg_ia.recortar(f)
                        m = cv2.warpAffine(alfa, M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
                        base = cv2.warpAffine(frente, M, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE)
                        if tipo_fundo == "desfoque":
                            pq = cv2.resize(base, (W // 4, H // 4))
                            bg = cv2.resize(cv2.GaussianBlur(pq, (0, 0), 7), (W, H))
                        else:
                            # parallax: o fundo anda menos que a pessoa (sensação de profundidade)
                            par = fundo.get("parallax", True)
                            pz = 1 + (z - 1) * 0.3 if par else 1
                            dx = 0.5 + 0.025 * math.sin(t_out * 0.22) if par else 0.5
                            bg = fundo_vivo.quadro(t_out, pz, dx) if bg_img is None else cobrir(bg_img, W, H, pz, dx, 0.5)
                        if fundo.get("sombra", True) and tipo_fundo != "desfoque":
                            sm = cv2.GaussianBlur(np.roll(m[..., 0], (22, 12), (0, 1)), (0, 0), 18)[..., None]
                            bg = (bg.astype(np.float32) * (1 - 0.4 * sm)).astype(np.uint8)
                        base = (base.astype(np.float32) * m + bg.astype(np.float32) * (1 - m)).astype(np.uint8)
                    base = aplicar_cor(base, luts, cor)
                ultimo_src = fi
                out = base
                k = fi - a_idx
                tipo_tr = s.get("transicao") or ("zoom" if si == 0 and dur_intro else None)
                if tipo_tr and ultimo is not None and k < TRN:
                    out = transicao(ultimo, base, (k + 1) / (TRN + 1), tipo_tr, W, H)
                out = out.copy()
                acabamento(out, t_out, t_src)
                proc.stdin.write(out.tobytes())
                n_out += 1
            if base is not None:
                ultimo = base.copy()
            gasto = time.time() - t0
            resta = gasto / max(n_out, 1) * (total * FPS - n_out)
            print(f"  {n_out / FPS:5.1f}s / {total:.1f}s  ({n_out / max(gasto, 1e-3):.1f} quadros/s, faltam ~{resta / 60:.1f} min)", flush=True)
        cap.release()
        if seg_ia:
            seg_ia.fechar()
        cache = {}
        n_cta = int(round(dur_cta * FPS))
        for k in range(n_cta):
            out = cartao_cta(cta, W, H, k / FPS, fundo_vivo, cache)
            if k < TRN and ultimo is not None:
                out = transicao(ultimo, out, (k + 1) / (TRN + 1), edl.get("transicao_cta", "zoom"), W, H)
            if barra:
                cv2.rectangle(out, (0, 0), (int(W * (n_out / FPS) / total), 6), bgr(CORES["champanhe"]), -1)
            proc.stdin.write(out.tobytes())
            n_out += 1
        proc.stdin.close()
        proc.wait()

    # 3) áudio: mesmos cortes, limpeza de voz e loudness para Instagram (-16 LUFS)
    au = edl.get("audio", {})
    parts, labels = [], []
    for i, s in enumerate(segs):
        d = s["qb"] - s["qa"]
        parts.append(f"[0:a]atrim={s['qa']:.4f}:{s['qb']:.4f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.012,afade=t=out:st={max(d - 0.012, 0):.4f}:d=0.012[a{i}]")
        labels.append(f"[a{i}]")
    # Cadeia conservadora (voz limpa e cheia, sem "estourar"): filtros suaves, compressão leve,
    # loudnorm em DUAS passadas (medida + linear) e um limitador no fim, depois dos efeitos.
    cadeia = ["highpass=f=80", "lowpass=f=14000"]
    if au.get("denoise", True):
        cadeia.append(f"afftdn=nr={au.get('denoise_db', 10)}:nf=-42:tn=1")
    cadeia += ["equalizer=f=250:t=q:w=1.0:g=-2"]
    if au.get("presenca_db", 1.0):
        cadeia.append(f"equalizer=f=3200:t=q:w=1.2:g={au.get('presenca_db', 1.0)}")
    cadeia += ["deesser=i=0.4", "acompressor=threshold=-24dB:ratio=2.5:attack=15:release=200:makeup=1",
               "aresample=48000"]
    fc_voz = ";".join(parts) + f";{''.join(labels)}concat=n={len(segs)}:v=0:a=1,{','.join(cadeia)}[v]"
    voz_bruta, voz = pasta / "_voz_bruta.wav", pasta / "_voz.wav"
    if au.get("voz", True) and tem_audio(src):
        sh(["ffmpeg", "-y", "-i", src, "-filter_complex", fc_voz, "-map", "[v]", "-ac", "1", str(voz_bruta)])
    else:  # clipe mudo ou "voz": false (só a trilha): silêncio do tamanho dos cortes
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{dur_fala:.4f}", str(voz_bruta)])
    alvo_lufs, alvo_tp = au.get("loudness", -16), -2.0
    m = medir_loudnorm(voz_bruta, alvo_lufs, alvo_tp)
    if m:
        sh(["ffmpeg", "-y", "-i", str(voz_bruta), "-af", loudnorm_2a(m, alvo_lufs, alvo_tp) + ",aresample=48000",
            "-ac", "1", str(voz)])
    else:  # som original em silêncio: não há o que normalizar
        shutil.copy(voz_bruta, voz)
    ganho = au.get("original_db", 0)  # som ambiente mais baixo sob a trilha (ex.: -8)
    fc = (f"[0:a]adelay={int(dur_intro * 1000)}:all=1,apad=whole_dur={total:.4f}"
          + (f",volume={ganho}dB" if ganho else "") + "[voz]")
    ins = ["-i", str(voz)]
    ev_wh = [s["o"] - 0.12 for s in segs if s.get("transicao")] + ([dur_fala - 0.12] if dur_cta else [])
    ev_pop = els.eventos() if au.get("sfx_elementos", True) else []
    if not au.get("sfx_transicoes", True):
        ev_wh = []
    ev_wh = [t + dur_intro for t in ev_wh]
    ev_pop = [t + dur_intro for t in ev_pop]
    if dur_intro:  # assinatura sonora da vinheta: whoosh na abertura, pop no ponto, whoosh no mergulho
        ev_wh += [0.0, dur_intro - 0.45]
        ev_pop += [1.05]
    alvo, mix = "[voz]", []
    if ev_wh or ev_pop:
        wh, pop = gerar_sfx(pasta)
        ins += ["-i", str(wh), "-i", str(pop)]
        for idx, evs, nome in ((1, ev_wh, "w"), (2, ev_pop, "p")):
            if not evs:
                continue
            fc += f";[{idx}:a]asplit={len(evs)}" + "".join(f"[{nome}{i}]" for i in range(len(evs)))
            for i, t in enumerate(evs):
                ms = int(max(t, 0) * 1000)
                fc += f";[{nome}{i}]adelay={ms}|{ms}[{nome}d{i}]"
                mix.append(f"[{nome}d{i}]")
    rot_voz = "[voz]"
    if trilha:
        # trilha real: nivelada pelo loudness medido, em loop se for curta, com fade na entrada e no fim;
        # sob a voz, o ducking (sidechain) abaixa a música só enquanto ele fala
        mus = padrao(edl, "musica", {})
        fala = au.get("voz", True) and any(qa <= (w["ini"] + w["fim"]) / 2 < qb for w in an["palavras"] for qa, qb in keep)
        vol = mus.get("volume_db")
        vol = (-9 if fala else 0) if vol is None else vol
        mm = medir_loudnorm(trilha, alvo_lufs, alvo_tp)
        g = alvo_lufs + vol - float(mm["input_i"]) if mm else vol
        fi, fo = mus.get("fade_in", 0.8), mus.get("fade_out", 2.5)
        idx = len([x for x in ins if x == "-i"])
        ins += ["-stream_loop", "-1", "-ss", f"{mus.get('ini', 0)}", "-i", str(trilha)]
        fc += (f";[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.4f},asetpts=PTS-STARTPTS,"
               f"volume={g:.2f}dB,afade=t=in:d={fi},afade=t=out:st={max(total - fo, 0):.4f}:d={fo}[mus]")
        if mus.get("ducking", True) and fala:
            fc += (";[voz]asplit=2[vozm][vsc];[vsc]aformat=channel_layouts=stereo[sc];"
                   "[mus][sc]sidechaincompress=threshold=0.02:ratio=8:attack=30:release=450[musd]")
            rot_voz = "[vozm]"
            mix.append("[musd]")
        else:
            mix.append("[mus]")
    if mix:
        fc += f";{rot_voz}" + "".join(mix) + f"amix=inputs={len(mix) + 1}:normalize=0:duration=first[mix]"
        alvo = "[mix]"
    limitador = "alimiter=limit=0.79:attack=5:release=60:level=disabled"  # teto em -2 dBFS
    tmp_a = pasta / "_audio.wav"
    if trilha:
        # com trilha, o alvo de loudness vale para o conjunto (voz + música): mede a mistura e normaliza
        mix_wav = pasta / "_mix.wav"
        sh(["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", alvo, "-t", f"{total:.4f}", "-ar", "48000", "-ac", "2", str(mix_wav)])
        mm = medir_loudnorm(mix_wav, alvo_lufs, alvo_tp)
        af = (loudnorm_2a(mm, alvo_lufs, alvo_tp) + ",aresample=48000," if mm else "") + limitador
        sh(["ffmpeg", "-y", "-i", str(mix_wav), "-af", af, "-ar", "48000", "-ac", "2", str(tmp_a)])
        mix_wav.unlink()
    else:
        fc += f";{alvo}{limitador}[fim]"
        sh(["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", "[fim]", "-t", f"{total:.4f}", "-ar", "48000", "-ac", "2", str(tmp_a)])

    sh(["ffmpeg", "-y", "-i", str(tmp_v), "-i", str(tmp_a), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-metadata", f"comment=marca={CFG['id']}; editor=edicao-video {__version__}", "-metadata", f"artist={CFG['nome']}",
        "-shortest", "-movflags", "+faststart", str(final)])
    passo = max(total / 12, 0.1)
    sh(["ffmpeg", "-y", "-i", str(final), "-vf", f"fps=1/{passo:.3f},scale=270:-2,tile=6x2:padding=6:color=white",
        "-frames:v", "1", str(pasta / "previa.jpg")])
    for p in (tmp_v, tmp_a, voz_bruta, voz, pasta / "_whoosh.wav", pasta / "_pop.wav"):
        if p.exists():
            p.unlink()
    usados = conferir_auditoria()
    escrever_manifesto(pasta, final, edl, faixa, usados, total)
    print(f"Pronto: {final} ({total:.1f}s, {len(segs)} cortes, marca {CFG['id']}) e {pasta / 'previa.jpg'}")
    if faixa:
        print(f"Crédito da música (cole na legenda): {faixa['credito']}")


def escrever_manifesto(pasta, final, edl, faixa, usados, total):
    """manifesto.json: de que marca é o vídeo e tudo que entrou nele (para conferência e licenças).
    creditos.txt: a linha de crédito da música, quando houver."""
    from .config import RAIZ
    rel = lambda p: str(p.relative_to(RAIZ)) if RAIZ in p.parents else str(p)
    man = {"marca": CFG["id"], "nome_marca": CFG["nome"], "editor": __version__, "video": final.name,
           "duracao": round(total, 2), "arquivos": [rel(p) for p in usados],
           "musica": {k: faixa.get(k) for k in ("id", "titulo", "artista", "licenca", "credito", "pagina")} if faixa else None}
    json.dump(man, open(pasta / "manifesto.json", "w"), ensure_ascii=False, indent=1)
    cred = pasta / "creditos.txt"
    if faixa:
        cred.write_text(faixa["credito"] + "\n")
    elif cred.exists():
        cred.unlink()

