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
    if tipo == "giro":
        return _giro(a, b, p, W, H)
    if tipo == "rasgo":
        return _rasgo(a, b, p, W, H)
    if tipo == "vidro":
        return _vidro(a, b, p, W, H)
    if tipo == "luz":
        return _luz(a, b, p, W, H)
    return b


def _giro(a, b, p, W, H):
    """Giro 3D no eixo vertical: o quadro antigo vira de lado e o novo chega girando, com borrão de movimento."""
    e = ease_in_out(p)
    graus = 90 * e / 0.5 if e < 0.5 else -90 * (1 - e) / 0.5
    f = a if e < 0.5 else b
    th = math.radians(graus)
    foco = W * 1.6
    esc = 1 - 0.12 * math.sin(math.pi * p)
    pts = []
    for x, y in ((-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)):
        X, Z = x * math.cos(th) * esc, x * math.sin(th)
        k = foco / (foco + Z)
        pts.append([W / 2 + X * k, H / 2 + y * esc * k])
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [W, 0], [W, H], [0, H]]), np.float32(pts))
    out = cv2.warpPerspective(f, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=bgr(CORES["marinho"]))
    return borrao_h(out, 4 + 70 * math.sin(math.pi * p))


_BORDA_RASGO = {}


def _rasgo(a, b, p, W, H):
    """Papel rasgado: uma borda irregular atravessa a tela e revela o quadro novo, com a fibra do papel aparecendo
    no rasgo e uma sombra curta sobre o quadro novo (estética de colagem)."""
    if H not in _BORDA_RASGO:
        r = np.random.default_rng(42)  # sempre o mesmo rasgo: o render é determinístico
        ys = np.arange(H, dtype=np.float32)
        jag = np.zeros(H, np.float32)
        for amp, per in ((W * 0.035, H / 3.1), (W * 0.018, H / 9.3), (W * 0.008, H / 31.0)):
            jag += amp * np.sin(ys / per * 2 * np.pi + r.uniform(0, 6.28))
        jag += np.repeat(r.normal(0, W * 0.005, H // 6 + 1), 6)[:H]
        fibra = np.abs(np.repeat(r.normal(0, 1, H // 3 + 1), 3)[:H]) * W * 0.008 + W * 0.009
        _BORDA_RASGO[H] = (jag, fibra)
    jag, fibra = _BORDA_RASGO[H]
    e = ease_in_out(p)
    ys = np.arange(H, dtype=np.float32)
    borda = (-0.25 + 1.5 * e) * W + jag + (ys / H - 0.5) * W * 0.22
    xs = np.arange(W, dtype=np.float32)[None, :]
    lado_novo = xs < borda[:, None]
    desl = int(W * 0.06 * e)  # o papel antigo é puxado para a direita enquanto rasga
    a2 = np.empty_like(a)
    a2[:, desl:] = a[:, :W - desl] if desl else a
    if desl:
        a2[:, :desl] = a[:, :1]
    out = np.where(lado_novo[..., None], b, a2)
    dist = borda[:, None] - xs
    sombra = np.clip(1 - dist / (W * 0.05), 0, 1) * (dist > 0)
    out = (out.astype(np.float32) * (1 - 0.35 * sombra[..., None])).astype(np.uint8)
    faixa = (dist <= 0) & (dist > -fibra[:, None])
    out[faixa] = bgr(CORES["papel_2"])
    return out


def _vidro(a, b, p, W, H):
    """Vidro líquido: o quadro passa por trás de um vidro fosco que distorce, desfoca e brilha, e o novo surge nítido."""
    q = math.sin(math.pi * p)
    mix = cv2.addWeighted(a, 1 - ease_in_out(p), b, ease_in_out(p), 0)
    if q < 0.02:
        return mix
    w2, h2 = W // 4, H // 4
    yy, xx = np.mgrid[0:h2, 0:w2].astype(np.float32)
    amp = 22 * q
    dx = amp * np.sin(yy / h2 * 9 + p * 6) + amp * 0.5 * np.sin((xx + yy) / w2 * 7)
    dy = amp * np.cos(xx / w2 * 8 - p * 5)
    mapa_x = cv2.resize(xx * 4 + dx, (W, H))
    mapa_y = cv2.resize(yy * 4 + dy, (W, H))
    out = cv2.remap(mix, mapa_x, mapa_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    k = int(1 + 36 * q) | 1
    out = cv2.GaussianBlur(out, (k, k), 0)
    banda = ((xx / w2 + yy / h2 * 0.6) - (-0.4 + 2.0 * p)) / 0.12
    reflexo = np.exp(-banda ** 2) * 0.45 * q
    reflexo = cv2.resize(reflexo, (W, H))[..., None]
    claro = np.array(bgr(CORES["papel_2"]), np.float32)
    out = out.astype(np.float32)
    out = out * (1 - reflexo) + claro * reflexo
    return np.clip(out * (1 + 0.06 * q), 0, 255).astype(np.uint8)


def _luz(a, b, p, W, H):
    """Queima de luz: o quadro estoura numa luz quente da marca (como filme superexposto) e o novo emerge dela."""
    base = a if p < 0.5 else b
    q = 1 - abs(p - 0.5) * 2
    q = ease_in(q) if p < 0.5 else ease_out(q)
    w2, h2 = W // 6, H // 6
    yy, xx = np.mgrid[0:h2, 0:w2].astype(np.float32)
    cx = w2 * (0.25 + 0.5 * p)
    g = np.exp(-(((xx - cx) / (w2 * 0.7)) ** 2 + ((yy - h2 * 0.4) / (h2 * 0.55)) ** 2))
    g = cv2.resize(g, (W, H))[..., None]
    quente = np.array(bgr(CORES["champanhe"]), np.float32)
    claro = np.array(bgr(CORES["papel_2"]), np.float32)
    cam = (quente * g + claro * (1 - g) * 0.6) * q
    f = cobrir(base, W, H, 1 + 0.05 * q).astype(np.float32)
    out = 255 - (255 - f) * (255 - cam * 1.1) / 255
    return np.clip(out, 0, 255).astype(np.uint8)

