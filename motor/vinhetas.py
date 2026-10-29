"""Vinhetas de abertura (uma por marca) e o cartão de CTA do encerramento."""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .elementos import Leo
from .fundo import desenhar_ticket
from .graficos import Cartao, blend, fonte, pil2np, transformar
from .marca import CFG, CORES, VINHETAS, ErroDeMarca, arquivo_marca, logo_marca, marca_ativa, tem_leo, tem_logo
from .movimento import clamp01, ease_in, ease_in_out, ease_out, ease_out_back, mola
from .util import bgr


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
    tipo = CFG["intro"]["tipo"]
    dono = VINHETAS.get(tipo)
    if dono not in (None, marca_ativa()):  # a validação da marca já barra; aqui é a segunda trava
        raise ErroDeMarca(f"a vinheta {tipo} é exclusiva da marca {dono}")
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
        if tem_logo():
            cache["logo"] = pil2np(logo_marca(int(W * CFG.get("intro", {}).get("logo_alt", 0.26))))
        else:  # marca sem logo: um ponto de destaque no centro do anel faz o papel do símbolo
            d = int(W * 0.07)
            cache["logo"] = np.zeros((d, d, 4), np.uint8)
            cv2.circle(cache["logo"], (d // 2, d // 2), d // 2 - 2, CORES["champanhe"] + (255,), -1, cv2.LINE_AA)
        lg = cache["logo"]
        g = np.zeros((H, W, 3), np.uint8)
        a = lg[..., 3:4].astype(np.float32) / 255
        cor = np.array(bgr(CORES["champanhe"]), np.float32)
        y0, x0 = cy - lg.shape[0] // 2, cx - lg.shape[1] // 2
        g[y0:y0 + lg.shape[0], x0:x0 + lg.shape[1]] = (a * cor).astype(np.uint8)
        cache["glow"] = cv2.GaussianBlur(g, (0, 0), W * 0.04)
    f = fundo.base.copy()
    ch = bgr(CORES["champanhe"])
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
        cache["nome"] = Cartao(it["nome"], W * 0.9, "titulo", 76)
        f2 = fonte("Bold", 38)
        sub = it.get("sub", "")
        im = Image.new("RGBA", (int(f2.getlength(sub)) + 60, 60), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((30, 8), sub, font=f2, fill=CORES["champanhe"])
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
    ouro = bgr(CORES["champanhe"])
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
        ImageDraw.Draw(im).text((10, 0), "001", font=fs, fill=CORES["champanhe"])
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
        cache["lp"] = np.array(Image.open(arquivo_marca(CFG["logo"])).convert("RGBA"))
        cache["tracos"] = _traco_logo()
    f = fundo.base.copy()
    cx, cy, r = W // 2, int(H * 0.40), int(W * 0.36)
    ch = bgr(CORES["champanhe"])
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
                                     fill=CORES["champanhe"] + (int(255 * (p - 0.6) / 0.4),), anchor="mm")
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
        cv2.circle(dot, (int(346 * esc), int(372 * esc)), int(26 * esc * pd), CORES["champanhe"] + (255,), -1, cv2.LINE_AA)
        blend(f, dot, cx - lado / 2, cy - lado / 2)
    # 3) nome e assinatura; mergulho final para dentro do símbolo
    sai = _assinatura(f, cache, W, H, t, dur)
    return _mergulho(f, sai, cx, cy, W, H)


def cartao_cta(cfg, W, H, t, fundo, cache):
    """Encerramento animado: logo da marca com mola, chamada cinética, URL (+ apoio) e, no @pontes_brain, Leo apontando."""
    f = fundo.quadro(t + 100, 1.0 + 0.02 * t)
    if "logo" not in cache:
        cache["logo"] = pil2np(logo_marca(int(W * CFG.get("cta_logo_alt", 0.16)))) if tem_logo() else None
        cache["cham"] = Cartao(cfg["chamada"], W * 0.86, "titulo", 78)
        cache["url"] = Cartao(cfg["url"], W * 0.92, "destaque", 50)
        cache["apoio"] = None
        if cfg.get("apoio"):
            fa = fonte("Bold", 40)
            im = Image.new("RGBA", (int(fa.getlength(cfg["apoio"])) + 40, 64), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((20, 6), cfg["apoio"], font=fa, fill=CORES["papel"])
            cache["apoio"] = pil2np(im)
        com_leo = cfg.get("pose_leo") and tem_leo()
        cache["leo"] = Leo({"pose": cfg["pose_leo"], "altura": 0.33, "x": 0.5, "y": 0.93, "lado": "direita"}, W, H) if com_leo else None
    lg = cache["logo"]
    if lg is not None:
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

