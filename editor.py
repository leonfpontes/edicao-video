#!/usr/bin/env python3
"""
Editor de vídeo (@pontes_brain, GiraHub, …) — pipeline local e gratuito.

  python editor.py analisar  VIDEO [--marca pontes_brain|girahub] [--pasta trabalho/] [--modelo small]
  python editor.py renderizar trabalho/edl.json [--rapido]

`analisar` normaliza o vídeo (30 fps, SDR), transcreve com Whisper (tempo por palavra),
rastreia o rosto e escreve trabalho/transcricao.txt + trabalho/edl.json (rascunho).
O agente edita o edl.json (cortes, zooms, fundo, elementos, transições, CTA) e chama
`renderizar`, que gera trabalho/final.mp4 e trabalho/previa.jpg (folha de contato).

Todos os tempos do edl.json estão na linha do tempo do vídeo ORIGINAL (a da transcrição).
A identidade visual (cores, fontes, logo, vinheta, fundo, CTA) vem de marcas/<marca>.json; o edl.json
guarda a marca em "marca". As chaves de cor são papéis: "marinho" = cor escura de fundo/caixa,
"champanhe" = cor de destaque, "papel" = cor clara.
"""
import argparse, json, math, os, subprocess, sys, shutil
from pathlib import Path

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
ASSETS = AQUI / "assets"
MODELOS = AQUI / "modelos"
FPS = 30

MARCA = {
    "marinho": (20, 33, 61),        # #14213D
    "marinho_2": (34, 48, 90),      # #22305A
    "champanhe": (212, 185, 140),   # #D4B98C
    "bronze": (148, 115, 61),       # #94733D
    "papel": (242, 238, 230),       # #F2EEE6
    "papel_2": (255, 253, 248),     # #FFFDF8
    "nevoa": (169, 178, 196),       # #A9B2C4
}
FORMATOS = {"vertical": (1080, 1920), "feed": (1080, 1350), "horizontal": (1920, 1080)}
VOCABULARIO = ("Leonardo Pontes, pontes_brain, mentoria de produto, PDCA, Plan, Do, Check, Act, "
               "gate, Gate 1, intake, business case, delivery, benefits, discovery, roadmap, OKR, "
               "product manager, stakeholder, backlog, MVP, leopontes.com.br")
MARCAS = AQUI / "marcas"
CFG = {"id": "pontes_brain"}  # marca ativa (marcas/<id>.json)
FONTES = {}


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def carregar_marca(nome):
    global VOCABULARIO
    p = MARCAS / f"{nome}.json"
    if not p.exists():
        sys.exit(f"Marca desconhecida: {nome} (opções: {', '.join(x.stem for x in MARCAS.glob('*.json'))})")
    cfg = json.load(open(p))
    CFG.clear()
    CFG.update(cfg)
    MARCA.update({k: hex2rgb(v) for k, v in cfg.get("cores", {}).items()})
    FONTES.clear()
    FONTES.update(cfg.get("fontes", {}))
    VOCABULARIO = cfg.get("vocabulario", VOCABULARIO)


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"Falhou: {' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r.stdout


def fonte(peso, tam, papel="texto"):
    """papel 'titulo' (cartões, nome da vinheta) ou 'texto' (legendas, rótulos), conforme a marca."""
    arq = FONTES.get(papel, {}).get(peso) or f"Roboto-{peso}.ttf"
    return ImageFont.truetype(str(ASSETS / "fontes" / arq), tam)


def bgr(rgb):
    return (rgb[2], rgb[1], rgb[0])


# ───────────────────────────── analisar ─────────────────────────────

def probe(path):
    out = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    return v, float(out["format"]["duration"])


def normalizar(src, dst):
    """30 fps constante, SDR bt709, lado maior <= 1920, áudio 48 kHz começando em zero."""
    v, _ = probe(src)
    vf = []
    if v.get("color_transfer") in ("arib-std-b67", "smpte2084"):  # HDR do iPhone
        vf.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                  "zscale=t=bt709:m=bt709:r=tv")
    vf += [f"fps={FPS}", "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))'", "format=yuv420p"]
    sh(["ffmpeg", "-y", "-fflags", "+genpts", "-i", str(src), "-vf", ",".join(vf),
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-g", "30",
        "-af", "aresample=48000:async=1", "-ac", "1", "-c:a", "pcm_s16le",
        "-avoid_negative_ts", "make_zero", str(dst)])


def transcrever(video, modelo):
    from faster_whisper import WhisperModel
    # decodifica com o ffmpeg (evita depender da versão do PyAV)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(audio, language="pt", word_timestamps=True, vad_filter=False,
                           initial_prompt=VOCABULARIO, condition_on_previous_text=False)
    palavras = []
    for s in segs:
        for w in s.words:
            txt = w.word.strip()
            if txt:
                palavras.append({"t": txt, "ini": round(w.start, 3), "fim": round(w.end, 3), "p": round(w.probability, 2)})
    return palavras


def rastrear_rosto(video):
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
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


def rascunho_edl(fonte_cfr, palavras, silencio_min=0.35, respiro=0.08, dur=None):
    """Um segmento por trecho de fala contínua; pausas >= silencio_min são cortadas."""
    segs, cur = [], None
    for i, w in enumerate(palavras):
        if cur and w["ini"] - palavras[i - 1]["fim"] < silencio_min:
            cur["fim"] = w["fim"]
            cur["texto"] += " " + w["t"]
        else:
            if cur:
                segs.append(cur)
            cur = {"ini": w["ini"], "fim": w["fim"], "texto": w["t"]}
    if cur:
        segs.append(cur)
    out = []
    for k, s in enumerate(segs):
        ini = max(0.0, s["ini"] - respiro)
        fim = s["fim"] + respiro + 0.04
        if dur:
            fim = min(fim, dur)
        if out and ini < out[-1]["fim"]:
            ini = out[-1]["fim"]
        out.append({"id": k, "ini": round(ini, 3), "fim": round(fim, 3),
                    "zoom": 1.0, "transicao": None, "texto": s["texto"]})
    return {
        "marca": CFG["id"],
        "fonte": str(fonte_cfr),
        "formato": "vertical",
        "segmentos": out,
        "zooms": [],
        "fundo": {"tipo": "original", "imagem": None, "parallax": True, "sombra": True},
        "cor": {"contraste": 1.05, "saturacao": 1.06, "calor": 0.03, "nitidez": 0.25},
        "audio": {"denoise": True, "denoise_db": 10, "presenca_db": 1.0, "loudness": -16, "sfx_transicoes": True},
        "legendas": {"ativo": True, "palavras_por_bloco": 3, "posicao_y": 0.68, "maiusculas": False,
                     "enfase": [], "correcoes": {}},
        "elementos": [],
        "marca_dagua": True,
        "barra_progresso": True,
        "cta": dict({"ativo": True, "duracao": 3.5}, **CFG.get("cta", {})),
    }


def cmd_analisar(a):
    carregar_marca(a.marca)
    src = Path(a.video).resolve()
    pasta = Path(a.pasta or src.parent / f"{src.stem}_edicao").resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    cfr = pasta / "fonte_cfr.mov"
    if not cfr.exists() or cfr.stat().st_mtime < src.stat().st_mtime:
        print("1/3 normalizando…", flush=True)
        normalizar(src, cfr)
    _, dur = probe(cfr)
    cache = pasta / f"palavras_{a.modelo}.json"
    if cache.exists():
        palavras = json.load(open(cache))
    else:
        print(f"2/3 transcrevendo com Whisper ({a.modelo})…", flush=True)
        palavras = transcrever(cfr, a.modelo)
        json.dump(palavras, open(cache, "w"), ensure_ascii=False)
    print("3/3 rastreando rosto…", flush=True)
    rosto = rastrear_rosto(cfr)
    json.dump({"duracao": dur, "palavras": palavras, "rosto": rosto}, open(pasta / "analise.json", "w"), ensure_ascii=False)
    edl = rascunho_edl(cfr, palavras, dur=dur)
    json.dump(edl, open(pasta / "edl.json", "w"), ensure_ascii=False, indent=1)
    with open(pasta / "transcricao.txt", "w") as f:
        f.write(f"# {src.name} — {dur:.1f}s, {len(palavras)} palavras. [id] ini–fim  texto  (? = palavra com baixa confiança)\n")
        for s in edl["segmentos"]:
            f.write(f"[{s['id']:03d}] {s['ini']:7.2f}–{s['fim']:7.2f}  {s['texto']}\n")
        baixas = [w for w in palavras if w["p"] < 0.5]
        if baixas:
            f.write("\n# Baixa confiança: " + ", ".join(f"{w['t']}@{w['ini']:.1f}" for w in baixas) + "\n")
    print(f"Pronto: {pasta}/transcricao.txt e edl.json ({len(edl['segmentos'])} segmentos)")




# ───────────────────────────── movimento ─────────────────────────────

def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):  # cúbica: rápida no começo, pousa macio
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp01(x)
    return x ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.70158):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def mola(x, amort=7.0, freq=11.0):
    """Mola amortecida: passa um pouco do alvo e assenta (0→1)."""
    if x <= 0:
        return 0.0
    return 1 - math.exp(-amort * x) * math.cos(freq * x)


def lerp(a, b, p):
    return a + (b - a) * p


# ───────────────────────────── gráficos ─────────────────────────────

def pil2np(im):
    return np.array(im.convert("RGBA"))


def blend(frame, rgba, x, y, alpha=1.0):
    """Cola um RGBA (numpy, ordem RGB) em frame BGR na posição (x,y), recortando nas bordas."""
    h, w = rgba.shape[:2]
    H, W = frame.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1 or alpha <= 0.003:
        return
    sub = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = sub[..., 3:4].astype(np.float32) * (alpha / 255.0)
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (roi * (1 - a) + sub[..., 2::-1].astype(np.float32) * a).astype(np.uint8)


def alpha_over(dst, src):
    sa = src[..., 3:4].astype(np.float32) / 255
    da = dst[..., 3:4].astype(np.float32) / 255
    oa = sa + da * (1 - sa)
    rgb = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    return np.concatenate([rgb, oa * 255], -1).clip(0, 255).astype(np.uint8)


def sombra(rgba, raio=18, opac=0.45, desloc=(0, 14)):
    a = rgba[..., 3].astype(np.float32) * opac
    pad = raio * 2 + max(map(abs, desloc))
    h, w = a.shape
    big = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    big[pad + desloc[1]:pad + desloc[1] + h, pad + desloc[0]:pad + desloc[0] + w] = a
    big = cv2.GaussianBlur(big, (0, 0), raio)
    out = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
    out[..., :3] = 8
    out[..., 3] = big.clip(0, 255).astype(np.uint8)
    out[pad:pad + h, pad:pad + w] = alpha_over(out[pad:pad + h, pad:pad + w], rgba)
    return out, pad


def transformar(rgba, escala=1.0, graus=0.0):
    """Escala e gira um sprite em torno do centro, mantendo o centro no mesmo lugar."""
    if abs(escala - 1) < 0.004 and abs(graus) < 0.05:
        return rgba
    h, w = rgba.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), graus, escala)
    return cv2.warpAffine(rgba, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))


def girar3d(rgba, graus):
    """Gira o cartão no eixo Y com perspectiva."""
    if abs(graus) < 0.3:
        return rgba
    h, w = rgba.shape[:2]
    th = math.radians(graus)
    f = w * 1.8
    pts = []
    for (x, y) in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        X, Z = x * math.cos(th), x * math.sin(th)
        s = f / (f + Z)
        pts.append([w / 2 + X * s, h / 2 + y * s])
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(pts))
    return cv2.warpPerspective(rgba, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))


def quebrar(texto, f, larg_max):
    linhas, atual = [], ""
    for p in texto.split():
        t = (atual + " " + p).strip()
        if f.getlength(t) <= larg_max or not atual:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    linhas.append(atual)
    return linhas


class Cartao:
    """Caixa de texto cinética.
    estilo 'titulo': caixa marinho abre da esquerda (wipe), barra champanhe cresce, palavras sobem
    uma a uma por trás de uma máscara e o cartão termina um leve giro 3D.
    estilo 'destaque': caixa champanhe cresce do centro com mola, texto marinho entra em cascata."""

    def __init__(self, texto, larg_max, estilo="titulo", tam=None):
        self.estilo = estilo
        tit = estilo == "titulo"
        self.f = fonte("Black" if tit else "Bold", tam or (80 if tit else 58), "titulo" if tit else "texto")
        self.cor_caixa = MARCA["marinho"] if tit else MARCA["champanhe"]
        self.cor_txt = (255, 255, 255) if tit else MARCA["marinho"]
        self.padx, self.pady = (46, 30) if tit else (34, 20)
        self.barra = 16 if tit else 0
        linhas = quebrar(texto, self.f, larg_max - 2 * self.padx - self.barra)
        self.lh = int(self.f.size * 1.2)
        esp = self.f.getlength(" ")
        self.palavras = []  # (sprite, x, y)
        for li, l in enumerate(linhas):
            x = self.padx + self.barra
            for p in l.split():
                wpx = int(self.f.getlength(p)) + 4
                im = Image.new("RGBA", (wpx, self.lh + 10), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((0, 0), p, font=self.f, fill=self.cor_txt)
                self.palavras.append((im, x, self.pady + li * self.lh))
                x += wpx - 4 + esp
        self.w = int(max(x0 + im.width for im, x0, _ in self.palavras) + self.padx)
        self.h = self.pady * 2 + self.lh * len(linhas)
        self.dur_in = 0.45 + 0.07 * len(self.palavras)

    def render(self, dt, rest):
        """dt: segundos desde a entrada; rest: segundos até a saída."""
        W, H = self.w, self.h
        sai = ease_in(1 - rest / 0.3) if rest < 0.3 else 0.0
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if self.estilo == "titulo":
            pb = ease_out(dt / 0.4)
            x0, x1 = 0, W * pb
            if sai:
                x0 = W * ease_in_out(sai)
        else:
            pb = clamp01(mola(dt / 0.55, 6, 10))
            meia = W / 2 * pb * (1 - ease_in(sai))
            x0, x1 = W / 2 - meia, W / 2 + meia
        if x1 - x0 > 24:
            d.rounded_rectangle([x0, 0, x1 - 1, H - 1], 12 if self.estilo == "titulo" else 10, fill=self.cor_caixa + (245,))
        if self.barra:
            hb = (H - 2 * self.pady + 8) * ease_out((dt - 0.1) / 0.35) * (1 - sai)
            cy = H / 2
            if hb > 2 and x1 > self.padx:
                d.rounded_rectangle([self.padx - 2, cy - hb / 2, self.padx + 6, cy + hb / 2], 3, fill=MARCA["champanhe"] + (255,))
        texto = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i, (sp, x, y) in enumerate(self.palavras):
            atraso = 0.22 if self.estilo == "titulo" else 0.1
            p = ease_out_back((dt - atraso - 0.07 * i) / 0.38, 1.3)
            if p <= 0:
                continue
            dy = int((1 - p) * self.lh * 0.9 - ease_in(sai) * self.lh * 0.9)
            # cada palavra só aparece dentro da faixa da própria linha (efeito de "subir por trás")
            topo, base = max(0, -dy), min(sp.height, self.lh + 4 - dy)
            if base > topo:
                texto.alpha_composite(sp.crop((0, topo, sp.width, base)), (int(x), int(y + dy + topo)))
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rectangle([x0, 0, x1, H], fill=255)
        a = np.array(texto)
        a[..., 3] = (a[..., 3].astype(np.uint16) * np.array(m) // 255).astype(np.uint8)
        im.alpha_composite(Image.fromarray(a))
        arr = pil2np(im)
        if self.estilo == "titulo":
            arr = girar3d(arr, 22 * (1 - ease_out(dt / 0.7)))
        return arr


class Legendas:
    """Legenda palavra a palavra: cada palavra surge com mola no instante em que é falada e a
    marcação champanhe desliza de uma palavra para a próxima."""

    def __init__(self, palavras, cfg, W, H, keep):
        self.cfg, self.W, self.H = cfg, W, H
        corr = {k.lower(): v for k, v in cfg.get("correcoes", {}).items()}
        enf = {e.lower().strip(".,!?") for e in cfg.get("enfase", [])}
        dentro = lambda t: any(a <= t < b for a, b in keep)
        ws = []
        for w in palavras:
            if not dentro((w["ini"] + w["fim"]) / 2):
                continue
            t = corr.get(w["t"].lower(), w["t"])
            if cfg.get("sem_pontuacao", True):
                t = t.rstrip(",.;:") if not t.endswith(("?", "!")) else t
            if t:
                ws.append(dict(w, t=t, orig=w["t"], enf=t.lower().strip(".,!?;:") in enf))
        n = cfg.get("palavras_por_bloco", 3)
        self.blocos, cur = [], []
        for i, w in enumerate(ws):
            cur.append(w)
            fim_frase = w["orig"][-1] in ".!?:,"
            pausa = i + 1 < len(ws) and ws[i + 1]["ini"] - w["fim"] > 0.4
            if len(cur) >= n or fim_frase or pausa or i == len(ws) - 1:
                self.blocos.append(cur)
                cur = []
        tam = cfg.get("tamanho", 76 if W < 1500 else 64)
        self.f = fonte("Black", tam)
        self.lay = {}

    def bloco_em(self, t):
        for i, b in enumerate(self.blocos):
            fim = self.blocos[i + 1][0]["ini"] if i + 1 < len(self.blocos) else b[-1]["fim"] + 0.5
            fim = min(fim, b[-1]["fim"] + 0.7)
            if b[0]["ini"] - 0.04 <= t < fim:
                return i
        return None

    def layout(self, i):
        if i in self.lay:
            return self.lay[i]
        b, f, gap = self.blocos[i], self.f, 20
        up = self.cfg.get("maiusculas")
        txt = [w["t"].upper() if up else w["t"] for w in b]
        larg = [f.getlength(x) for x in txt]
        linhas = [list(range(len(txt)))]
        if sum(larg) + gap * (len(txt) - 1) > self.W * 0.82 and len(txt) > 1:
            m = (len(txt) + 1) // 2
            linhas = [list(range(m)), list(range(m, len(txt)))]
        lh = int(f.size * 1.34)
        Wc = int(max(sum(larg[k] for k in L) + gap * (len(L) - 1) for L in linhas)) + 80
        Hc = lh * len(linhas) + 40
        pos = {}
        for li, L in enumerate(linhas):
            x = (Wc - (sum(larg[k] for k in L) + gap * (len(L) - 1))) / 2
            for k in L:
                pos[k] = (x, 18 + li * lh, larg[k])
                x += larg[k] + gap
        sprites = []
        for k, t in enumerate(txt):
            def spr(cor, stroke):
                im = Image.new("RGBA", (int(larg[k]) + 24, lh + 12), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((12, 4), t, font=f, fill=cor, stroke_width=stroke, stroke_fill=MARCA["marinho"])
                return im
            normal = spr(MARCA["champanhe"] if b[k]["enf"] else (255, 255, 255), 7)
            sprites.append((normal, spr(MARCA["marinho"], 0)))
        self.lay[i] = (Wc, Hc, pos, sprites, lh)
        return self.lay[i]

    def render(self, i, t):
        b = self.blocos[i]
        Wc, Hc, pos, sprites, lh = self.layout(i)
        im = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        cur = max([k for k, w in enumerate(b) if w["ini"] - 0.03 <= t] or [0])
        # marcação desliza da palavra anterior para a atual
        pr = ease_out((t - b[cur]["ini"]) / 0.12)
        x, y, w = pos[cur]
        if cur > 0 and pos[cur - 1][1] == y:
            px, _, pw = pos[cur - 1]
            x, w = lerp(px, x, pr), lerp(pw, w, pr)
            esc = 1.0
        else:
            esc = 0.6 + 0.4 * clamp01(mola((t - b[cur]["ini"]) / 0.35))
        cx, cy = x + w / 2, y + lh / 2 + 2
        hw, hh = (w / 2 + 16) * esc, (lh / 2 + 2) * esc
        ImageDraw.Draw(im).rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh], 10, fill=MARCA["champanhe"] + (255,))
        for k, wd in enumerate(b):
            dt = t - wd["ini"]
            if dt < -0.03:
                continue
            p = clamp01(mola(max(dt, 0) / 0.32, 8, 13))
            sp = sprites[k][1] if k == cur else sprites[k][0]
            s = 0.55 + 0.45 * p
            if s < 0.995:
                sp = sp.resize((max(2, int(sp.width * s)), max(2, int(sp.height * s))), Image.BILINEAR)
            x, y, w = pos[k]
            dy = (1 - clamp01(p)) * 22
            im.alpha_composite(sp, (int(x + w / 2 - sp.width / 2), int(y + lh / 2 + 4 - sp.height / 2 + dy)))
        return pil2np(im)


class Leo:
    """Leo 3D: entra deslizando com giro e mola, 'respira' (flutua e balança) e sai deslizando."""

    def __init__(self, e, W, H):
        p = ASSETS / "leo" / f"cut-{e.get('pose', 'apontando')}.png"
        im = Image.open(p if p.exists() else ASSETS / "leo" / "leo3d-cut.png").convert("RGBA")
        alt = int(H * e.get("altura", 0.27))
        im = im.resize((int(im.width * alt / im.height), alt), Image.LANCZOS)
        self.lado = e.get("lado", "direita")
        if self.lado == "esquerda":
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        self.spr, _ = sombra(pil2np(im), 18, 0.45, (0, 16))
        self.W, self.H = W, H
        self.cx = W * e.get("x", 0.80 if self.lado == "direita" else 0.20)
        self.base = H * e.get("y", 0.62)

    def desenhar(self, frame, dt, rest):
        sgn = 1 if self.lado == "direita" else -1
        ent = ease_out_back(dt / 0.55, 1.4)
        sai = ease_in(1 - rest / 0.35) if rest < 0.35 else 0
        dx = sgn * (1 - ent) * self.W * 0.45 + sgn * sai * self.W * 0.5
        ang = sgn * (-14 * (1 - clamp01(ent)) + 1.6 * math.sin(dt * 1.7)) - sgn * 10 * sai
        bob = 7 * math.sin(dt * 2.3)
        esc = 1 + 0.012 * math.sin(dt * 2.3 + 1)
        spr = transformar(self.spr, esc, ang)
        h, w = spr.shape[:2]
        blend(frame, spr, self.cx - w / 2 + dx, self.base - h + bob, 1.0)


class Objeto3D:
    """Logo extrudado em 3D (frente + camadas laterais), com luz e reflexo que acompanham o giro.
    Entra girando com mola, flutua balançando e sai girando para o lado. Faces em assets/3d/<nome>.png."""

    def __init__(self, e, W, H):
        p = Path(e["arquivo"]) if "arquivo" in e else ASSETS / "3d" / f"{e['nome']}.png"
        im = Image.open(p).convert("RGBA")
        im = im.crop(im.getbbox())
        lado = int(W * e.get("tamanho", 0.24))
        im = im.resize((lado, int(im.height * lado / im.width)), Image.LANCZOS)
        pad = int(lado * 0.18)
        face = np.zeros((im.height + 2 * pad, im.width + 2 * pad, 4), np.uint8)
        face[pad:pad + im.height, pad:pad + im.width] = pil2np(im)
        self.face = face
        lat = face.copy()
        lat[..., :3] = (lat[..., :3].astype(np.float32) * 0.5).astype(np.uint8)
        self.lat = lat
        self.prof = max(8, int(lado * 0.07))
        self.W, self.H = W, H
        self.cx, self.cy = W * e.get("x", 0.5), H * e.get("y", 0.3)
        self.fase = e.get("fase", 0.0)
        self.cache = {}

    def sprite(self, graus):
        k = int(round(graus))
        if k in self.cache:
            return self.cache[k]
        th = math.radians(k)
        h, w = self.face.shape[:2]
        acc = np.zeros_like(self.face)
        passo = math.sin(th)
        # laterais: cópias escurecidas deslocadas na direção da espessura (de trás para frente)
        lat = girar3d(self.lat, k)
        n = self.prof * 2
        for i in range(n, 0, -1):
            M = np.float32([[1, 0, -i * passo * 0.5], [0, 1, i * 0.12]])
            camada = cv2.warpAffine(lat, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
            if i > n * 0.6:  # parte de trás da espessura um pouco mais escura
                camada = camada.copy()
                camada[..., :3] = (camada[..., :3] * 0.8).astype(np.uint8)
            acc = alpha_over(acc, camada)
        fr = girar3d(self.face, k).astype(np.float32)
        # luz: frente mais clara de frente para a câmera + faixa de reflexo que corre com o giro
        luz = 0.82 + 0.25 * math.cos(th)
        xs = np.linspace(-1, 1, w)[None, :]
        faixa = np.exp(-((xs - (-0.9 + 1.8 * (0.5 + k / 120))) ** 2) / 0.02) * 0.35
        fr[..., :3] = np.clip(fr[..., :3] * luz + 255 * faixa[..., None] * (fr[..., 3:4] / 255), 0, 255)
        acc = alpha_over(acc, fr.astype(np.uint8))
        out, _ = sombra(acc, int(w * 0.05), 0.5, (0, int(h * 0.06)))
        self.cache[k] = out
        return out

    def desenhar(self, frame, dt, rest):
        ent = clamp01(dt / 0.7)
        sai = ease_in(1 - rest / 0.45) if rest < 0.45 else 0.0
        graus = -85 * (1 - mola(ent, 6, 9)) + 16 * math.sin(dt * 1.6 + self.fase) * ease_out(ent) + 88 * sai
        graus = max(-89, min(89, graus))
        esc = (0.35 + 0.65 * ease_out_back(ent, 1.6)) * (1 - 0.6 * sai)
        spr = self.sprite(graus)
        spr = transformar(spr, max(esc, 0.05))
        h, w = spr.shape[:2]
        bob = 10 * math.sin(dt * 2.0 + self.fase)
        sobe = (1 - ease_out(ent)) * 60
        blend(frame, spr, self.cx - w / 2, self.cy - h / 2 + bob + sobe, clamp01(dt / 0.15) * (1 - sai))


class Elementos:
    """titulo | destaque | leo | broll | imagem — tempos na linha do tempo original."""

    def __init__(self, lst, W, H, map_out, palavras=()):
        self.W, self.H, self.items = W, H, []
        norm = lambda t: t.lower().strip(".,!?;:\"'")

        def achar(txt, n=1, depois=0.0):
            alvo = [norm(x) for x in txt.split()]
            achados = 0
            for i in range(len(palavras)):
                if palavras[i]["ini"] < depois:
                    continue
                if [norm(w["t"]) for w in palavras[i:i + len(alvo)]] == alvo:
                    achados += 1
                    if achados == n:
                        return palavras[i]["ini"], palavras[i + len(alvo) - 1]["fim"]
            sys.exit(f"Âncora não encontrada na transcrição: '{txt}' (ocorrência {n})")

        for e in lst:
            e = dict(e)
            # âncora: o efeito entra na palavra exata ("na": "inteligência artificial") e sai no fim
            # de outra fala ("ate": "superlegal"), em vez de tempos digitados à mão
            if "na" in e:
                a, b = achar(e["na"], e.get("ocorrencia", 1))
                e["ini"] = a - e.get("antecipa", 0.12)
                e.setdefault("fim", b + e.get("segura", 1.2))
                if "ate" in e:
                    e["fim"] = achar(e["ate"], 1, a)[1] + e.get("segura", 0.25)
            if "saida" in e:  # tempos já na linha do tempo final (ex.: título sobre o gancho)
                e["o_ini"], e["o_fim"] = e["saida"]
            else:
                e["o_ini"], e["o_fim"] = map_out(e["ini"]), map_out(e["fim"])
            if e["o_fim"] <= e["o_ini"]:
                continue
            tp = e["tipo"]
            if tp in ("titulo", "destaque"):
                e["obj"] = Cartao(e["texto"], W * (0.86 if tp == "titulo" else 0.8), tp, e.get("tam"))
                e.setdefault("y", 0.15 if tp == "titulo" else 0.12)
            elif tp == "leo":
                e["obj"] = Leo(e, W, H)
            elif tp == "objeto3d":
                e["obj"] = Objeto3D(e, W, H)
            elif tp == "imagem":
                im = Image.open(e["arquivo"]).convert("RGBA")
                lw = int(W * e.get("largura", 0.6))
                im = im.resize((lw, int(im.height * lw / im.width)), Image.LANCZOS)
                e["img"], _ = sombra(pil2np(im), 20, 0.4)
                e.setdefault("y", 0.3)
            elif tp == "broll":
                p = Path(e["arquivo"])
                if p.suffix.lower() in (".mp4", ".mov", ".m4v"):
                    e["cap"] = cv2.VideoCapture(str(p))
                else:
                    e["still"] = cv2.imread(str(p))
            self.items.append(e)

    def eventos(self):
        """Instantes de entrada (para o som de 'pop')."""
        return [e["o_ini"] for e in self.items if e["tipo"] in ("titulo", "destaque", "leo", "imagem", "objeto3d")]

    def ativo(self, t, tipo):
        return any(e["tipo"] == tipo and e["o_ini"] <= t < e["o_fim"] for e in self.items)

    def broll(self, t):
        for e in self.items:
            if e["tipo"] == "broll" and e["o_ini"] <= t < e["o_fim"]:
                if "cap" in e:
                    ok, f = e["cap"].read()
                    if not ok:
                        e["cap"].set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, f = e["cap"].read()
                else:
                    f = e["still"]
                p = (t - e["o_ini"]) / max(e["o_fim"] - e["o_ini"], 0.01)
                return cobrir(f, self.W, self.H, 1.0 + 0.08 * p)
        return None

    def desenhar(self, frame, t):
        for e in self.items:
            if e["tipo"] == "broll" or not (e["o_ini"] <= t < e["o_fim"]):
                continue
            dt, rest = t - e["o_ini"], e["o_fim"] - t
            if e["tipo"] in ("leo", "objeto3d"):
                e["obj"].desenhar(frame, dt, rest)
                continue
            if e["tipo"] == "imagem":
                p = clamp01(mola(dt / 0.5, 6, 10))
                sai = ease_in(1 - rest / 0.25) if rest < 0.25 else 0
                img = transformar(e["img"], max(0.05, p * (1 - 0.3 * sai)), 3 * (1 - clamp01(p)))
                alpha = clamp01(dt / 0.12) * (1 - sai)
            else:
                img, alpha = e["obj"].render(dt, rest), 1.0
            h, w = img.shape[:2]
            blend(frame, img, self.W * e.get("x", 0.5) - w / 2, self.H * e["y"] - h / 2, alpha)


def cobrir(f, W, H, z=1.0, cx=0.5, cy=0.5, flags=cv2.INTER_LINEAR):
    h, w = f.shape[:2]
    s = max(W / w, H / h) * z
    M = np.float32([[s, 0, W / 2 - cx * w * s], [0, s, H / 2 - cy * h * s]])
    return cv2.warpAffine(f, M, (W, H), flags=flags, borderMode=cv2.BORDER_REFLECT)


def _ticket(esc=1.0, ox=0.0, oy=0.0):
    """Contorno do ícone Ticket (Lucide, caixa 24, o logo do GiraHub) a partir do recorte da esquerda,
    mais os 3 picotes. Devolve (contorno, picotes) em pixels."""
    def arco(cx, cy, r, a0, a1, n=14):
        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

    def seg(a, b, n=10):
        return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
    c = (arco(2, 12, 3, -90, 90) + seg((2, 15), (2, 17), 3) + arco(4, 17, 2, 180, 90, 8) + seg((4, 19), (20, 19), 40)
         + arco(20, 17, 2, 90, 0, 8) + seg((22, 17), (22, 15), 3) + arco(22, 12, 3, 90, 270) + seg((22, 9), (22, 7), 3)
         + arco(20, 7, 2, 0, -90, 8) + seg((20, 5), (4, 5), 40) + arco(4, 7, 2, -90, -180, 8) + seg((2, 7), (2, 9), 3))
    f = lambda pts: [(ox + x * esc, oy + y * esc) for x, y in pts]
    return f(c), [f([(13, y0), (13, y0 + 2)]) for y0 in (5, 11, 17)]


def desenhar_ticket(img, ox, oy, esc, cor, esp, p=1.0, picotes=1.0):
    """Desenha o ticket traçado até a fração p do contorno (pontas redondas) e os picotes até 'picotes'."""
    c, pics = _ticket(esc, ox, oy)
    n = int(len(c) * clamp01(p))
    if n > 1:
        pts = np.int32(c[:n])
        cv2.polylines(img, [pts], p >= 1, cor, esp, cv2.LINE_AA)
        for x, y in (pts[0], pts[-1]):
            cv2.circle(img, (int(x), int(y)), esp // 2, cor, -1, cv2.LINE_AA)
    for k, (a, b) in enumerate(pics):
        q = clamp01(mola((picotes * 3 - k) / 1.0, 7, 12)) if picotes < 1 else 1.0
        if q <= 0.02:
            continue
        mx, my, h = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (b[1] - a[1]) / 2 * q
        cv2.line(img, (int(mx), int(my - h)), (int(mx), int(my + h)), cor, esp, cv2.LINE_AA)
        for y in (my - h, my + h):
            cv2.circle(img, (int(mx), int(y)), esp // 2, cor, -1, cv2.LINE_AA)


class FundoMarca:
    """Marinho (ou papel) com luz ambiente difusa atrás da pessoa e o motivo da marca em traço fino:
    o ciclo PDCA (4 gates) no @pontes_brain, o ticket da senha da gira no GiraHub.
    Um ponto de destaque percorre o motivo devagar, sem distrair."""

    def __init__(self, W, H, variante="marinho"):
        self.W, self.H = W, H
        self.S = 1.18
        w, h = int(W * self.S), int(H * self.S)
        escuro = variante == "marinho"
        base = np.array(MARCA["marinho"] if escuro else MARCA["papel"], np.float32)[::-1]
        self.traco = bgr(MARCA["champanhe"] if escuro else MARCA["marinho"])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w * 0.5, h * 0.36
        r = np.sqrt(((xx - cx) / (w * 0.75)) ** 2 + ((yy - cy) / (h * 0.55)) ** 2)
        luz = np.clip(1 - r, 0, 1) ** 1.6
        fator = (0.62 + 0.75 * luz) if escuro else (0.90 + 0.12 * luz)
        img = (base[None, None, :] * fator[..., None]).clip(0, 255).astype(np.uint8)
        self.cx, self.cy, self.r = int(w * 0.5), int(h * 0.40), int(min(w, h) * 0.44)
        self.motivo = CFG.get("fundo_motivo", "pdca")
        ov = img.copy()
        if self.motivo in ("anel", "nenhum"):
            self.contorno = [(self.cx + self.r * math.cos(math.radians(a)), self.cy + self.r * math.sin(math.radians(a)))
                             for a in range(0, 360, 2)]
            if self.motivo == "anel":
                cv2.circle(ov, (self.cx, self.cy), self.r, self.traco, 3, cv2.LINE_AA)
                cv2.circle(ov, (self.cx, self.cy), int(self.r * 0.56), self.traco, 1, cv2.LINE_AA)
            self.img = cv2.addWeighted(ov, 0.22, img, 0.78, 0)
            self.base = cobrir(img, W, H)
            return
        if self.motivo == "ticket":
            esc = w * 0.74 / 20
            ox, oy = self.cx - 12 * esc, self.cy - 12 * esc
            desenhar_ticket(ov, ox, oy, esc, self.traco, 3)
            self.contorno = _ticket(esc, ox, oy)[0]
            self.img = cv2.addWeighted(ov, 0.22, img, 0.78, 0)
            self.base = cobrir(img, W, H)
            return
        for k, (lbl, a0) in enumerate([("PLAN", 180), ("DO", 270), ("CHECK", 0), ("ACT", 90)]):
            cv2.ellipse(ov, (self.cx, self.cy), (self.r, self.r), 0, a0 + 5, a0 + 85, self.traco, 3, cv2.LINE_AA)
            am = math.radians(a0 + 45)
            tx, ty = self.cx + (self.r + 64) * math.cos(am), self.cy + (self.r + 64) * math.sin(am)
            pim = Image.fromarray(cv2.cvtColor(ov, cv2.COLOR_BGR2RGB))
            ImageDraw.Draw(pim).text((tx, ty), f"G{k + 1} · {lbl}", font=fonte("Bold", 30), fill=bgr(self.traco), anchor="mm")
            ov = cv2.cvtColor(np.array(pim), cv2.COLOR_RGB2BGR)
        cv2.circle(ov, (self.cx, self.cy), int(self.r * 0.56), self.traco, 1, cv2.LINE_AA)
        self.img = cv2.addWeighted(ov, 0.28, img, 0.72, 0)
        self.base = cobrir(img, W, H)  # só o gradiente com a luz difusa (usado na vinheta)

    def quadro(self, t, z=1.0, dx=0.5):
        f = self.img.copy()
        ov = f.copy()
        if self.motivo == "nenhum":
            return cobrir(f, self.W, self.H, z, dx, 0.5)
        if self.motivo in ("ticket", "anel"):  # luz que percorre o contorno do motivo (20 s por volta)
            c, n = self.contorno, len(self.contorno)
            i = int((t / 20 % 1) * n)
            rastro = np.int32([c[(i - k) % n] for k in range(n // 9, -1, -1)])
            cv2.polylines(ov, [rastro], False, self.traco, 4, cv2.LINE_AA)
            cv2.circle(ov, (int(c[i][0]), int(c[i][1])), 9, self.traco, -1, cv2.LINE_AA)
            f = cv2.addWeighted(ov, 0.55, f, 0.45, 0)
            return cobrir(f, self.W, self.H, z, dx, 0.5)
        a = (t * 24) % 360  # 15 s por volta
        cv2.ellipse(ov, (self.cx, self.cy), (self.r, self.r), 0, a - 50, a, self.traco, 4, cv2.LINE_AA)
        px, py = self.cx + self.r * math.cos(math.radians(a)), self.cy + self.r * math.sin(math.radians(a))
        cv2.circle(ov, (int(px), int(py)), 9, self.traco, -1, cv2.LINE_AA)
        f = cv2.addWeighted(ov, 0.55, f, 0.45, 0)
        return cobrir(f, self.W, self.H, z, dx, 0.5)


# ───────────────────────────── renderizar ─────────────────────────────

class Rosto:
    def __init__(self, r):
        a = np.array(r["amostras"], np.float64)
        self.t, self.x, self.y, self.h = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
        k = 5  # suaviza ~2,5 s para o enquadramento não "nadar"
        if len(self.x) > k:
            ker = np.ones(k) / k
            pad = lambda v: np.convolve(np.pad(v, k // 2, mode="edge"), ker, "valid")
            self.x, self.y, self.h = pad(self.x), pad(self.y), pad(self.h)

    def em(self, t):
        return (float(np.interp(t, self.t, self.x)), float(np.interp(t, self.t, self.y)), float(np.interp(t, self.t, self.h)))


class Segmentador:
    """Recorte da pessoa. Usa Robust Video Matting (rede recorrente feita para vídeo: cabelo e bordas
    limpos, estável entre quadros, e devolve a cor da frente sem o 'vazamento' do ambiente).
    Sem o modelo, cai para o MediaPipe."""

    def __init__(self):
        rvm = MODELOS / "rvm_mobilenetv3_fp32.onnx"
        self.rvm = None
        if rvm.exists():
            import onnxruntime as ort
            self.ort, self.rvm_path = ort, str(rvm)
            pref = [p for p in ("CoreMLExecutionProvider", "CUDAExecutionProvider") if p in ort.get_available_providers()]
            self.rvm = ort.InferenceSession(self.rvm_path, providers=pref + ["CPUExecutionProvider"])
            self.reset()
        else:
            import mediapipe as mp
            from mediapipe.tasks.python import vision, BaseOptions
            self.mp = mp
            self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=str(MODELOS / "selfie_segmenter.tflite")),
                running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True))
            self.ts = 0
        self.prev = None

    def reset(self):
        self.rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4

    def recortar(self, frame):
        """Devolve (alfa 0..1 float32 HxW, frente BGR uint8 sem vazamento de cor)."""
        if self.rvm is not None:
            h, w = frame.shape[:2]
            x = (cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255).transpose(2, 0, 1)[None]
            ratio = np.array([min(1.0, 512 / max(h, w))], np.float32)
            ent = {"src": x, "r1i": self.rec[0], "r2i": self.rec[1], "r3i": self.rec[2], "r4i": self.rec[3],
                   "downsample_ratio": ratio}
            try:
                fgr, pha, *self.rec = self.rvm.run(None, ent)
            except Exception:  # acelerador recusou o modelo: segue na CPU
                self.rvm = self.ort.InferenceSession(self.rvm_path, providers=["CPUExecutionProvider"])
                fgr, pha, *self.rec = self.rvm.run(None, ent)
            a = pha[0, 0]
            a = np.clip((a - 0.04) / 0.92, 0, 1)  # limpa resíduos quase transparentes do ambiente
            fg = (fgr[0].transpose(1, 2, 0)[..., ::-1] * 255).clip(0, 255).astype(np.uint8)
            return a, fg
        self.ts += 33
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        m = self.seg.segment_for_video(img, self.ts).confidence_masks[0].numpy_view().astype(np.float32)
        m = cv2.resize(m, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        m = np.clip((m - 0.3) / 0.4, 0, 1)
        m = m * m * (3 - 2 * m)
        m = cv2.GaussianBlur(m, (0, 0), 1.5)
        if self.prev is not None and self.prev.shape == m.shape:
            m = 0.55 * m + 0.45 * self.prev
        self.prev = m
        return m, frame

    def fechar(self):
        if self.rvm is None:
            self.seg.close()


def lut_cor(c):
    x = np.arange(256, dtype=np.float32)
    y = (x - 128) * c.get("contraste", 1.0) + 128
    q = c.get("calor", 0.0)
    b = np.clip(y * (1 - q), 0, 255)
    r = np.clip(y * (1 + q), 0, 255)
    return [b.astype(np.uint8), np.clip(y, 0, 255).astype(np.uint8), r.astype(np.uint8)]


def aplicar_cor(f, luts, c):
    f = cv2.merge([cv2.LUT(ch, l) for ch, l in zip(cv2.split(f), luts)])
    s = c.get("saturacao", 1.0)
    if abs(s - 1) > 0.01:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = cv2.LUT(hsv[..., 1], np.clip(np.arange(256) * s, 0, 255).astype(np.uint8))
        f = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    n = c.get("nitidez", 0)
    if n > 0:
        f = cv2.addWeighted(f, 1 + n, cv2.GaussianBlur(f, (0, 0), 2), -n, 0)
    return f


def matriz_enquadre(w0, h0, W, H, z, face, desloc=(0.0, 0.0)):
    fx, fy, fh = face
    if w0 / h0 > W / H:
        ch = h0 / z
        cw = ch * W / H
    else:
        cw = w0 / z
        ch = cw * H / W
    left = fx * w0 - cw / 2
    top = fy * h0 - ch * (0.36 if H > W else 0.42)  # olhos no terço superior
    left = min(max(left, 0), w0 - cw)
    top = min(max(top, 0), h0 - ch)
    s = W / cw
    return np.float32([[s, 0, -left * s + desloc[0]], [0, s, -top * s + desloc[1]]])


def zoom_em(t, zooms, fim_seg=1e9):
    """Ênfases de zoom (fator multiplicador): punch = tranco curto e volta macia; suave = aproximação lenta.
    A volta sempre termina antes do fim do trecho, para o corte seguinte encontrar o mesmo enquadramento."""
    z, tremor = 1.0, (0.0, 0.0)
    for zz in zooms:
        a, f = zz["ini"], zz.get("fator", 1.2)
        b = min(zz["fim"], fim_seg - 0.4) if a < fim_seg else zz["fim"]
        b = max(b, a + 0.15)
        if a <= t < b + 0.35:
            if zz.get("modo", "suave") == "punch":
                p = ease_out((t - a) / 0.1) * (1 - ease_in_out((t - b) / 0.35))
                k = math.exp(-14 * (t - a))
                tremor = (6 * k * math.sin(70 * (t - a)), 4 * k * math.cos(55 * (t - a)))
            else:
                p = ease_in_out(min((t - a) / 0.7, (b + 0.35 - t) / 0.85, 1))
            z *= 1 + (f - 1) * p
    return z, tremor


class Camera:
    """Enquadramento contínuo: zoom-base e centro do rosto seguem suavemente de um corte para o outro,
    então o locutor nunca 'salta' de posição num corte (só os punches marcados no EDL mexem rápido)."""

    def __init__(self, k_zoom=0.06, k_pos=0.08):
        self.z = self.x = self.y = self.h = None
        self.kz, self.kp = k_zoom, k_pos

    def passo(self, z_alvo, face):
        fx, fy, fh = face
        if self.z is None:
            self.z, self.x, self.y, self.h = z_alvo, fx, fy, fh
        else:
            self.z += (z_alvo - self.z) * self.kz
            self.x += (fx - self.x) * self.kp
            self.y += (fy - self.y) * self.kp
            self.h += (fh - self.h) * self.kp
        return self.z, (self.x, self.y, self.h)


def borrao_h(frame, k):
    k = int(k)
    return cv2.blur(frame, (k, 1)) if k > 2 else frame


def transicao(a, b, p, tipo, W, H):
    """Mistura o último quadro do trecho anterior (a) com o novo trecho (b). p: 0→1."""
    if tipo in ("push", "whip"):
        e = ease_in_out(p)
        vel = math.sin(math.pi * p)  # mais rápido no meio → mais borrão
        out = np.empty_like(b)
        off = int(e * W)
        out[:, :W - off] = a[:, off:]
        out[:, W - off:] = b[:, :off]
        return borrao_h(out, 6 + 140 * vel)
    if tipo == "zoom":
        if p < 0.5:
            q = ease_in(p / 0.5)
            f = cobrir(a, W, H, 1 + 0.6 * q)
            k = int(1 + 30 * q) | 1
        else:
            q = 1 - ease_out((p - 0.5) / 0.5)
            f = cobrir(b, W, H, 1 + 0.4 * q)
            k = int(1 + 30 * q) | 1
        return cv2.GaussianBlur(f, (k, k), 0)
    if tipo == "slide":
        e = ease_in_out(p)
        off = int(e * H)
        out = np.empty_like(b)
        out[:H - off] = a[off:]
        out[H - off:] = b[:off]
        vel = math.sin(math.pi * p)
        k = int(5 + 90 * vel)
        return cv2.blur(out, (1, k)) if k > 2 else out
    if tipo == "flash":
        base = a if p < 0.5 else b
        lum = 1 - abs(p - 0.5) * 2
        return cv2.addWeighted(base, 1 - 0.9 * lum, np.full_like(base, bgr(MARCA["papel_2"])), 0.9 * lum, 0)
    return b


def _traco_logo():
    """Caminho do Monograma LP (geometria do lp-simbolo, caixa 512): o L e o P dividem a mesma haste."""
    def seg(a, b, n=40):
        return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
    L = seg((178, 118), (178, 372)) + seg((178, 372), (300, 372))[1:]
    arco = [(290 + 72 * math.cos(math.radians(a)), 212 + 72 * math.sin(math.radians(a))) for a in range(-90, 91, 3)]
    P = seg((178, 140), (290, 140)) + arco[1:] + seg((290, 284), (222, 284))[1:]
    return [[(x - 16, y) for x, y in L], [(x - 16, y) for x, y in P]]


def quadro_intro(W, H, t, fundo, cache, dur=2.2):
    """Vinheta de abertura da marca ativa (igual em todos os vídeos dela)."""
    tipo = CFG.get("intro", {}).get("tipo", "pdca_lp")
    if tipo == "ticket":
        return _intro_ticket(W, H, t, fundo, cache, dur)
    if tipo == "logo":
        return _intro_logo(W, H, t, fundo, cache, dur)
    return _intro_pdca(W, H, t, fundo, cache, dur)


def _intro_logo(W, H, t, fundo, cache, dur=2.2):
    """Vinheta genérica (qualquer marca nova, só com configuração): um anel na cor de destaque se
    desenha, o logo da marca revela-se de dentro para fora com mola e brilho, o nome e o subtítulo
    sobem e a câmera mergulha no logo. Pede só "logo", "cores" e "intro" (nome, sub) no JSON."""
    cx, cy = W // 2, int(H * 0.40)
    if "logo" not in cache:
        cache["logo"] = pil2np(logo_marca(int(W * CFG.get("intro", {}).get("logo_alt", 0.26))))
        lg = cache["logo"]
        g = np.zeros((H, W, 3), np.uint8)
        a = lg[..., 3:4].astype(np.float32) / 255
        cor = np.array(bgr(MARCA["champanhe"]), np.float32)
        y0, x0 = cy - lg.shape[0] // 2, cx - lg.shape[1] // 2
        g[y0:y0 + lg.shape[0], x0:x0 + lg.shape[1]] = (a * cor).astype(np.uint8)
        cache["glow"] = cv2.GaussianBlur(g, (0, 0), W * 0.04)
    f = fundo.base.copy()
    ch = bgr(MARCA["champanhe"])
    r = int(W * 0.30)
    acende = ease_out((t - 0.7) / 0.5)
    if acende > 0:
        f = cv2.add(f, (cache["glow"].astype(np.float32) * 0.6 * acende).astype(np.uint8))
    ov = f.copy()
    pa = ease_in_out((t - 0.05) / 0.8)
    if pa > 0:
        cv2.ellipse(ov, (cx, cy), (r, r), 0, -90, -90 + 360 * pa, ch, 4, cv2.LINE_AA)
        a = math.radians(-90 + 360 * pa)
        cv2.circle(ov, (int(cx + r * math.cos(a)), int(cy + r * math.sin(a))), 9, ch, -1, cv2.LINE_AA)
    f = cv2.addWeighted(ov, 0.8, f, 0.2, 0)
    p = clamp01(mola((t - 0.45) / 0.6, 6, 10))
    if p > 0:
        lg = cache["logo"].copy()
        h, w = lg.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        raio = math.hypot(w, h) / 2 * ease_out((t - 0.45) / 0.5)
        dentro = ((xx - w / 2) ** 2 + (yy - h / 2) ** 2) <= raio ** 2
        lg[..., 3] = np.where(dentro, lg[..., 3], 0)
        lg = transformar(lg, max(0.05, 0.85 + 0.15 * p))
        blend(f, lg, cx - lg.shape[1] / 2, cy - lg.shape[0] / 2)
    sai = _assinatura(f, cache, W, H, t, dur)
    return _mergulho(f, sai, cx, cy, W, H)


def _mergulho(f, sai, cx, cy, W, H):
    """Câmera avança para dentro do símbolo (zoom com o símbolo parado + desfoque)."""
    if sai > 0:
        z = 1 + 2.2 * sai
        M = np.float32([[z, 0, (1 - z) * cx], [0, z, (1 - z) * cy]])
        f = cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        k = int(1 + 18 * sai) | 1
        f = cv2.GaussianBlur(f, (k, k), 0)
    return f


def _assinatura(f, cache, W, H, t, dur):
    """Nome (cartão cinético) e subtítulo da vinheta; devolve o progresso de saída."""
    if "nome" not in cache:
        it = CFG.get("intro", {})
        cache["nome"] = Cartao(it.get("nome", "Leonardo Pontes"), W * 0.9, "titulo", 76)
        f2 = fonte("Bold", 38)
        sub = it.get("sub", "MENTORIA DE PRODUTO  ·  DIAGNÓSTICO")
        im = Image.new("RGBA", (int(f2.getlength(sub)) + 60, 60), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((30, 8), sub, font=f2, fill=MARCA["champanhe"])
        cache["sub"] = pil2np(im)
    sai = ease_in((t - (dur - 0.4)) / 0.4)
    nm = cache["nome"].render(t - 1.0, 99)
    blend(f, nm, W / 2 - nm.shape[1] / 2, H * 0.67 - sai * 80, 1 - sai)
    ps = ease_out((t - 1.35) / 0.4)
    sb = cache["sub"]
    blend(f, sb, W / 2 - sb.shape[1] / 2, H * 0.745 + (1 - ps) * 30 - sai * 80, ps * (1 - sai))
    return sai


def _intro_ticket(W, H, t, fundo, cache, dur=2.2):
    """Vinheta GiraHub (~2 s): o ticket da senha da gira é traçado em ouro a partir do recorte, os
    picotes entram um a um, a senha 001 se acende dentro dele, o nome sobe e a câmera mergulha no ticket."""
    f = fundo.base.copy()
    cx, cy = W // 2, int(H * 0.40)
    esc = W * 0.62 / 20
    ox, oy = cx - 12 * esc, cy - 12 * esc
    ouro = bgr(MARCA["champanhe"])
    esp = max(6, int(esc * 1.1))
    # brilho ambiente que acende atrás do ticket quando ele se fecha
    acende = ease_out((t - 0.85) / 0.5)
    if acende > 0:
        if "glow" not in cache:
            g = np.zeros((H, W, 3), np.uint8)
            desenhar_ticket(g, ox, oy, esc, ouro, esp * 3)
            cache["glow"] = cv2.GaussianBlur(g, (0, 0), W * 0.05)
        f = cv2.add(f, (cache["glow"].astype(np.float32) * 0.55 * acende).astype(np.uint8))
    ov = np.zeros_like(f)
    desenhar_ticket(ov, ox, oy, esc, ouro, esp, ease_in_out((t - 0.05) / 0.85), clamp01((t - 0.75) / 0.45))
    m = cv2.cvtColor(ov, cv2.COLOR_BGR2GRAY) > 0
    # pulso de "carimbo" quando o último picote entra
    pulso = 1 + 0.05 * math.sin(max(0, t - 1.15) * 10) * math.exp(-max(0, t - 1.15) * 5) if t > 1.15 else 1
    if pulso != 1:
        M = np.float32([[pulso, 0, (1 - pulso) * cx], [0, pulso, (1 - pulso) * cy]])
        ov = cv2.warpAffine(ov, M, (W, H), flags=cv2.INTER_LINEAR)
        m = cv2.cvtColor(ov, cv2.COLOR_BGR2GRAY) > 0
    f[m] = ov[m]
    # a senha do dia acende na parte maior do ticket
    if "senha" not in cache:
        fs = fonte("Black", int(esc * 3.0), "titulo")
        im = Image.new("RGBA", (int(fs.getlength("001")) + 20, int(esc * 7)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 0), "001", font=fs, fill=MARCA["champanhe"])
        cache["senha"] = pil2np(im)
    ps = clamp01(mola((t - 1.0) / 0.45, 7, 12))
    if ps > 0:
        sn = transformar(cache["senha"], max(ps, 0.05))
        blend(f, sn, ox + 8.8 * esc - sn.shape[1] / 2, cy - sn.shape[0] / 2 + esc * 0.15, clamp01(ps * 1.5))
    sai = _assinatura(f, cache, W, H, t, dur)
    return _mergulho(f, sai, cx, cy, W, H)


def _intro_pdca(W, H, t, fundo, cache, dur=2.2):
    """Vinheta @pontes_brain (~2 s): o ciclo PDCA dos 4 gates se desenha, o Monograma LP é traçado
    no centro com o ponto champanhe, o nome sobe e a câmera mergulha no símbolo."""
    if "lp" not in cache:
        cache["lp"] = np.array(Image.open(ASSETS / "lp-simbolo-claro.png").convert("RGBA"))
        cache["tracos"] = _traco_logo()
    f = fundo.base.copy()
    cx, cy, r = W // 2, int(H * 0.40), int(W * 0.36)
    ch = bgr(MARCA["champanhe"])
    ov = f.copy()
    # 1) os 4 gates (PDCA) desenham-se em sequência, cada arco com seu rótulo
    for k, (lbl, a0) in enumerate([("PLAN", 180), ("DO", 270), ("CHECK", 0), ("ACT", 90)]):
        p = ease_out((t - 0.08 - 0.13 * k) / 0.4)
        if p <= 0:
            continue
        cv2.ellipse(ov, (cx, cy), (r, r), 0, a0 + 5, a0 + 5 + 80 * p, ch, 4, cv2.LINE_AA)
        if p > 0.6:
            am = math.radians(a0 + 45)
            tx, ty = cx + (r + 70) * math.cos(am), cy + (r + 70) * math.sin(am)
            pim = Image.fromarray(cv2.cvtColor(ov, cv2.COLOR_BGR2RGB))
            ImageDraw.Draw(pim).text((tx, ty), f"G{k + 1} · {lbl}", font=fonte("Bold", 30),
                                     fill=MARCA["champanhe"] + (int(255 * (p - 0.6) / 0.4),), anchor="mm")
            ov = cv2.cvtColor(np.array(pim), cv2.COLOR_RGB2BGR)
    # ponto que percorre o ciclo depois de desenhado
    if t > 0.7:
        a = 180 + 360 * ease_in_out((t - 0.7) / 1.2)
        px, py = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
        cv2.circle(ov, (int(px), int(py)), 10, ch, -1, cv2.LINE_AA)
    f = cv2.addWeighted(ov, 0.75, f, 0.25, 0)
    # 2) o Monograma LP é traçado (máscara que segue o caminho real do símbolo)
    lp = cache["lp"]
    lado = int(W * 0.40)
    esc = lado / 1024 * 2  # caixa 512 → 1024 px do PNG → lado
    m = np.zeros((lado, lado), np.uint8)
    pl = ease_in_out((t - 0.35) / 0.45)
    pp = ease_in_out((t - 0.6) / 0.5)
    for tr, p in zip(cache["tracos"], (pl, pp)):
        n = int(len(tr) * p)
        if n > 1:
            pts = np.int32([[x * esc, y * esc] for x, y in tr[:n]])
            cv2.polylines(m, [pts], False, 255, int(60 * esc), cv2.LINE_AA)
    spr = cv2.resize(lp, (lado, lado), interpolation=cv2.INTER_AREA)
    corpo = spr.copy()
    # o ponto champanhe fica de fora do traço e entra com mola
    yy, xx = np.mgrid[0:lado, 0:lado]
    no_ponto = ((xx - 346 * esc) ** 2 + (yy - 372 * esc) ** 2) < (34 * esc) ** 2
    corpo[..., 3] = np.where(no_ponto, 0, np.minimum(corpo[..., 3], m))
    pulso = 1 + 0.06 * math.sin(max(0, t - 1.15) * 9) * math.exp(-max(0, t - 1.15) * 4)
    corpo = transformar(corpo, pulso)
    blend(f, corpo, cx - lado / 2, cy - lado / 2)
    pd = clamp01(mola((t - 1.05) / 0.4, 7, 12))
    if pd > 0:
        dot = np.zeros((lado, lado, 4), np.uint8)
        cv2.circle(dot, (int(346 * esc), int(372 * esc)), int(26 * esc * pd), MARCA["champanhe"] + (255,), -1, cv2.LINE_AA)
        blend(f, dot, cx - lado / 2, cy - lado / 2)
    # 3) nome e assinatura; mergulho final para dentro do símbolo
    sai = _assinatura(f, cache, W, H, t, dur)
    return _mergulho(f, sai, cx, cy, W, H)


def logo_marca(alt):
    """Logo da marca ativa (PNG com transparência) com altura alt, proporção preservada."""
    im = Image.open(ASSETS / CFG.get("logo", "lp-simbolo-claro.png")).convert("RGBA")
    return im.resize((max(1, int(im.width * alt / im.height)), alt), Image.LANCZOS)


def cartao_cta(cfg, W, H, t, fundo, cache):
    """Encerramento animado: logo da marca com mola, chamada cinética, URL (+ apoio) e, no @pontes_brain, Leo apontando."""
    f = fundo.quadro(t + 100, 1.0 + 0.02 * t)
    if "logo" not in cache:
        cache["logo"] = pil2np(logo_marca(int(W * CFG.get("cta_logo_alt", 0.16))))
        cache["cham"] = Cartao(cfg["chamada"], W * 0.86, "titulo", 78)
        cache["url"] = Cartao(cfg["url"], W * 0.92, "destaque", 50)
        cache["apoio"] = None
        if cfg.get("apoio"):
            fa = fonte("Bold", 40)
            im = Image.new("RGBA", (int(fa.getlength(cfg["apoio"])) + 40, 64), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((20, 6), cfg["apoio"], font=fa, fill=MARCA["papel"])
            cache["apoio"] = pil2np(im)
        pose = ASSETS / "leo" / f"cut-{cfg.get('pose_leo', 'apontando')}.png"
        tem_leo = CFG.get("leo", True) and cfg.get("pose_leo") and pose.exists()
        cache["leo"] = Leo({"pose": cfg["pose_leo"], "altura": 0.33, "x": 0.5, "y": 0.93, "lado": "direita"}, W, H) if tem_leo else None
    lg = cache["logo"]
    p = clamp01(mola(t / 0.6, 6, 10))
    s = transformar(lg, max(p, 0.02), -20 * (1 - p))
    blend(f, s, W / 2 - s.shape[1] / 2, H * 0.13, clamp01(t / 0.15))
    longe = 99
    c = cache["cham"].render(t - 0.25, longe)
    blend(f, c, W / 2 - c.shape[1] / 2, H * 0.31)
    u = cache["url"].render(t - 0.75, longe)
    pulso = 1 + 0.025 * math.sin((t - 1.4) * 6) if t > 1.4 else 1
    u = transformar(u, pulso)
    blend(f, u, W / 2 - u.shape[1] / 2, H * 0.47)
    if cache["apoio"] is not None:
        pa = ease_out((t - 1.0) / 0.4)
        ap = cache["apoio"]
        blend(f, ap, W / 2 - ap.shape[1] / 2, H * 0.47 + u.shape[0] + 24 + (1 - pa) * 20, pa)
    if cache["leo"] and t > 0.5:
        leo = cache["leo"]
        dt = t - 0.5
        spr = transformar(leo.spr, 1 + 0.012 * math.sin(dt * 2.3), 1.5 * math.sin(dt * 1.7))
        h, w = spr.shape[:2]
        sobe = (1 - ease_out_back(dt / 0.6, 1.3)) * H * 0.4
        blend(f, spr, W / 2 - w / 2, leo.base - h + sobe + 7 * math.sin(dt * 2.3))
    return f


def gerar_sfx(pasta):
    wh, pop = pasta / "_whoosh.wav", pasta / "_pop.wav"
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.45:c=pink:a=0.6:r=48000",
        "-af", "highpass=f=250,lowpass=f=6000,afade=t=in:d=0.25:curve=exp,afade=t=out:st=0.25:d=0.2,volume=0.16",
        "-ac", "1", str(wh)])
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc='0.5*sin(2*PI*(260+900*exp(-40*t))*t)*exp(-28*t)':d=0.16:s=48000",
        "-af", "volume=0.18", "-ac", "1", str(pop)])
    return wh, pop


def cmd_renderizar(a):
    edl_p = Path(a.edl).resolve()
    pasta = edl_p.parent
    edl = json.load(open(edl_p))
    carregar_marca(edl.get("marca", "pontes_brain"))
    an = json.load(open(pasta / "analise.json"))
    W, H = FORMATOS[edl.get("formato", "vertical")]
    src = edl["fonte"]

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
    cta = edl.get("cta", {})
    dur_cta = cta.get("duracao", 3.5) if cta.get("ativo") else 0
    intro = edl.get("intro", {"ativo": True})
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
    bg_img = cobrir(cv2.imread(fundo["imagem"]), int(W * 1.2), int(H * 1.2)) if tipo_fundo == "imagem" else None
    cor = edl.get("cor", {})
    luts = lut_cor(cor)
    leg = Legendas(an["palavras"], edl.get("legendas", {}), W, H, keep) if edl.get("legendas", {}).get("ativo", True) else None
    els = Elementos(edl.get("elementos", []), W, H, map_out, an["palavras"])
    zooms = edl.get("zooms", [])
    marca = None
    if edl.get("marca_dagua", True):
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
        import time
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
            if edl.get("barra_progresso", True):
                cv2.rectangle(out, (0, 0), (int(W * (t_out + dur_intro) / total), 6), bgr(MARCA["champanhe"]), -1)

        # vinheta de abertura (igual em todos os vídeos)
        cache_intro = {}
        for k in range(int(round(dur_intro * FPS))):
            out = quadro_intro(W, H, k / FPS, fundo_vivo, cache_intro, dur_intro)
            proc.stdin.write(out.tobytes())
            n_out += 1
            ultimo = out
        for si, s in enumerate(segs):
            a_idx, b_idx = int(round(s["qa"] * FPS)), int(round(s["qb"] * FPS))
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
            if edl.get("barra_progresso", True):
                cv2.rectangle(out, (0, 0), (int(W * (n_out / FPS) / total), 6), bgr(MARCA["champanhe"]), -1)
            proc.stdin.write(out.tobytes())
            n_out += 1
        proc.stdin.close()
        proc.wait()

    # 3) áudio: mesmos cortes, limpeza de voz e loudness para Instagram (-14 LUFS)
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
    sh(["ffmpeg", "-y", "-i", src, "-filter_complex", fc_voz, "-map", "[v]", "-ac", "1", str(voz_bruta)])
    alvo_lufs, alvo_tp = au.get("loudness", -16), -2.0
    med = subprocess.run(["ffmpeg", "-i", str(voz_bruta), "-af", f"loudnorm=I={alvo_lufs}:TP={alvo_tp}:LRA=11:print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(med[med.rindex("{"):med.rindex("}") + 1])
    sh(["ffmpeg", "-y", "-i", str(voz_bruta), "-af",
        f"loudnorm=I={alvo_lufs}:TP={alvo_tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
        f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
        "aresample=48000", "-ac", "1", str(voz)])
    fc = f"[0:a]adelay={int(dur_intro * 1000)}:all=1,apad=whole_dur={total:.4f}[voz]"
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
        fc += ";[voz]" + "".join(mix) + f"amix=inputs={len(mix) + 1}:normalize=0:duration=first[mix]"
        alvo = "[mix]"
    fc += f";{alvo}alimiter=limit=0.79:attack=5:release=60:level=disabled[fim]"  # teto em -2 dBFS
    alvo = "[fim]"
    tmp_a = pasta / "_audio.wav"
    sh(["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", alvo, "-t", f"{total:.4f}", "-ar", "48000", "-ac", "2", str(tmp_a)])

    sh(["ffmpeg", "-y", "-i", str(tmp_v), "-i", str(tmp_a), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(final)])
    passo = max(total / 12, 0.1)
    sh(["ffmpeg", "-y", "-i", str(final), "-vf", f"fps=1/{passo:.3f},scale=270:-2,tile=6x2:padding=6:color=white",
        "-frames:v", "1", str(pasta / "previa.jpg")])
    for p in (tmp_v, tmp_a, voz_bruta, voz, pasta / "_whoosh.wav", pasta / "_pop.wav"):
        if p.exists():
            p.unlink()
    print(f"Pronto: {final} ({total:.1f}s, {len(segs)} cortes) e {pasta / 'previa.jpg'}")


def folha_marca(W=1080, H=1920):
    """Folha de conferência da marca ativa: vinheta em 5 instantes, fundo, CTA e um quadro com título,
    destaque, legenda e marca d'água. Determinística (serve de referência para o teste)."""
    fundo = FundoMarca(W, H)
    cache, cc = {}, {}
    fr = [quadro_intro(W, H, t, fundo, cache, 2.2) for t in (0.3, 0.7, 1.0, 1.4, 1.95)]
    fr.append(fundo.quadro(3.0))
    cta = dict({"ativo": True, "duracao": 3.5}, **CFG.get("cta", {}))
    fr += [cartao_cta(cta, W, H, t, fundo, cc) for t in (0.6, 2.0)]
    f = fundo.quadro(5.0)
    img = Cartao("Título de teste da marca", W * 0.86, "titulo").render(1.2, 9)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.18)
    img = Cartao("Destaque", W * 0.8, "destaque").render(1.2, 9)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.32)
    pal = [{"t": w, "ini": 0.3 * i, "fim": 0.3 * i + 0.28, "p": 1} for i, w in enumerate("legenda palavra por palavra".split())]
    lg = Legendas(pal, {"enfase": ["palavra"]}, W, H, [(0, 99)])
    img = lg.render(0, 0.35)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.68)
    m, _ = sombra(pil2np(logo_marca(CFG.get("marca_dagua_alt", 80))), 6, 0.5, (0, 3))
    blend(f, m, W - m.shape[1] - 30, H * CFG.get("marca_dagua_y", 0.115), 0.85)
    fr.append(f)
    th = [cv2.resize(x, (270, 480), interpolation=cv2.INTER_AREA) for x in fr]
    return np.vstack([np.hstack(th[:5]), np.hstack(th[5:] + [np.zeros_like(th[0])])])


def medir_audio(video):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    resumo = r[r.rfind("Summary:"):]
    num = lambda chave: float(resumo.split(chave)[1].split()[0])
    return num("I:"), num("Peak:")


def cmd_testar(a):
    """Teste de regressão de todas as marcas: (1) a folha visual tem de bater com testes/referencia/<marca>.png;
    (2) um vídeo sintético de 4 s passa pelo render inteiro (cortes, fundo marca, título, legenda, CTA, áudio)
    e o áudio final precisa ficar entre -17 e -15 LUFS com pico abaixo de -1,5 dBFS."""
    ref_dir, tmp = AQUI / "testes" / "referencia", AQUI / "testes" / "_tmp"
    ref_dir.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    marcas = [a.marca] if a.marca else sorted(p.stem for p in MARCAS.glob("*.json"))
    falhas = []
    src = tmp / "sintetico.mov"
    if not src.exists() and not a.so_visual:
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=4", "-f", "lavfi",
            "-i", "sine=f=180:r=48000:d=4,volume='0.25+0.2*sin(2*PI*3*t)':eval=frame",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(src)])
    for m in marcas:
        carregar_marca(m)
        folha = folha_marca()
        ref = ref_dir / f"{m}.png"
        if a.atualizar or not ref.exists():
            cv2.imwrite(str(ref), folha)
            print(f"[{m}] referência visual gravada: {ref}")
        else:
            r = cv2.imread(str(ref))
            dif = float(np.abs(r.astype(np.int16) - folha.astype(np.int16)).mean()) if r.shape == folha.shape else 99.0
            ok = dif < 1.5
            cv2.imwrite(str(tmp / f"{m}-atual.png"), folha)
            print(f"[{m}] visual: diferença média {dif:.2f} {'OK' if ok else 'FALHOU (veja testes/_tmp/' + m + '-atual.png)'}")
            if not ok:
                falhas.append(f"{m}: visual")
        if a.so_visual:
            continue
        pasta = tmp / m
        pasta.mkdir(exist_ok=True)
        pal = [{"t": w, "ini": 0.4 + 0.35 * i, "fim": 0.4 + 0.35 * i + 0.3, "p": 0.99}
               for i, w in enumerate("este é um teste automático de marca do editor".split())]
        json.dump({"duracao": 4.0, "palavras": pal, "rosto": {"w": 1080, "h": 1920, "quadros": 120,
                   "amostras": [[0, 0.5, 0.35, 0.2]]}}, open(pasta / "analise.json", "w"))
        edl = rascunho_edl(src, pal, dur=4.0)
        edl["segmentos"] = [{"id": 0, "ini": 0.3, "fim": 1.8, "zoom": 1.0, "transicao": None},
                            {"id": 1, "ini": 2.1, "fim": 3.9, "zoom": 1.0, "transicao": "push"}]
        edl["fundo"] = {"tipo": "marca", "parallax": True, "sombra": True}
        edl["elementos"] = [{"tipo": "titulo", "texto": "Teste automático", "na": "teste", "segura": 0.8}]
        edl["cta"]["duracao"] = 1.5
        json.dump(edl, open(pasta / "edl.json", "w"), ensure_ascii=False)
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "renderizar", str(pasta / "edl.json"), "--rapido"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[{m}] render: FALHOU\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
            falhas.append(f"{m}: render")
            continue
        lufs, pico = medir_audio(pasta / "final.mp4")
        ok = -17 <= lufs <= -15 and pico < -1.5
        print(f"[{m}] render: OK · áudio {lufs:.1f} LUFS, pico {pico:.1f} dBFS {'OK' if ok else 'FALHOU'}")
        if not ok:
            falhas.append(f"{m}: áudio")
    print("\nTUDO OK" if not falhas else "\nFALHAS: " + "; ".join(falhas))
    sys.exit(1 if falhas else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analisar")
    p.add_argument("video")
    p.add_argument("--pasta")
    p.add_argument("--marca", default="pontes_brain", help="identidade visual: arquivo marcas/<marca>.json")
    p.add_argument("--modelo", default="small", help="tiny|base|small|medium|large-v3")
    p = sub.add_parser("renderizar")
    p.add_argument("edl")
    p.add_argument("--rapido", action="store_true", help="codificação rápida para conferir")
    p.add_argument("--so-audio", action="store_true", help="refaz só o áudio sobre o vídeo já renderizado")
    p = sub.add_parser("testar", help="teste de regressão de todas as marcas (rode antes de entregar mudanças no editor)")
    p.add_argument("--marca", help="testa só esta marca")
    p.add_argument("--atualizar", action="store_true", help="grava a folha atual como nova referência visual")
    p.add_argument("--so-visual", action="store_true", help="pula o render ponta a ponta")
    a = ap.parse_args()
    {"analisar": cmd_analisar, "renderizar": cmd_renderizar, "testar": cmd_testar}[a.cmd](a)


if __name__ == "__main__":
    main()
