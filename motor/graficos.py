"""Primitivas gráficas: colagem com alfa, sombra, giro 3D, quebra de texto e o cartão cinético."""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import FONTES_DIR
from .marca import CORES, FONTES
from .movimento import clamp01, ease_in, ease_in_out, ease_out, ease_out_back, mola


def fonte(peso, tam, papel="texto"):
    """papel 'titulo' (cartões, nome da vinheta) ou 'texto' (legendas, rótulos), conforme a marca."""
    arq = FONTES.get(papel, {}).get(peso) or f"Roboto-{peso}.ttf"
    return ImageFont.truetype(str(FONTES_DIR / arq), tam)


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
        self.cor_caixa = CORES["marinho"] if tit else CORES["champanhe"]
        self.cor_txt = (255, 255, 255) if tit else CORES["marinho"]
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
                d.rounded_rectangle([self.padx - 2, cy - hb / 2, self.padx + 6, cy + hb / 2], 3, fill=CORES["champanhe"] + (255,))
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


def cobrir(f, W, H, z=1.0, cx=0.5, cy=0.5, flags=cv2.INTER_LINEAR):
    h, w = f.shape[:2]
    s = max(W / w, H / h) * z
    M = np.float32([[s, 0, W / 2 - cx * w * s], [0, s, H / 2 - cy * h * s]])
    return cv2.warpAffine(f, M, (W, H), flags=flags, borderMode=cv2.BORDER_REFLECT)

