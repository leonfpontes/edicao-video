"""Biblioteca de layers de efeito (gerados por código, para todas as marcas).

Cada efeito é uma camada animada que entra no EDL como elemento:

    {"tipo": "efeito", "nome": "confete", "na": "conseguimos", "segura": 1.5, "x": 0.5, "y": 0.4}

Os efeitos não carregam cor própria: usam os papéis de cor da marca ativa ("champanhe", "papel",
"bronze"…). Um mesmo efeito sai dourado no @pontes_brain, ouro-terra no GiraHub e âmbar no @leopontesrp,
e nunca pode trazer a cor de outra marca. Tudo é determinístico (mesma entrada, mesmo quadro), o que
permite o teste de regressão.

Fases: "elementos" desenha junto dos títulos (sob a legenda); "pos" age no quadro inteiro, por último.
"""
import math

import cv2
import numpy as np

from .config import FPS
from .graficos import Cartao, blend, fonte, transformar
from .marca import CORES, PAPEIS_COR, ErroDeMarca
from .movimento import clamp01, ease_in, ease_in_out, ease_out, mola

REGISTRO = {}


def efeito(nome, categoria, descricao, params=None, fase="elementos", pop=False):
    """Registra uma classe de efeito na biblioteca."""
    def reg(cls):
        cls.nome, cls.categoria, cls.descricao = nome, categoria, descricao
        cls.params, cls.fase, cls.pop = params or {}, fase, pop
        REGISTRO[nome] = cls
        return cls
    return reg


def criar_efeito(e, W, H, semente=0):
    nome = e.get("nome")
    if nome not in REGISTRO:
        raise ErroDeMarca(f"efeito desconhecido: {nome} (veja `editor.py biblioteca listar efeitos`)")
    return REGISTRO[nome](e, W, H, semente)


def catalogo_efeitos():
    return [{"id": n, "categoria": c.categoria, "descricao": c.descricao, "fase": c.fase, "som_pop": c.pop,
             "params": c.params} for n, c in sorted(REGISTRO.items())]


def cor_marca(nome):
    """Cor de um papel da paleta da marca ativa (RGB). Hex solto não é aceito: protege a identidade."""
    if nome not in PAPEIS_COR:
        raise ErroDeMarca(f"cor de efeito precisa ser um papel da paleta ({', '.join(PAPEIS_COR)}), não {nome!r}")
    return CORES[nome]


def _bgr(rgb):
    return (int(rgb[2]), int(rgb[1]), int(rgb[0]))


def _somar(frame, camada_bgr, alpha=1.0):
    """Mistura aditiva (luz): camada float32 BGR 0..255 do tamanho do quadro."""
    if alpha <= 0.003:
        return
    frame[:] = np.clip(frame.astype(np.float32) + camada_bgr * alpha, 0, 255).astype(np.uint8)


def _tela(frame, camada_bgr, alpha=1.0):
    """Mistura 'tela' (screen): clareia sem estourar como a soma."""
    if alpha <= 0.003:
        return
    f = frame.astype(np.float32)
    c = camada_bgr * alpha
    frame[:] = (255 - (255 - f) * (255 - c) / 255).clip(0, 255).astype(np.uint8)


class Efeito:
    def __init__(self, e, W, H, semente=0):
        self.e, self.W, self.H = e, W, H
        self.semente = int(semente) * 7919 + sum(map(ord, self.nome))
        self.rng = np.random.default_rng(self.semente)
        self.x, self.y = W * e.get("x", 0.5), H * e.get("y", 0.5)
        self.cor = cor_marca(e.get("cor", "champanhe"))
        self.cor2 = cor_marca(e.get("cor2", "papel_2"))
        self.forca = float(e.get("intensidade", 1.0))
        self.preparar()

    def preparar(self):
        pass

    def presenca(self, dt, rest, ent=0.2, sai=0.25):
        return clamp01(dt / ent) * clamp01(rest / sai) if ent and sai else 1.0

    def rng_quadro(self, dt):
        return np.random.default_rng(self.semente + int(round(dt * FPS)))

    def desenhar(self, frame, dt, rest):
        raise NotImplementedError


# ───────────────────────────── luz e textura (quadro inteiro) ─────────────────────────────

@efeito("vazamento_luz", "luz", "Vazamento de luz quente que atravessa a tela, como em filme. Bom em abertura e virada de assunto.",
        {"intensidade": "0 a 1 (padrão 1)", "direcao": "esquerda|direita (padrão direita)"}, fase="pos")
class VazamentoLuz(Efeito):
    def preparar(self):
        w, h = self.W // 6, self.H // 6
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.w, self.h, self.xx, self.yy = w, h, xx, yy

    def desenhar(self, frame, dt, rest):
        dur = dt + rest
        p = ease_in_out(dt / max(dur, 0.01))
        sentido = -1 if self.e.get("direcao") == "esquerda" else 1
        cx = self.w * (0.5 + sentido * (-0.9 + 1.8 * p))
        cy = self.h * (0.35 + 0.1 * math.sin(dt * 1.3))
        d1 = ((self.xx - cx) / (self.w * 0.55)) ** 2 + ((self.yy - cy) / (self.h * 0.45)) ** 2
        d2 = ((self.xx - cx * 0.8 - self.w * 0.1) / (self.w * 0.3)) ** 2 + ((self.yy - cy * 1.4) / (self.h * 0.3)) ** 2
        a1, a2 = np.exp(-d1 * 1.6), np.exp(-d2 * 2.2)
        c1, c2 = np.array(_bgr(self.cor), np.float32), np.array(_bgr(cor_marca("bronze")), np.float32)
        cam = a1[..., None] * c1 + a2[..., None] * c2 * 0.8
        cam = cv2.resize(cam, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        _tela(frame, cam, 0.85 * self.forca * self.presenca(dt, rest, 0.3, 0.4))


@efeito("grao", "textura", "Grão de filme sutil no quadro inteiro. Dá textura de cinema a vídeos muito 'limpos'.",
        {"intensidade": "0 a 1 (padrão 1 = grão leve)"}, fase="pos")
class Grao(Efeito):
    def preparar(self):
        self.telhas = [self.rng.normal(0, 1, (self.H // 2, self.W // 2)).astype(np.float32) for _ in range(6)]

    def desenhar(self, frame, dt, rest):
        n = self.telhas[int(dt * FPS) % len(self.telhas)]
        n = cv2.resize(n, (self.W, self.H), interpolation=cv2.INTER_NEAREST)
        amp = 9 * self.forca * self.presenca(dt, rest, 0.3, 0.3)
        frame[:] = np.clip(frame.astype(np.float32) + n[..., None] * amp, 0, 255).astype(np.uint8)


@efeito("vinheta", "textura", "Escurece as bordas e leva o olhar para o centro. Use em fala emotiva ou dramática.",
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos")
class Vinheta(Efeito):
    def preparar(self):
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        r = np.sqrt(((xx - self.W / 2) / (self.W * 0.62)) ** 2 + ((yy - self.H * 0.42) / (self.H * 0.62)) ** 2)
        self.mask = np.clip((r - 0.45) / 0.65, 0, 1) ** 1.6

    def desenhar(self, frame, dt, rest):
        k = 0.55 * self.forca * self.presenca(dt, rest, 0.5, 0.5)
        frame[:] = (frame.astype(np.float32) * (1 - k * self.mask[..., None])).astype(np.uint8)


@efeito("vhs", "textura", "Estética VHS: linhas de varredura, cor deslocada e uma faixa de ruído. Para memória, nostalgia, 'antigamente'.",
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos")
class VHS(Efeito):
    def preparar(self):
        linhas = np.ones((self.H, 1), np.float32)
        linhas[::4] = 0.86
        self.linhas = linhas

    def desenhar(self, frame, dt, rest):
        a = self.forca * self.presenca(dt, rest, 0.15, 0.2)
        if a <= 0.01:
            return
        f = frame.astype(np.float32)
        d = int(4 * a)
        if d:
            f[:, d:, 2] = f[:, :-d, 2]
            f[:, :-d, 0] = f[:, d:, 0]
        cinza = f.mean(2, keepdims=True)
        f = f * (1 - 0.25 * a) + cinza * 0.25 * a
        f *= 1 - (1 - self.linhas[..., None]) * a
        y0 = int((dt * 0.35 % 1) * self.H)
        faixa = slice(y0, min(self.H, y0 + int(self.H * 0.025)))
        r = self.rng_quadro(dt)
        f[faixa] += r.normal(0, 28 * a, f[faixa].shape[:2])[..., None]
        frame[:] = np.clip(f, 0, 255).astype(np.uint8)


@efeito("glitch", "impacto", "Falha digital rápida (canais de cor separados e fatias deslocadas). Para virada, erro, 'bug' no processo.",
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos", pop=True)
class Glitch(Efeito):
    def desenhar(self, frame, dt, rest):
        r = self.rng_quadro(dt)
        ativo = r.random() < 0.75 or dt < 0.12
        if not ativo:
            return
        a = self.forca * (1 - 0.5 * ease_in(dt / max(dt + rest, 0.01)))
        d = int(r.integers(6, 22) * a)
        src = frame.copy()
        if d:
            frame[:, d:, 2] = src[:, :-d, 2]
            frame[:, :-d, 0] = src[:, d:, 0]
        for _ in range(int(r.integers(3, 8))):
            y = int(r.integers(0, self.H - 40))
            h = int(r.integers(8, max(9, int(self.H * 0.05))))
            off = int(r.integers(-60, 60) * a)
            frame[y:y + h] = np.roll(frame[y:y + h], off, axis=1)


@efeito("flash", "impacto", "Clarão rápido na cor clara da marca, no instante de uma palavra forte.",
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos", pop=True)
class Flash(Efeito):
    def desenhar(self, frame, dt, rest):
        a = (ease_out(dt / 0.06) if dt < 0.06 else 1 - ease_out((dt - 0.06) / max(dt + rest - 0.06, 0.1)))
        a *= 0.85 * self.forca
        if a > 0.01:
            frame[:] = cv2.addWeighted(frame, 1 - a, np.full_like(frame, _bgr(self.cor2)), a, 0)


@efeito("tremor", "impacto", "Câmera treme e assenta (impacto, susto, revelação). Curto: 0,3 a 0,6 s.",
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos")
class Tremor(Efeito):
    def desenhar(self, frame, dt, rest):
        k = math.exp(-6 * dt) * 22 * self.forca
        dx, dy = k * math.sin(dt * 63), k * 0.7 * math.cos(dt * 51)
        if abs(dx) + abs(dy) < 0.4:
            return
        M = np.float32([[1.03, 0, dx - self.W * 0.015], [0, 1.03, dy - self.H * 0.015]])
        frame[:] = cv2.warpAffine(frame, M, (self.W, self.H), borderMode=cv2.BORDER_REFLECT)


@efeito("foco", "atencao", "Escurece tudo fora de um círculo (íris que fecha sobre o ponto x,y). Para apontar um detalhe.",
        {"x": "0 a 1", "y": "0 a 1", "raio": "fração da largura (padrão 0.22)", "intensidade": "escuridão 0 a 1"}, fase="pos")
class Foco(Efeito):
    def preparar(self):
        yy, xx = np.mgrid[0:self.H // 4, 0:self.W // 4].astype(np.float32)
        self.d = np.sqrt((xx * 4 - self.x) ** 2 + (yy * 4 - self.y) ** 2)

    def desenhar(self, frame, dt, rest):
        alvo = self.W * self.e.get("raio", 0.22)
        r = lerp_(self.H * 1.1, alvo, ease_in_out(dt / 0.5))
        r = lerp_(r, self.H * 1.1, ease_in(1 - rest / 0.3) if rest < 0.3 else 0)
        m = np.clip((self.d - r) / (self.W * 0.05), 0, 1)
        m = cv2.resize(m, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        k = 0.7 * self.forca
        frame[:] = (frame.astype(np.float32) * (1 - k * m[..., None])).astype(np.uint8)


def lerp_(a, b, p):
    return a + (b - a) * p


# ───────────────────────────── partículas ─────────────────────────────

@efeito("bokeh", "luz", "Bolhas de luz desfocadas subindo devagar. Clima de sonho, conquista, fim de vídeo.",
        {"intensidade": "0 a 1", "quantidade": "número de luzes (padrão 18)"})
class Bokeh(Efeito):
    def preparar(self):
        n = int(self.e.get("quantidade", 18))
        r = self.rng
        self.p = np.stack([r.random(n), r.random(n), r.uniform(10, 34, n), r.uniform(0.02, 0.07, n),
                           r.random(n), r.uniform(0.4, 1, n)], 1)

    def desenhar(self, frame, dt, rest):
        a = 0.5 * self.forca * self.presenca(dt, rest, 0.6, 0.6)
        w, h = self.W // 3, self.H // 3
        cam = np.zeros((h, w, 3), np.float32)
        for x, y, raio, v, fase, brilho in self.p:
            yy = ((y - v * dt) % 1.1 - 0.05) * h
            xx = (x + 0.02 * math.sin(dt * 0.8 + fase * 6)) * w
            cor = self.cor if fase < 0.6 else self.cor2
            cv2.circle(cam, (int(xx), int(yy)), int(raio), tuple(float(c) * brilho for c in _bgr(cor)), -1, cv2.LINE_AA)
        cam = cv2.GaussianBlur(cam, (0, 0), 3)
        _tela(frame, cv2.resize(cam, (self.W, self.H)), a)


@efeito("brilhos", "luz", "Faíscas de quatro pontas piscando ao redor de um ponto. Para algo valioso, novo, 'mágico'.",
        {"x": "0 a 1", "y": "0 a 1", "raio": "fração da largura (padrão 0.2)", "quantidade": "padrão 9"}, pop=True)
class Brilhos(Efeito):
    def preparar(self):
        n = int(self.e.get("quantidade", 9))
        r = self.rng
        R = self.W * self.e.get("raio", 0.2)
        ang, dist = r.uniform(0, 2 * math.pi, n), r.uniform(0.25, 1, n) * R
        self.pts = np.stack([np.cos(ang) * dist, np.sin(ang) * dist, r.uniform(28, 70, n), r.uniform(0, 1.2, n)], 1)
        self.R = int(R + 60)

    def desenhar(self, frame, dt, rest):
        a = self.presenca(dt, rest, 0.05, 0.3)
        lado = self.R * 2
        cam = np.zeros((lado, lado, 3), np.float32)
        for px, py, tam, atraso in self.pts:
            t = dt - atraso * 0.5
            if t < 0:
                continue
            s = tam * (0.5 + 0.5 * math.sin(t * 7)) * clamp01(mola(t / 0.35, 6, 12))
            if s < 2:
                continue
            cx, cy = self.R + px, self.R + py
            estrela = np.array([[cx, cy - s], [cx + s * 0.18, cy - s * 0.18], [cx + s, cy], [cx + s * 0.18, cy + s * 0.18],
                                [cx, cy + s], [cx - s * 0.18, cy + s * 0.18], [cx - s, cy], [cx - s * 0.18, cy - s * 0.18]], np.int32)
            cv2.fillPoly(cam, [estrela], _bgr(self.cor2), cv2.LINE_AA)
            cv2.circle(cam, (int(cx), int(cy)), int(s * 0.5), _bgr(self.cor), -1, cv2.LINE_AA)
        brilho = cv2.GaussianBlur(cam, (0, 0), 6)
        cam = cam + brilho * 1.2
        x0, y0 = int(self.x - self.R), int(self.y - self.R)
        _somar_roi(frame, cam, x0, y0, a * self.forca)


def _somar_roi(frame, cam, x0, y0, alpha):
    h, w = cam.shape[:2]
    H, W = frame.shape[:2]
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb or alpha <= 0.003:
        return
    roi = frame[ya:yb, xa:xb].astype(np.float32)
    frame[ya:yb, xa:xb] = np.clip(roi + cam[ya - y0:yb - y0, xa - x0:xb - x0] * alpha, 0, 255).astype(np.uint8)


@efeito("confete", "celebracao", "Explosão de confete nas cores da marca, com gravidade. Para conquista, lançamento, 'deu certo'.",
        {"x": "0 a 1 (origem)", "y": "0 a 1 (origem)", "quantidade": "padrão 90"}, pop=True)
class Confete(Efeito):
    def preparar(self):
        n = int(self.e.get("quantidade", 90))
        r = self.rng
        ang = r.uniform(math.radians(-160), math.radians(-20), n)
        vel = r.uniform(0.7, 1.5, n) * self.H * 0.75
        cores = [cor_marca(c) for c in ("champanhe", "bronze", "papel", "nevoa", "papel_2")]
        self.p = [(math.cos(a) * v, math.sin(a) * v, r.uniform(24, 42), r.uniform(12, 20), r.uniform(0, 6.28),
                   r.uniform(-14, 14), _bgr(cores[i % len(cores)]), r.uniform(0.6, 1.4)) for i, (a, v) in enumerate(zip(ang, vel))]

    def desenhar(self, frame, dt, rest):
        g, arrasto = self.H * 1.3, 1.6
        a = clamp01(rest / 0.4)
        if a <= 0.01:
            return
        cam = frame.copy()
        e = math.exp(-arrasto * dt)
        for vx, vy, w, h, th0, om, cor, osc in self.p:
            x = self.x + vx * (1 - e) / arrasto + 30 * math.sin(dt * 5 * osc)
            y = self.y + vy * (1 - e) / arrasto + g * (dt / arrasto - (1 - e) / arrasto ** 2)
            th = th0 + om * dt
            larg = w * abs(math.cos(th * 0.7)) + 2  # gira no eixo também (vira de lado)
            caixa = cv2.boxPoints(((x, y), (larg, h), math.degrees(th)))
            cv2.fillPoly(cam, [np.int32(caixa)], cor, cv2.LINE_AA)
        frame[:] = cv2.addWeighted(cam, a, frame, 1 - a, 0)


@efeito("ondas", "atencao", "Anéis que se expandem a partir de um ponto (pulso de atenção, notificação, 'olha aqui').",
        {"x": "0 a 1", "y": "0 a 1", "raio": "fração da largura (padrão 0.3)"})
class Ondas(Efeito):
    def desenhar(self, frame, dt, rest):
        R = self.W * self.e.get("raio", 0.3)
        ov = frame.copy()
        tocou = False
        for k in range(3):
            t = (dt - k * 0.28) % 1.1
            if dt - k * 0.28 < 0:
                continue
            p = ease_out(t / 1.1)
            cv2.circle(ov, (int(self.x), int(self.y)), int(R * p) + 4, _bgr(self.cor), max(2, int(10 * (1 - p))), cv2.LINE_AA)
            tocou = True
        if tocou:
            a = 0.8 * self.presenca(dt, rest, 0.1, 0.3) * self.forca
            frame[:] = cv2.addWeighted(ov, a, frame, 1 - a, 0)


@efeito("chuva_3d", "celebracao", "Objetos da biblioteca 3D caindo pela tela (ex.: dinheiro, corações, foguetes).",
        {"objeto": "id da biblioteca 3D (padrão estrela)", "quantidade": "padrão 12", "tamanho": "fração da largura (padrão 0.12)"})
class Chuva3D(Efeito):
    def preparar(self):
        from PIL import Image

        from .bibliotecas import objeto_3d
        from .graficos import pil2np
        caminho, _ = objeto_3d(self.e.get("objeto", "estrela"))
        im = Image.open(caminho).convert("RGBA")
        im = im.crop(im.getbbox())
        n = int(self.e.get("quantidade", 12))
        r = self.rng
        base = self.W * self.e.get("tamanho", 0.12)
        self.sprites = []
        for _ in range(n):
            lado = int(base * r.uniform(0.6, 1.25))
            self.sprites.append(pil2np(im.resize((lado, int(im.height * lado / im.width)), Image.LANCZOS)))
        self.p = np.stack([r.random(n), r.uniform(-0.9, 0, n), r.uniform(0.35, 0.6, n), r.uniform(-90, 90, n), r.uniform(-30, 30, n)], 1)

    def desenhar(self, frame, dt, rest):
        a = self.presenca(dt, rest, 0.1, 0.35)
        for spr, (x, y0, v, th0, om) in zip(self.sprites, self.p):
            y = (y0 + v * dt) * self.H
            if y > self.H + 200:
                continue
            s = transformar(spr, 1.0, th0 + om * dt)
            blend(frame, s, x * self.W - s.shape[1] / 2, y - s.shape[0] / 2, a)


# ───────────────────────────── marcações desenhadas ─────────────────────────────

def _traco(frame, pts, p, cor, esp, alpha=1.0):
    """Desenha a fração p de uma polilinha (traço com pontas redondas), com sombra suave."""
    n = int(len(pts) * clamp01(p))
    if n < 2 or alpha <= 0.01:
        return
    pts = np.int32(pts[:n])
    ov = frame.copy()
    cv2.polylines(ov, [pts + [0, 5]], False, (10, 10, 10), esp + 2, cv2.LINE_AA)
    frame[:] = cv2.addWeighted(ov, 0.25 * alpha, frame, 1 - 0.25 * alpha, 0)
    ov = frame.copy()
    cv2.polylines(ov, [pts], False, cor, esp, cv2.LINE_AA)
    for x, y in (pts[0], pts[-1]):
        cv2.circle(ov, (int(x), int(y)), esp // 2, cor, -1, cv2.LINE_AA)
    frame[:] = cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0)


@efeito("circulo", "marcacao", "Círculo feito 'à mão' em volta de um ponto (marca-texto de vídeo).",
        {"x": "0 a 1", "y": "0 a 1", "largura": "fração da largura (padrão 0.4)", "altura": "fração da largura (padrão 0.18)"})
class Circulo(Efeito):
    def preparar(self):
        rx, ry = self.W * self.e.get("largura", 0.4) / 2, self.W * self.e.get("altura", 0.18) / 2
        r = self.rng
        ts = np.linspace(0, 2 * math.pi * 1.12, 140)
        trem = 1 + 0.035 * np.sin(ts * 3 + r.uniform(0, 6)) + 0.02 * np.sin(ts * 7)
        a0 = math.radians(-160)
        self.pts = np.stack([self.x + rx * trem * np.cos(ts + a0) * (1 + 0.04 * ts / 6),
                             self.y + ry * trem * np.sin(ts + a0) * (1 + 0.06 * ts / 6)], 1)

    def desenhar(self, frame, dt, rest):
        _traco(frame, self.pts, ease_out(dt / 0.5), _bgr(self.cor), int(self.W * 0.011), clamp01(rest / 0.25))


@efeito("sublinhado", "marcacao", "Sublinhado ondulado desenhado da esquerda para a direita, sob uma palavra ou número.",
        {"x": "centro 0 a 1", "y": "0 a 1", "largura": "fração da largura (padrão 0.5)"})
class Sublinhado(Efeito):
    def preparar(self):
        L = self.W * self.e.get("largura", 0.5)
        xs = np.linspace(-L / 2, L / 2, 90)
        self.pts = np.stack([self.x + xs, self.y + 7 * np.sin(xs / L * 9) - xs * 0.04], 1)

    def desenhar(self, frame, dt, rest):
        _traco(frame, self.pts, ease_out(dt / 0.4), _bgr(self.cor), int(self.W * 0.012), clamp01(rest / 0.25))


@efeito("seta", "marcacao", "Seta curva que se desenha e aponta para (x, y). Para indicar um detalhe da tela ou do b-roll.",
        {"x": "ponta 0 a 1", "y": "ponta 0 a 1", "de": "esquerda|direita|cima|baixo (padrão esquerda)", "comprimento": "fração da largura (padrão 0.3)"})
class Seta(Efeito):
    def preparar(self):
        L = self.W * self.e.get("comprimento", 0.3)
        dx, dy = {"esquerda": (-1, 0.35), "direita": (1, 0.35), "cima": (0.35, -1), "baixo": (0.35, 1)}[self.e.get("de", "esquerda")]
        ini = np.array([self.x + dx * L, self.y + dy * L])
        fim = np.array([self.x, self.y])
        meio = (ini + fim) / 2 + np.array([-dy, dx]) * L * 0.35
        t = np.linspace(0, 1, 80)[:, None]
        self.pts = (1 - t) ** 2 * ini + 2 * (1 - t) * t * meio + t ** 2 * fim
        d = self.pts[-1] - self.pts[-6]
        self.ang = math.atan2(d[1], d[0])

    def desenhar(self, frame, dt, rest):
        a = clamp01(rest / 0.25)
        cor, esp = _bgr(self.cor), int(self.W * 0.012)
        bob = 6 * math.sin(dt * 6) * clamp01((dt - 0.5) / 0.2)
        pts = self.pts + np.array([math.cos(self.ang), math.sin(self.ang)]) * bob
        _traco(frame, pts, ease_out(dt / 0.45), cor, esp, a)
        pc = clamp01(mola((dt - 0.38) / 0.3, 7, 12))
        if pc > 0.02:
            tam = self.W * 0.045 * pc
            px, py = pts[-1]
            asas = [(px - tam * math.cos(self.ang - s), py - tam * math.sin(self.ang - s)) for s in (0.55, -0.55)]
            _traco(frame, np.array([asas[0], (px, py), asas[1]]), 1.0, cor, esp, a)


class _Selo(Efeito):
    """Base do check e do xis: disco na cor de destaque com mola e o símbolo traçado por cima."""
    def preparar(self):
        self.R = self.W * self.e.get("tamanho", 0.12) / 2

    def simbolo(self):
        raise NotImplementedError

    def desenhar(self, frame, dt, rest):
        sai = ease_in(1 - rest / 0.3) if rest < 0.3 else 0
        s = clamp01(mola(dt / 0.45, 6, 10)) * (1 - sai)
        if s < 0.02:
            return
        ov = frame.copy()
        cv2.circle(ov, (int(self.x), int(self.y + 8)), int(self.R * s), (12, 12, 12), -1, cv2.LINE_AA)
        frame[:] = cv2.addWeighted(ov, 0.25, frame, 0.75, 0)
        cv2.circle(frame, (int(self.x), int(self.y)), int(self.R * s), _bgr(self.cor), -1, cv2.LINE_AA)
        for tr in self.simbolo():
            pts = np.array([(self.x + px * self.R * s, self.y + py * self.R * s) for px, py in tr])
            dens = np.concatenate([np.linspace(pts[i], pts[i + 1], 20) for i in range(len(pts) - 1)])
            _traco(frame, dens, ease_out((dt - 0.2) / 0.35), _bgr(cor_marca("marinho")), int(self.R * 0.18), 1 - sai)


@efeito("check", "marcacao", "Selo de 'certo' (disco com mola e check traçado). Para acerto, aprovado, 'faça assim'.",
        {"x": "0 a 1", "y": "0 a 1", "tamanho": "diâmetro em fração da largura (padrão 0.12)"}, pop=True)
class Check(_Selo):
    def simbolo(self):
        return [[(-0.45, 0.02), (-0.12, 0.34), (0.48, -0.32)]]


@efeito("xis", "marcacao", "Selo de 'errado' (disco com mola e X traçado). Para erro comum, mito, 'não faça'.",
        {"x": "0 a 1", "y": "0 a 1", "tamanho": "diâmetro em fração da largura (padrão 0.12)"}, pop=True)
class Xis(_Selo):
    def simbolo(self):
        return [[(-0.36, -0.36), (0.36, 0.36)], [(0.36, -0.36), (-0.36, 0.36)]]


# ───────────────────────────── informação ─────────────────────────────

def _numero(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


@efeito("contador", "informacao", "Número que conta até o valor falado (ex.: 0 → 87%), num cartão da marca.",
        {"de": "número inicial (padrão 0)", "ate": "número final", "prefixo": "ex.: R$ ", "sufixo": "ex.: %",
         "casas": "casas decimais (padrão 0)", "duracao_contagem": "segundos (padrão 1.2)", "y": "0 a 1 (padrão 0.3)"}, pop=True)
class Contador(Efeito):
    def preparar(self):
        self.y = self.H * self.e.get("y", 0.3)
        self.cache = {}

    def desenhar(self, frame, dt, rest):
        p = ease_out(dt / self.e.get("duracao_contagem", 1.2))
        v = lerp_(float(self.e.get("de", 0)), float(self.e["ate"]), p)
        txt = f"{self.e.get('prefixo', '')}{_numero(v, int(self.e.get('casas', 0)))}{self.e.get('sufixo', '')}"
        if txt not in self.cache:
            self.cache = {txt: Cartao(txt, self.W * 0.8, "titulo", int(self.e.get("tam", 130)))}
        img = self.cache[txt].render(10, rest)  # caixa já aberta; a entrada é a mola abaixo
        s = clamp01(mola(dt / 0.5, 6, 10))
        img = transformar(img, max(0.05, 0.6 + 0.4 * s))
        blend(frame, img, self.W * self.e.get("x", 0.5) - img.shape[1] / 2, self.y - img.shape[0] / 2, clamp01(dt / 0.1))


@efeito("moldura_rec", "informacao", "Moldura de câmera gravando (cantos, ponto pulsando e cronômetro). Para bastidores e vlog.",
        {"rotulo": "texto ao lado do ponto (padrão REC)"})
class MolduraRec(Efeito):
    def preparar(self):
        self.f = fonte("Bold", int(self.W * 0.035))

    def desenhar(self, frame, dt, rest):
        from PIL import Image, ImageDraw
        a = self.presenca(dt, rest, 0.3, 0.3)
        if a <= 0.01:
            return
        m, L, esp = int(self.W * 0.06), int(self.W * 0.09), max(3, int(self.W * 0.005))
        cor = _bgr(self.cor2)
        ov = frame.copy()
        for cx, cy, sx, sy in ((m, m * 2, 1, 1), (self.W - m, m * 2, -1, 1), (m, self.H - m * 2, 1, -1), (self.W - m, self.H - m * 2, -1, -1)):
            cv2.line(ov, (cx, cy), (cx + sx * L, cy), cor, esp, cv2.LINE_AA)
            cv2.line(ov, (cx, cy), (cx, cy + sy * L), cor, esp, cv2.LINE_AA)
        if math.sin(dt * 6) > -0.2:
            cv2.circle(ov, (m + int(self.W * 0.03), m * 2 + int(self.W * 0.06)), int(self.W * 0.014), _bgr(self.cor), -1, cv2.LINE_AA)
        frame[:] = cv2.addWeighted(ov, a, frame, 1 - a, 0)
        txt = f"{self.e.get('rotulo', 'REC')}  {int(dt) // 60:02d}:{int(dt) % 60:02d}"
        im = Image.new("RGBA", (int(self.f.getlength(txt)) + 20, int(self.f.size * 1.4)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((4, 0), txt, font=self.f, fill=tuple(self.cor2))
        blend(frame, np.array(im), m + int(self.W * 0.06), m * 2 + int(self.W * 0.06) - self.f.size * 0.7, a)


# ───────────────────────────── prévia (galeria e exportação) ─────────────────────────────

EXEMPLOS = {
    "contador": {"ate": 87, "sufixo": "%"},
    "seta": {"x": 0.62, "y": 0.42},
    "circulo": {"y": 0.42},
    "sublinhado": {"y": 0.5},
    "foco": {"y": 0.38},
    "chuva_3d": {"objeto": "estrela"},
}


def quadro_exemplo(nome, W, H, t, fundo, dur=2.0):
    """Um quadro do efeito sobre o fundo da marca ativa (galeria do README e `biblioteca previa`)."""
    e = dict({"tipo": "efeito", "nome": nome, "x": 0.5, "y": 0.4}, **EXEMPLOS.get(nome, {}))
    ef = criar_efeito(e, W, H, 0)
    f = fundo.quadro(t)
    ef.desenhar(f, t, dur - t)
    return f
