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


def efeito(nome, categoria, descricao, params=None, fase="elementos", pop=False, som=None):
    """Registra uma classe de efeito na biblioteca. pop: ganha o "pop" sintético nas marcas sem biblioteca de
    sons; som: id do som padrão (biblioteca/sons/) nas marcas com "sons": {"modo": "biblioteca"}."""
    def reg(cls):
        cls.nome, cls.categoria, cls.descricao = nome, categoria, descricao
        cls.params, cls.fase, cls.pop, cls.som = params or {}, fase, pop, som
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
             "som": c.som, "params": c.params} for n, c in sorted(REGISTRO.items())]


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
        {"intensidade": "0 a 1 (padrão 1)", "direcao": "esquerda|direita (padrão direita)"}, fase="pos", som="whoosh-sopro")
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
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos", pop=True, som="glitch")
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
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos", pop=True, som="reverso")
class Flash(Efeito):
    def desenhar(self, frame, dt, rest):
        a = (ease_out(dt / 0.06) if dt < 0.06 else 1 - ease_out((dt - 0.06) / max(dt + rest - 0.06, 0.1)))
        a *= 0.85 * self.forca
        if a > 0.01:
            frame[:] = cv2.addWeighted(frame, 1 - a, np.full_like(frame, _bgr(self.cor2)), a, 0)


@efeito("tremor", "impacto", "Câmera treme e assenta (impacto, susto, revelação). Curto: 0,3 a 0,6 s.",
        {"intensidade": "0 a 1 (padrão 1)"}, fase="pos", som="impacto-grave")
class Tremor(Efeito):
    def desenhar(self, frame, dt, rest):
        k = math.exp(-6 * dt) * 22 * self.forca
        dx, dy = k * math.sin(dt * 63), k * 0.7 * math.cos(dt * 51)
        if abs(dx) + abs(dy) < 0.4:
            return
        M = np.float32([[1.03, 0, dx - self.W * 0.015], [0, 1.03, dy - self.H * 0.015]])
        frame[:] = cv2.warpAffine(frame, M, (self.W, self.H), borderMode=cv2.BORDER_REFLECT)


@efeito("foco", "atencao", "Escurece tudo fora de um círculo (íris que fecha sobre o ponto x,y). Para apontar um detalhe.",
        {"x": "0 a 1", "y": "0 a 1", "raio": "fração da largura (padrão 0.22)", "intensidade": "escuridão 0 a 1"}, fase="pos", som="whoosh-lento")
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
        {"x": "0 a 1", "y": "0 a 1", "raio": "fração da largura (padrão 0.2)", "quantidade": "padrão 9"}, pop=True, som="brilho")
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
        {"x": "0 a 1 (origem)", "y": "0 a 1 (origem)", "quantidade": "padrão 90"}, pop=True, som="pop-bolha")
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
        {"x": "0 a 1", "y": "0 a 1", "raio": "fração da largura (padrão 0.3)"}, som="notificacao")
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
        {"objeto": "id da biblioteca 3D (padrão estrela)", "quantidade": "padrão 12", "tamanho": "fração da largura (padrão 0.12)"}, som="pop-bolha")
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
        {"x": "0 a 1", "y": "0 a 1", "largura": "fração da largura (padrão 0.4)", "altura": "fração da largura (padrão 0.18)"}, som="lapis")
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
        {"x": "centro 0 a 1", "y": "0 a 1", "largura": "fração da largura (padrão 0.5)"}, som="lapis")
class Sublinhado(Efeito):
    def preparar(self):
        L = self.W * self.e.get("largura", 0.5)
        xs = np.linspace(-L / 2, L / 2, 90)
        self.pts = np.stack([self.x + xs, self.y + 7 * np.sin(xs / L * 9) - xs * 0.04], 1)

    def desenhar(self, frame, dt, rest):
        _traco(frame, self.pts, ease_out(dt / 0.4), _bgr(self.cor), int(self.W * 0.012), clamp01(rest / 0.25))


@efeito("seta", "marcacao", "Seta curva que se desenha e aponta para (x, y). Para indicar um detalhe da tela ou do b-roll.",
        {"x": "ponta 0 a 1", "y": "ponta 0 a 1", "de": "esquerda|direita|cima|baixo (padrão esquerda)", "comprimento": "fração da largura (padrão 0.3)"},
        som="lapis")
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
        {"x": "0 a 1", "y": "0 a 1", "tamanho": "diâmetro em fração da largura (padrão 0.12)"}, pop=True, som="acerto")
class Check(_Selo):
    def simbolo(self):
        return [[(-0.45, 0.02), (-0.12, 0.34), (0.48, -0.32)]]


@efeito("xis", "marcacao", "Selo de 'errado' (disco com mola e X traçado). Para erro comum, mito, 'não faça'.",
        {"x": "0 a 1", "y": "0 a 1", "tamanho": "diâmetro em fração da largura (padrão 0.12)"}, pop=True, som="erro")
class Xis(_Selo):
    def simbolo(self):
        return [[(-0.36, -0.36), (0.36, 0.36)], [(0.36, -0.36), (-0.36, 0.36)]]


# ───────────────────────────── informação ─────────────────────────────

def _numero(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


@efeito("contador", "informacao", "Número que conta até o valor falado (ex.: 0 → 87%), num cartão da marca.",
        {"de": "número inicial (padrão 0)", "ate": "número final", "prefixo": "ex.: R$ ", "sufixo": "ex.: %",
         "casas": "casas decimais (padrão 0)", "duracao_contagem": "segundos (padrão 1.2)", "y": "0 a 1 (padrão 0.3)"}, pop=True, som="rolagem")
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
        {"rotulo": "texto ao lado do ponto (padrão REC)"}, som="clique")
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


# ───────────────────────────── tendências 2026: vidro líquido, tipografia cinética, UI ─────────────────────────────

def _mascara_arredondada(w, h, raio):
    """Máscara 0..1 de um retângulo de cantos arredondados (desenhada em 2x para a borda ficar lisa)."""
    from PIL import Image, ImageDraw
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], raio * 2, fill=255)
    return np.asarray(m.resize((w, h), Image.LANCZOS), np.float32) / 255


def painel_vidro(frame, x0, y0, w, h, alpha=1.0, raio=None, tom="marinho", tom_alpha=0.32):
    """Painel de vidro líquido (estilo Apple): o que está atrás fica fosco e um pouco mais claro, com um véu da cor da
    marca para o texto ler em qualquer fundo, fio de luz champanhe na borda, brilho especular no topo e sombra macia."""
    H, W = frame.shape[:2]
    x0, y0, w, h = int(x0), int(y0), int(w), int(h)
    if w < 8 or h < 8 or alpha <= 0.01:
        return
    raio = raio or max(8, int(12 * W / 1080))  # cantos de 8 a 12 px (nunca pílula)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb:
        return
    m = _mascara_arredondada(w, h, raio)[ya - y0:yb - y0, xa - x0:xb - x0][..., None]
    # sombra macia embaixo do painel
    pad = int(h * 0.25)
    sy0, sy1, sx0, sx1 = max(0, ya + pad // 3), min(H, yb + pad), max(0, xa - pad // 2), min(W, xb + pad // 2)
    if sy1 > sy0 and sx1 > sx0:
        sm = np.zeros((sy1 - sy0, sx1 - sx0), np.float32)
        sm[max(0, ya + pad // 3 - sy0):yb - sy0, xa - sx0:xb - sx0] = 1
        sm = cv2.GaussianBlur(sm, (0, 0), pad / 2.5)[..., None] * 0.35 * alpha
        frame[sy0:sy1, sx0:sx1] = (frame[sy0:sy1, sx0:sx1].astype(np.float32) * (1 - sm)).astype(np.uint8)
    roi = frame[ya:yb, xa:xb].astype(np.float32)
    k = max(3, int(W * 0.028)) | 1
    fosco = cv2.GaussianBlur(cv2.resize(roi, None, fx=0.5, fy=0.5), (k, k), 0)
    fosco = cv2.resize(fosco, (xb - xa, yb - ya))
    vel = np.array(_bgr(cor_marca(tom)), np.float32)
    fosco = fosco * (1 - tom_alpha) + vel * tom_alpha
    fosco = fosco * 1.04 + 6
    # brilho especular: faixa clara no terço de cima, apagando para baixo
    gy = np.linspace(0, 1, h)[ya - y0:yb - y0, None, None]
    luz = np.clip(1 - gy / 0.45, 0, 1) ** 2 * 26
    fosco = fosco + luz
    vidro = roi * (1 - m * alpha) + fosco * m * alpha
    # fio de luz na borda: champanhe em cima, névoa embaixo
    borda = np.clip(m[..., 0] - cv2.erode(m[..., 0], np.ones((3, 3), np.uint8)), 0, 1)[..., None]
    cor_borda = np.array(_bgr(cor_marca("champanhe")), np.float32) * (1 - gy) + np.array(_bgr(cor_marca("nevoa")), np.float32) * gy
    vidro = vidro * (1 - borda * 0.85 * alpha) + cor_borda * borda * 0.85 * alpha
    frame[ya:yb, xa:xb] = np.clip(vidro, 0, 255).astype(np.uint8)


def _texto_rgba(txt, peso, tam, cor, papel="texto"):
    from PIL import Image, ImageDraw
    f = fonte(peso, tam, papel)
    x0, y0, x1, y1 = f.getbbox(txt)
    im = Image.new("RGBA", (x1 - x0 + 8, y1 - y0 + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - x0, 4 - y0), txt, font=f, fill=tuple(int(c) for c in cor) + (255,))
    return np.array(im)


def _entrada_painel(dt, rest, ent=0.45, sai=0.3):
    """Escala, deslocamento vertical e opacidade de um painel que entra com mola e sai subindo."""
    s = clamp01(mola(dt / ent, 6, 10))
    q = ease_in(1 - rest / sai) if rest < sai else 0.0
    return 0.9 + 0.1 * s, (1 - clamp01(dt / ent)) * 30 - q * 40, clamp01(dt / 0.15) * (1 - q)


@efeito("cartao_vidro", "informacao", "Cartão de vidro líquido (fosco, fio de luz, brilho) com título e linha de apoio. "
        "Para conceito, definição, gate, número com contexto.",
        {"texto": "título do cartão", "sub": "linha de apoio (opcional)", "x": "0 a 1", "y": "0 a 1 (padrão 0.24)",
         "largura": "fração da largura (padrão 0.78)"}, pop=True, som="toque-vidro")
class CartaoVidro(Efeito):
    def preparar(self):
        u = self.W / 1080
        self.y = self.H * self.e.get("y", 0.24)
        self.larg = int(self.W * self.e.get("largura", 0.78))
        self.tit = _texto_rgba(self.e.get("texto", ""), "Black", int(64 * u), cor_marca("papel_2"), "titulo")
        sub = self.e.get("sub")
        self.sub = _texto_rgba(sub, "Regular", int(38 * u), cor_marca("papel")) if sub else None
        self.pad = int(40 * u)
        self.alt = self.pad * 2 + self.tit.shape[0] + (self.sub.shape[0] + int(10 * u) if sub else 0)
        maior = max(self.tit.shape[1], self.sub.shape[1] if sub else 0) + 2 * self.pad + int(24 * u)
        self.larg = max(self.larg, min(maior, int(self.W * 0.92)))

    def desenhar(self, frame, dt, rest):
        esc, dy, a = _entrada_painel(dt, rest)
        w, h = int(self.larg * esc), int(self.alt * esc)
        x0, y0 = self.x - w / 2, self.y - h / 2 + dy
        painel_vidro(frame, x0, y0, w, h, a)
        barra = int(self.W * 0.008)
        hb = (h - 2 * self.pad * esc) * ease_out((dt - 0.15) / 0.35)
        if hb > 2:
            cv2.rectangle(frame, (int(x0 + self.pad * 0.55), int(y0 + h / 2 - hb / 2)),
                          (int(x0 + self.pad * 0.55) + barra, int(y0 + h / 2 + hb / 2)), _bgr(self.cor), -1, cv2.LINE_AA)
        tx = x0 + self.pad + barra * 2
        p = ease_out((dt - 0.12) / 0.4)
        blend(frame, self.tit, tx, y0 + self.pad * esc + (1 - p) * 18, a * p)
        if self.sub is not None:
            p2 = ease_out((dt - 0.25) / 0.4)
            blend(frame, self.sub, tx, y0 + self.pad * esc + self.tit.shape[0] + 10 + (1 - p2) * 18, a * p2)


@efeito("notificacao", "informacao", "Notificação de celular em vidro descendo do topo (mensagem de cliente, alerta, lembrete). "
        "Formato que prende o olho em 2026.",
        {"app": "nome do remetente/app (padrão Mensagem)", "texto": "texto da notificação", "y": "0 a 1 (padrão 0.15)"},
        pop=True, som="notificacao")
class Notificacao(Efeito):
    def preparar(self):
        from .marca import tem_logo
        u = self.W / 1080
        self.u = u
        self.y = self.H * self.e.get("y", 0.15)
        self.larg = int(self.W * 0.86)
        self.app = _texto_rgba(self.e.get("app", "Mensagem"), "Bold", int(34 * u), cor_marca("papel_2"))
        self.agora = _texto_rgba("agora", "Regular", int(28 * u), cor_marca("nevoa"))
        from .graficos import quebrar
        f = fonte("Regular", int(36 * u))
        linhas = quebrar(self.e.get("texto", ""), f, self.larg - int(170 * u))[:2]
        self.linhas = [_texto_rgba(li, "Regular", int(36 * u), cor_marca("papel")) for li in linhas]
        self.alt = int(56 * u) + self.app.shape[0] + sum(li.shape[0] + int(4 * u) for li in self.linhas)
        self.icone = None
        if tem_logo():
            from .graficos import pil2np
            from .marca import logo_marca
            self.icone = pil2np(logo_marca(int(56 * u)))

    def desenhar(self, frame, dt, rest):
        u = self.u
        e = clamp01(mola(dt / 0.55, 7, 11))
        q = ease_in(1 - rest / 0.35) if rest < 0.35 else 0.0
        y0 = self.y - self.alt / 2 - (1 - e) * self.H * 0.14 - q * self.H * 0.14
        a = clamp01(dt / 0.12) * (1 - q)
        x0 = self.x - self.larg / 2
        painel_vidro(frame, x0, y0, self.larg, self.alt, a, raio=int(12 * u))
        ic = int(84 * u)
        ix, iy = int(x0 + 26 * u), int(y0 + (self.alt - ic) / 2)
        cv2.rectangle(frame, (ix, iy), (ix + ic, iy + ic), _bgr(cor_marca("marinho")), -1, cv2.LINE_AA)
        cv2.rectangle(frame, (ix, iy), (ix + ic, iy + ic), _bgr(cor_marca("champanhe")), max(1, int(2 * u)), cv2.LINE_AA)
        if self.icone is not None:
            blend(frame, self.icone, ix + (ic - self.icone.shape[1]) / 2, iy + (ic - self.icone.shape[0]) / 2, a)
        tx, ty = ix + ic + int(24 * u), y0 + int(26 * u)
        blend(frame, self.app, tx, ty, a)
        blend(frame, self.agora, x0 + self.larg - self.agora.shape[1] - int(28 * u), ty + 4 * u, a)
        ty += self.app.shape[0] + int(6 * u)
        for li in self.linhas:
            blend(frame, li, tx, ty, a)
            ty += li.shape[0] + int(4 * u)


@efeito("carregando", "informacao", "Barra de progresso em vidro que enche até o valor (formato 'loading' em alta). "
        "Para status de projeto, avanço, 'quanto falta'.",
        {"rotulo": "texto acima da barra", "ate": "porcentagem final (padrão 100)", "duracao_carga": "segundos (padrão 1.6)",
         "y": "0 a 1 (padrão 0.26)"}, pop=True, som="rolagem")
class Carregando(Efeito):
    def preparar(self):
        u = self.W / 1080
        self.u = u
        self.y = self.H * self.e.get("y", 0.26)
        self.larg, self.alt = int(self.W * 0.8), int(170 * u)
        self.rot = _texto_rgba(self.e.get("rotulo", "Carregando"), "Bold", int(40 * u), cor_marca("papel_2"))
        self.cache = {}

    def desenhar(self, frame, dt, rest):
        u = self.u
        esc, dy, a = _entrada_painel(dt, rest)
        w, h = int(self.larg * esc), int(self.alt * esc)
        x0, y0 = self.x - w / 2, self.y - h / 2 + dy
        painel_vidro(frame, x0, y0, w, h, a)
        alvo = float(self.e.get("ate", 100))
        p = ease_in_out((dt - 0.25) / self.e.get("duracao_carga", 1.6))
        v = alvo * p
        pct = f"{int(round(v))}%"
        if pct not in self.cache:
            self.cache = {pct: _texto_rgba(pct, "Black", int(44 * u), cor_marca("champanhe"))}
        pad = int(34 * u)
        blend(frame, self.rot, x0 + pad, y0 + pad * 0.8, a)
        txt = self.cache[pct]
        blend(frame, txt, x0 + w - pad - txt.shape[1], y0 + pad * 0.7, a)
        bx0, bx1 = int(x0 + pad), int(x0 + w - pad)
        by0 = int(y0 + h - pad - 26 * u)
        by1 = by0 + int(26 * u)
        trilho = frame.copy()
        cv2.rectangle(trilho, (bx0, by0), (bx1, by1), _bgr(cor_marca("marinho")), -1, cv2.LINE_AA)
        cheio = int(bx0 + (bx1 - bx0) * v / 100)
        if cheio > bx0 + 2:
            cv2.rectangle(trilho, (bx0, by0), (cheio, by1), _bgr(self.cor), -1, cv2.LINE_AA)
            brilho = int(bx0 + (cheio - bx0) * ((dt * 0.9) % 1))  # reflexo correndo dentro da barra
            cv2.rectangle(trilho, (max(bx0, brilho - int(30 * u)), by0), (brilho, by1), _bgr(cor_marca("papel_2")), -1)
        frame[:] = cv2.addWeighted(trilho, 0.92 * a, frame, 1 - 0.92 * a, 0)


@efeito("checklist", "informacao", "Lista em vidro em que cada item entra e é marcado com um check, um por vez. "
        "Para passo a passo, critérios, 'o que você precisa'.",
        {"itens": "lista de textos (até 5)", "intervalo": "segundos entre itens (padrão 0.7)", "titulo": "cabeçalho (opcional)",
         "y": "0 a 1 (padrão 0.3)"}, som="tique")
class Checklist(Efeito):
    def preparar(self):
        u = self.W / 1080
        self.u = u
        itens = list(self.e.get("itens", []))[:5]
        self.txt = [_texto_rgba(t, "Bold", int(42 * u), cor_marca("papel_2")) for t in itens]
        tit = self.e.get("titulo")
        self.tit = _texto_rgba(tit, "Black", int(36 * u), cor_marca("champanhe"), "titulo") if tit else None
        self.lh = int(78 * u)
        self.pad = int(36 * u)
        self.larg = int(self.W * 0.8)
        self.alt = self.pad * 2 + self.lh * len(itens) + (self.tit.shape[0] + int(16 * u) if tit else 0)
        self.y = self.H * self.e.get("y", 0.3)
        self.passo = float(self.e.get("intervalo", 0.7))

    def batidas(self):
        """Instantes (desde a entrada) dos sons extras: um tique por item marcado."""
        return [0.35 + i * self.passo + 0.25 for i in range(len(self.txt))]

    def desenhar(self, frame, dt, rest):
        u = self.u
        esc, dy, a = _entrada_painel(dt, rest)
        w, h = int(self.larg * esc), int(self.alt * esc)
        x0, y0 = self.x - w / 2, self.y - h / 2 + dy
        painel_vidro(frame, x0, y0, w, h, a)
        y = y0 + self.pad
        if self.tit is not None:
            blend(frame, self.tit, x0 + self.pad, y, a)
            y += self.tit.shape[0] + int(16 * u)
        caixa = int(40 * u)
        for i, t in enumerate(self.txt):
            ti = dt - 0.35 - i * self.passo
            p = ease_out(ti / 0.35)
            if p <= 0:
                continue
            cx, cy = int(x0 + self.pad), int(y + (self.lh - caixa) / 2)
            cv2.rectangle(frame, (cx, cy), (cx + caixa, cy + caixa), _bgr(cor_marca("champanhe")), max(2, int(3 * u)), cv2.LINE_AA)
            pc = ease_out((ti - 0.25) / 0.25)
            if pc > 0:
                cv2.rectangle(frame, (cx, cy), (cx + caixa, cy + caixa), _bgr(cor_marca("champanhe")), -1, cv2.LINE_AA)
                pts = np.array([(cx + caixa * 0.2, cy + caixa * 0.52), (cx + caixa * 0.42, cy + caixa * 0.74),
                                (cx + caixa * 0.8, cy + caixa * 0.28)])
                dens = np.concatenate([np.linspace(pts[k], pts[k + 1], 12) for k in range(2)])
                n = int(len(dens) * pc)
                if n > 1:
                    cv2.polylines(frame, [np.int32(dens[:n])], False, _bgr(cor_marca("marinho")), max(3, int(6 * u)), cv2.LINE_AA)
            blend(frame, t, cx + caixa + int(24 * u) + (1 - p) * 30, y + (self.lh - t.shape[0]) / 2, a * p)
            y += self.lh


@efeito("tipografia", "texto", "Tipografia cinética: palavra grande com letras caindo em cascata e mola, que se abrem de leve "
        "e saem subindo. Para a palavra-chave do vídeo (gancho, conceito).",
        {"texto": "1 ou 2 palavras", "y": "0 a 1 (padrão 0.22)", "tam": "tamanho da letra (padrão 170)",
         "maiusculas": "true|false (padrão true)"}, pop=True, som="impacto-seco")
class Tipografia(Efeito):
    def preparar(self):
        from PIL import Image, ImageDraw
        u = self.W / 1080
        txt = self.e.get("texto", "")
        if self.e.get("maiusculas", True):
            txt = txt.upper()
        tam = int(self.e.get("tam", 170) * u)
        f = fonte("Black", tam, "titulo")
        while f.getlength(txt) > self.W * 0.9 and tam > 40:
            tam = int(tam * 0.92)
            f = fonte("Black", tam, "titulo")
        self.letras, x = [], 0.0
        sombra_cor = tuple(cor_marca("marinho"))
        for ch in txt:
            larg = f.getlength(ch)
            if ch.strip():
                im = Image.new("RGBA", (int(larg) + 40, int(tam * 1.5)), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                d.text((20, 10 + tam * 0.06), ch, font=f, fill=sombra_cor + (170,))
                d.text((20, 10), ch, font=f, fill=tuple(self.cor) + (255,))
                self.letras.append((np.array(im), x))
            x += larg
        self.total = x
        self.y = self.H * self.e.get("y", 0.22)
        self.tam = tam

    def desenhar(self, frame, dt, rest):
        n = max(len(self.letras), 1)
        abre = 1 + 0.03 * ease_out((dt - 0.6) / 1.5)  # as letras se abrem devagar enquanto a palavra fica
        for i, (spr, x) in enumerate(self.letras):
            ti = dt - 0.04 * i
            p = clamp01(mola(ti / 0.5, 6, 9))
            if ti <= 0:
                continue
            qi = rest - 0.03 * (n - i)
            q = ease_in(1 - qi / 0.3) if qi < 0.3 else 0.0
            yy = self.y - spr.shape[0] / 2 - (1 - p) * self.tam * 0.9 - q * self.tam * 0.8
            xx = self.x - self.total * abre / 2 + x * abre - 20
            img = transformar(spr, 1.0, (1 - clamp01(p)) * 12 * (1 if i % 2 else -1))
            blend(frame, img, xx, yy, clamp01(ti / 0.1) * (1 - q))


@efeito("marca_texto", "marcacao", "Marca-texto passando sobre uma linha (print, b-roll, documento), com borda de traço real. "
        "Com 'texto', escreve a frase em marinho e passa o marca-texto champanhe por trás (funciona sobre qualquer fundo).",
        {"texto": "frase marcada (opcional; sem ela, só a faixa sobre o que já está na tela)", "x": "centro 0 a 1", "y": "0 a 1",
         "largura": "fração da largura (padrão 0.5)", "altura": "fração da altura (padrão 0.035)"},
        som="lapis")
class MarcaTexto(Efeito):
    def preparar(self):
        r = self.rng
        self.L = self.W * self.e.get("largura", 0.5)
        self.A = self.H * self.e.get("altura", 0.035)
        self.txt = None
        if self.e.get("texto"):
            u = self.W / 1080
            self.txt = _texto_rgba(self.e["texto"], "Black", int(self.e.get("tam", 64) * u), cor_marca("marinho"), "titulo")
            self.A = max(self.A, self.txt.shape[0] * 1.35)
            self.L = max(self.L, self.txt.shape[1] + 40 * u)
        xs = np.linspace(0, 1, 60)
        self.topo = r.normal(0, 0.06, 60).cumsum() * 0.2 + 0.0
        self.base = r.normal(0, 0.06, 60).cumsum() * 0.2 + 1.0
        self.xs = xs

    def desenhar(self, frame, dt, rest):
        p = ease_out(dt / 0.45)
        a = clamp01(rest / 0.3)
        if p <= 0.01 or a <= 0.01:
            return
        x0 = self.x - self.L / 2
        n = max(2, int(60 * p))
        sup = [(x0 + self.L * self.xs[i], self.y - self.A / 2 + self.topo[i] * self.A * 0.3) for i in range(n)]
        inf = [(x0 + self.L * self.xs[i], self.y + self.A / 2 + (self.base[i] - 1) * self.A * 0.3) for i in range(n)][::-1]
        ov = frame.copy()
        cv2.fillPoly(ov, [np.int32(sup + inf)], _bgr(self.cor), cv2.LINE_AA)
        forca = 0.92 if self.txt is not None else 0.42  # com texto próprio, a faixa precisa ser opaca para ler sobre o vídeo
        frame[:] = cv2.addWeighted(ov, forca * a, frame, 1 - forca * a, 0)
        if self.txt is not None:
            th, tw = self.txt.shape[:2]
            tx = int(self.x - tw / 2)
            vis = int(min(tw, x0 + self.L * self.xs[n - 1] - tx))  # a frase aparece junto com a faixa, da esquerda para a direita
            if vis > 0:
                blend(frame, self.txt[:, :vis], tx, int(self.y - th / 2), a)


@efeito("reacoes", "celebracao", "Objetos 3D subindo e balançando como reações de live (corações, fogo, 100). "
        "Para engajamento, 'comenta aqui', resultado bom.",
        {"objeto": "id da biblioteca 3D (padrão coracao)", "objetos": "lista de ids (alterna)", "quantidade": "padrão 10",
         "x": "0 a 1 (padrão 0.82)"}, som="pop-bolha")
class Reacoes(Efeito):
    def preparar(self):
        from PIL import Image

        from .bibliotecas import objeto_3d
        from .graficos import pil2np
        nomes = self.e.get("objetos") or [self.e.get("objeto", "coracao")]
        ims = []
        for nome in nomes:
            caminho, _ = objeto_3d(nome)
            im = Image.open(caminho).convert("RGBA")
            ims.append(im.crop(im.getbbox()))
        n = int(self.e.get("quantidade", 10))
        r = self.rng
        self.x = self.W * self.e.get("x", 0.82)
        self.sprites = []
        for i in range(n):
            im = ims[i % len(ims)]
            lado = int(self.W * r.uniform(0.07, 0.11))
            self.sprites.append(pil2np(im.resize((lado, int(im.height * lado / im.width)), Image.LANCZOS)))
        self.p = np.stack([r.uniform(0, 1.6, n), r.uniform(0.9, 1.4, n), r.uniform(-0.06, 0.06, n), r.uniform(0, 6.3, n)], 1)

    def desenhar(self, frame, dt, rest):
        a_sai = clamp01(rest / 0.4)
        for spr, (atraso, vel, dx, fase) in zip(self.sprites, self.p):
            t = dt - atraso
            if t <= 0:
                continue
            vida = t * vel / 2.2
            if vida > 1:
                continue
            y = self.H * (0.86 - 0.62 * ease_out(vida))
            x = self.x + self.W * (dx + 0.035 * math.sin(t * 3.2 + fase))
            s = clamp01(mola(t / 0.35, 6, 10)) * (1 - 0.3 * vida)
            img = transformar(spr, max(0.05, s), 10 * math.sin(t * 2.5 + fase))
            blend(frame, img, x - img.shape[1] / 2, y - img.shape[0] / 2, (1 - ease_in(vida)) * a_sai)


@efeito("reflexo", "luz", "Reflexo de vidro: uma faixa de luz atravessa a tela na diagonal (acabamento premium, revelação).",
        {"intensidade": "0 a 1 (padrão 1)", "duracao_passada": "segundos (padrão 0.9)"}, fase="pos", som="vidro-shimmer")
class Reflexo(Efeito):
    def preparar(self):
        w, h = self.W // 4, self.H // 4
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.d = (xx / w) * 0.8 + (yy / h) * 0.45

    def desenhar(self, frame, dt, rest):
        p = dt / self.e.get("duracao_passada", 0.9)
        if p > 1.05:
            return
        c = -0.25 + 1.6 * ease_in_out(p)
        banda = np.exp(-((self.d - c) / 0.05) ** 2) + 0.35 * np.exp(-((self.d - c + 0.11) / 0.025) ** 2)
        cam = cv2.resize(banda, (self.W, self.H))[..., None] * np.array(_bgr(cor_marca("papel_2")), np.float32)
        _tela(frame, cam, 0.55 * self.forca)


# ───────────────────────────── prévia (galeria e exportação) ─────────────────────────────

EXEMPLOS = {
    "contador": {"ate": 87, "sufixo": "%"},
    "cartao_vidro": {"texto": "Gate 2 · Business case", "sub": "Vale a pena investir?", "y": 0.3},
    "notificacao": {"app": "Cliente", "texto": "O projeto atrasou de novo. Dá pra salvar?", "y": 0.2},
    "carregando": {"rotulo": "Roadmap", "ate": 72, "y": 0.35},
    "checklist": {"titulo": "Antes do kickoff", "itens": ["Problema claro", "Dono definido", "Métrica de sucesso"], "y": 0.38},
    "tipografia": {"texto": "Escopo", "y": 0.35},
    "marca_texto": {"y": 0.42, "texto": "o problema certo"},
    "reacoes": {"objetos": ["coracao", "fogo", "cem"]},
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
