"""Enquadramento: rosto suavizado, câmera contínua entre cortes, zooms de ênfase e transições."""
import math

import cv2
import numpy as np

from .graficos import cobrir
from .marca import CORES
from .movimento import ease_in, ease_in_out, ease_out
from .util import bgr


class Rosto:
    def __init__(self, r):
        a = np.array(r["amostras"], np.float64)
        self.t, self.x, self.y, self.h = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
        k = 5  # suaviza ~2,5 s para o enquadramento não "nadar"
        ker = np.ones(k) / k
        pad = lambda v: np.convolve(np.pad(v, k // 2, mode="edge"), ker, "valid") if len(v) > k else v
        # com vários clipes, cada um é suavizado sozinho (a posição de um não vaza para o outro)
        cortes = np.searchsorted(self.t, r.get("clipes_ini", [0.0])[1:])
        for v in (self.x, self.y, self.h):
            for p in np.split(np.arange(len(v)), cortes):
                v[p] = pad(v[p])

    def em(self, t):
        return (float(np.interp(t, self.t, self.x)), float(np.interp(t, self.t, self.y)), float(np.interp(t, self.t, self.h)))


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
    if tipo in ("dissolve", "fade"):  # fusão suave: troca de cena ou de momento no vídeo do dia a dia
        return cv2.addWeighted(a, 1 - ease_in_out(p), b, ease_in_out(p), 0)
    if tipo == "flash":
        base = a if p < 0.5 else b
        lum = 1 - abs(p - 0.5) * 2
        return cv2.addWeighted(base, 1 - 0.9 * lum, np.full_like(base, bgr(CORES["papel_2"])), 0.9 * lum, 0)
    return b

