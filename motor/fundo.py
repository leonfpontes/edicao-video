"""Fundo da marca: cor escura com luz ambiente difusa e o motivo da marca em traço fino."""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .graficos import cobrir, fonte
from .marca import CFG, CORES
from .movimento import clamp01, mola
from .util import bgr


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
        base = np.array(CORES["marinho"] if escuro else CORES["papel"], np.float32)[::-1]
        self.traco = bgr(CORES["champanhe"] if escuro else CORES["marinho"])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w * 0.5, h * 0.36
        r = np.sqrt(((xx - cx) / (w * 0.75)) ** 2 + ((yy - cy) / (h * 0.55)) ** 2)
        luz = np.clip(1 - r, 0, 1) ** 1.6
        fator = (0.62 + 0.75 * luz) if escuro else (0.90 + 0.12 * luz)
        img = (base[None, None, :] * fator[..., None]).clip(0, 255).astype(np.uint8)
        self.cx, self.cy, self.r = int(w * 0.5), int(h * 0.40), int(min(w, h) * 0.44)
        self.motivo = CFG["fundo_motivo"]
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

