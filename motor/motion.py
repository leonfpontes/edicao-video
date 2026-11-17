"""Motion de interface e tipografia de estilo (docs/estilos-de-referencia.md).

Cada classe desenha um sprite RGBA (numpy, ordem RGB) a partir de dt (segundos desde a entrada) e rest
(segundos até a saída). As cores vêm só dos papéis da paleta da marca ativa; imagens externas (ícones de
app, prints) entram como são, porque "objeto externo leva a identidade dele".

Tipos novos de elemento (todos aceitam "na"/"ate", "x", "y" e "area": "palco"):

| tipo | campos |
|---|---|
| passo | numero, texto |
| digitacao | texto, vel (letras/s), caixa |
| janela | titulo, linhas ([[trecho]] sai marcado), largura |
| arvore | raiz, filhos |
| mapa | centro, itens (até 6) |
| comentario | texto (palavra-chave do CTA), dica |
| icone | arquivo (PNG) ou nome ("pasta", "documento", "pessoa"), rotulo, tamanho |
| carrossel | arquivos (2 a 6 imagens), altura |
| titulo_caixa | texto (linhas separadas por "/") |
| titulo_editorial | partes [{t, fonte, cor}], numero |
| bilhete | texto (letras de bilhete de resgate) |
| anotacao | texto (rótulo mono pequeno) |
| neon | texto, cor, caixa |
| texto_atras | texto, cor, fonte, tam (desenhado atrás da pessoa) |
| hud_rosto | rotulo (segue o rosto) |
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .estilos import fonte_estilo
from .graficos import pil2np, quebrar, sombra
from .marca import CORES, PAPEIS_COR, ErroDeMarca, registrar
from .movimento import clamp01, ease_in, ease_out, ease_out_back, mola


def cor(nome, padrao="champanhe"):
    nome = nome or padrao
    if nome not in PAPEIS_COR:
        raise ErroDeMarca(f"cor precisa ser um papel da paleta ({', '.join(PAPEIS_COR)}), não {nome!r}")
    return tuple(CORES[nome])


def rgba(c, a=255):
    return tuple(int(v) for v in c) + (int(a),)


def _saida(rest, d=0.25):
    return ease_in(1 - rest / d) if rest < d else 0.0


def _alpha(im, a):
    if a >= 0.999:
        return im
    arr = np.array(im)
    arr[..., 3] = (arr[..., 3].astype(np.float32) * clamp01(a)).astype(np.uint8)
    return Image.fromarray(arr)


def _sombra_pil(im, raio=18, opac=0.45, desloc=(0, 12)):
    arr, pad = sombra(pil2np(im), raio, opac, desloc)
    return Image.fromarray(arr), pad


def _icone_desenhado(nome, lado):
    """Ícones simples desenhados com a paleta (quando não há PNG do objeto real)."""
    im = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c1, c2, cl = cor("champanhe"), cor("bronze"), cor("papel_2")
    if nome == "pasta":
        d.rounded_rectangle([lado * 0.04, lado * 0.16, lado * 0.46, lado * 0.32], lado * 0.05, fill=rgba(c2))
        d.rounded_rectangle([lado * 0.04, lado * 0.24, lado * 0.96, lado * 0.84], lado * 0.07, fill=rgba(c2))
        d.rounded_rectangle([lado * 0.04, lado * 0.32, lado * 0.96, lado * 0.84], lado * 0.07, fill=rgba(c1))
    elif nome == "documento":
        d.rounded_rectangle([lado * 0.2, lado * 0.06, lado * 0.8, lado * 0.94], lado * 0.06, fill=rgba(cl))
        for k in range(5):
            y = lado * (0.24 + 0.12 * k)
            d.rounded_rectangle([lado * 0.3, y, lado * (0.7 if k % 2 else 0.6), y + lado * 0.04], 3, fill=rgba(cor("nevoa")))
    elif nome == "pessoa":
        d.ellipse([lado * 0.34, lado * 0.1, lado * 0.66, lado * 0.42], fill=rgba(cor("nevoa")))
        d.pieslice([lado * 0.16, lado * 0.48, lado * 0.84, lado * 1.16], 180, 360, fill=rgba(cor("nevoa")))
    else:
        raise ErroDeMarca(f"ícone desenhado desconhecido: {nome} (opções: pasta, documento, pessoa; ou use \"arquivo\")")
    return im


def _texto(t, f, c, a=255):
    l, t0, r, b = f.getbbox(t)
    im = Image.new("RGBA", (max(1, r - min(l, 0) + 8), max(1, b + 8)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-min(l, 0) + 2, 2), t, font=f, fill=rgba(c, a))
    return im


class Passo:
    """Cabeçalho de passo: número em serifa itálica ("Passo 1.") e o texto em sans. Entra subindo e fica."""

    def __init__(self, e, W, H):
        n, txt = e.get("numero", 1), e.get("texto", "")
        tam = int(W * e.get("tam", 0.052))
        f_num, f_txt = fonte_estilo("serifa_italica", int(tam * 1.08)), fonte_estilo("sans", tam)
        a = _texto(f"{e.get('rotulo', 'Passo')} {n}.", f_num, cor(e.get("cor"), "papel_2"))
        b = _texto(e.get("texto", txt), f_txt, cor(e.get("cor"), "papel_2"))
        esp = int(tam * 0.3)
        h = max(a.height, b.height)
        self.im = Image.new("RGBA", (a.width + esp + b.width, h), (0, 0, 0, 0))
        self.im.alpha_composite(a, (0, h - a.height))
        self.im.alpha_composite(b, (a.width + esp, h - b.height))

    def render(self, dt, rest):
        p = ease_out(dt / 0.35)
        im = _alpha(self.im, p * (1 - _saida(rest, 0.2)))
        out = Image.new("RGBA", (im.width, im.height + 20), (0, 0, 0, 0))
        out.alpha_composite(im, (0, int((1 - p) * 18)))
        return pil2np(out)


class Digitacao:
    """Texto digitado letra a letra com cursor piscando; com "caixa", dentro de um campo de texto."""

    def __init__(self, e, W, H):
        self.txt = e.get("texto", "")
        self.vel = float(e.get("vel", 16))
        self.f = fonte_estilo("sans", int(W * e.get("tam", 0.05)))
        self.caixa = e.get("caixa", False)
        self.larg = int(W * e.get("largura", 0.7)) if self.caixa else int(self.f.getlength(self.txt) + 40)
        self.alt = int(self.f.size * (2.0 if self.caixa else 1.4))
        self.c = cor(e.get("cor"), "papel_2")

    def letras(self, dt):
        return min(len(self.txt), int(max(dt - 0.1, 0) * self.vel))

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.larg, self.alt), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x0 = 20
        if self.caixa:
            d.rounded_rectangle([0, 0, self.larg - 1, self.alt - 1], self.alt // 2, fill=rgba(cor("marinho_2")),
                                outline=rgba(cor("nevoa"), 90), width=2)
            x0 = int(self.alt * 0.45)
        vis = self.txt[:self.letras(dt)]
        y = (self.alt - self.f.size * 1.2) / 2
        d.text((x0, y), vis, font=self.f, fill=rgba(self.c))
        if int(dt * 2.2) % 2 == 0 or self.letras(dt) < len(self.txt):
            cx = x0 + self.f.getlength(vis) + 4
            d.rectangle([cx, y + self.f.size * 0.1, cx + max(3, self.f.size // 14), y + self.f.size * 1.15], fill=rgba(cor("champanhe")))
        return pil2np(_alpha(im, clamp01(dt / 0.12) * (1 - _saida(rest))))


class Janela:
    """Janela de app (três pontos, barra, título) com linhas que aparecem uma a uma. [[trecho]] sai com
    marca-texto na cor de destaque."""

    def __init__(self, e, W, H):
        self.larg = int(W * e.get("largura", 0.86))
        tam = int(W * e.get("tam", 0.033))
        self.f, self.ft = fonte_estilo("sans_leve", tam), fonte_estilo("serifa", int(tam * 1.25))
        self.titulo = e.get("titulo", "")
        self.pad = int(tam * 1.4)
        linhas = []
        for ln in e.get("linhas", []):
            linhas += quebrar(ln, self.f, self.larg - 2 * self.pad) if "[[" not in ln else [ln]
        self.linhas = linhas
        self.lh = int(tam * 1.5)
        self.topo = int(tam * 2.2) + (int(tam * 2.4) if self.titulo else 0)
        self.alt = self.topo + self.lh * len(linhas) + self.pad
        self.vel = float(e.get("vel", 6))  # linhas por segundo

    def render(self, dt, rest):
        W, H = self.larg, self.alt
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, W - 1, H - 1], 22, fill=rgba(cor("papel_2")))
        d.rounded_rectangle([0, 0, W - 1, int(self.f.size * 1.9)], 22, fill=rgba(cor("papel")))
        d.rectangle([0, int(self.f.size * 1.2), W - 1, int(self.f.size * 1.9)], fill=rgba(cor("papel")))
        r = self.f.size * 0.28
        for k, c in enumerate(("bronze", "champanhe", "nevoa")):
            cx = self.pad * 0.7 + k * r * 3.2
            d.ellipse([cx - r, self.f.size * 0.95 - r, cx + r, self.f.size * 0.95 + r], fill=rgba(cor(c)))
        y = int(self.f.size * 2.4)
        if self.titulo:
            tw = self.ft.getlength(self.titulo)
            d.text(((W - tw) / 2, y), self.titulo, font=self.ft, fill=rgba(cor("marinho")))
            y += int(self.f.size * 2.4)
        n = int(max(dt - 0.25, 0) * self.vel) + 1
        for ln in self.linhas[:n]:
            x = self.pad
            partes = ln.replace("]]", "[[").split("[[")
            for k, pt in enumerate(partes):
                if not pt:
                    continue
                w = self.f.getlength(pt)
                if k % 2:
                    d.rectangle([x - 3, y - 2, x + w + 3, y + self.f.size * 1.2], fill=rgba(cor("champanhe"), 200))
                d.text((x, y), pt, font=self.f, fill=rgba(cor("marinho")))
                x += w
            y += self.lh
        p = clamp01(mola(dt / 0.5, 6, 10))
        sp, _ = _sombra_pil(im, 26, 0.5, (0, 18))
        esc = 0.86 + 0.14 * p
        sp = sp.resize((max(2, int(sp.width * esc)), max(2, int(sp.height * esc))), Image.BILINEAR)
        return pil2np(_alpha(sp, clamp01(dt / 0.15) * (1 - _saida(rest))))


def _cartao_rotulo(txt, f, c_txt, c_fundo, pad=(28, 16)):
    w = int(f.getlength(txt)) + 2 * pad[0]
    h = int(f.size * 1.25) + 2 * pad[1]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 18, fill=rgba(c_fundo), outline=rgba(cor("nevoa"), 70), width=2)
    d.text((pad[0], pad[1]), txt, font=f, fill=rgba(c_txt))
    return im


class Arvore:
    """Raiz em cima, linhas que se desenham e filhos que entram com mola, um a um."""

    def __init__(self, e, W, H):
        self.W = int(W * e.get("largura", 0.92))
        tam = int(W * e.get("tam", 0.04))
        f = fonte_estilo("sans", tam)
        self.raiz = _cartao_rotulo(e.get("raiz", ""), f, cor("marinho"), cor("champanhe"))
        self.filhos = [_cartao_rotulo(t, f, cor("papel_2"), cor("marinho_2")) for t in e.get("filhos", [])][:5]
        self.gap = int(tam * 3)
        self.H = self.raiz.height + self.gap + max([c.height for c in self.filhos] or [0]) + 20

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pr = clamp01(mola(dt / 0.45, 6, 10))
        r = self.raiz.resize((max(2, int(self.raiz.width * (0.7 + 0.3 * pr))), max(2, int(self.raiz.height * (0.7 + 0.3 * pr)))))
        im.alpha_composite(r, (self.W // 2 - r.width // 2, self.raiz.height // 2 - r.height // 2))
        n = len(self.filhos)
        if n:
            ybar = self.raiz.height + self.gap // 2
            pl = ease_out((dt - 0.3) / 0.45)
            cx = [int(self.W * (k + 0.5) / n) for k in range(n)]
            c_linha = rgba(cor("nevoa"), 200)
            if pl > 0:
                d.line([self.W // 2, self.raiz.height, self.W // 2, self.raiz.height + (ybar - self.raiz.height) * min(1, pl * 2)], fill=c_linha, width=3)
                meia = (cx[-1] - cx[0]) / 2 * clamp01(pl * 2 - 1)
                d.line([self.W // 2 - meia, ybar, self.W // 2 + meia, ybar], fill=c_linha, width=3)
            for k, c in enumerate(self.filhos):
                p = clamp01(mola((dt - 0.65 - 0.18 * k) / 0.45, 6, 10))
                if p <= 0:
                    continue
                d.line([cx[k], ybar, cx[k], ybar + self.gap // 2 * min(1, p)], fill=c_linha, width=3)
                cc = c.resize((max(2, int(c.width * (0.6 + 0.4 * p))), max(2, int(c.height * (0.6 + 0.4 * p)))))
                x = int(np.clip(cx[k] - cc.width / 2, 0, self.W - cc.width))
                im.alpha_composite(cc, (x, self.raiz.height + self.gap))
        return pil2np(_alpha(im, 1 - _saida(rest)))


class Mapa:
    """Recapitulação: um objeto no centro e os itens ao redor, ligados por linhas pontilhadas que se desenham."""

    def __init__(self, e, W, H):
        self.W, self.H = int(W * 0.96), int(H * e.get("altura", 0.42))
        tam = int(W * e.get("tam", 0.036))
        self.fc, self.fi, self.fn = fonte_estilo("sans", int(tam * 1.2)), fonte_estilo("sans", tam), fonte_estilo("serifa_italica", tam)
        self.centro = _cartao_rotulo(e.get("centro", ""), self.fc, cor("marinho"), cor("champanhe"), (34, 22))
        self.itens = list(e.get("itens", []))[:6]

    def render(self, dt, rest):
        W, H = self.W, self.H
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pc = clamp01(mola(dt / 0.45, 6, 10))
        c = self.centro.resize((max(2, int(self.centro.width * (0.6 + 0.4 * pc))), max(2, int(self.centro.height * (0.6 + 0.4 * pc)))))
        cx, cy = W // 2, H // 2
        n = len(self.itens)
        for k, txt in enumerate(self.itens):
            ang = -math.pi / 2 + 2 * math.pi * (k + 0.5) / max(n, 1) if n > 2 else (math.pi if k == 0 else 0)
            px, py = cx + math.cos(ang) * W * 0.34, cy + math.sin(ang) * H * 0.36
            p = ease_out((dt - 0.4 - 0.35 * k) / 0.5)
            if p <= 0:
                continue
            pts = 26
            for j in range(int(pts * p)):
                if j % 2:
                    continue
                a0, a1 = j / pts, (j + 1) / pts
                d.line([cx + (px - cx) * a0, cy + (py - cy) * a0, cx + (px - cx) * a1, cy + (py - cy) * a1], fill=rgba(cor("nevoa"), 180), width=3)
            if p > 0.6:
                partes = txt.split(". ", 1)
                al = clamp01((p - 0.6) / 0.4)
                yy = py - self.fi.size * (1.2 if len(partes) > 1 else 0.6)
                if len(partes) > 1:
                    w = self.fn.getlength(partes[0] + ".")
                    d.text((px - w / 2, yy), partes[0] + ".", font=self.fn, fill=rgba(cor("papel_2"), 255 * al))
                    yy += self.fi.size * 1.2
                t = partes[-1]
                w = self.fi.getlength(t)
                d.text((px - w / 2, yy), t, font=self.fi, fill=rgba(cor("nevoa"), 255 * al))
        im.alpha_composite(c, (cx - c.width // 2, cy - c.height // 2))
        return pil2np(_alpha(im, 1 - _saida(rest)))


class Comentario:
    """Barra de comentário com a palavra-chave sendo digitada e o botão de enviar (CTA "comenta a palavra")."""

    def __init__(self, e, W, H):
        self.larg, tam = int(W * 0.86), int(W * 0.042)
        self.f, self.fd = fonte_estilo("sans", tam), fonte_estilo("sans_leve", int(tam * 0.7))
        self.txt, self.dica = e.get("texto", ""), e.get("dica", "Comente")
        self.alt = int(tam * 2.3)

    def render(self, dt, rest):
        W, H = self.larg, self.alt + 60
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, W - 1, self.alt], self.alt // 2, fill=rgba(cor("marinho")), outline=rgba(cor("nevoa"), 90), width=2)
        n = min(len(self.txt), int(max(dt - 0.35, 0) * 10))
        vis = self.txt[:n]
        x0 = self.alt * 0.5
        y = (self.alt - self.f.size * 1.2) / 2
        if n == 0:
            d.text((x0, y + self.f.size * 0.2), self.dica, font=self.fd, fill=rgba(cor("nevoa")))
        d.text((x0, y), vis, font=self.f, fill=rgba(cor("papel_2")))
        if int(dt * 2.2) % 2 == 0:
            cx = x0 + self.f.getlength(vis) + 4
            d.rectangle([cx, y + 4, cx + 4, y + self.f.size * 1.1], fill=rgba(cor("champanhe")))
        r = self.alt * 0.36
        bx, by = W - self.alt * 0.55, self.alt / 2
        pr = clamp01(mola((dt - 0.35 - len(self.txt) / 10) / 0.4, 6, 10)) if n == len(self.txt) else 0.0
        rr = r * (0.8 + 0.2 * pr)
        d.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=rgba(cor("champanhe") if pr > 0 else cor("nevoa"), 255))
        d.polygon([(bx - rr * 0.35, by - rr * 0.45), (bx + rr * 0.5, by), (bx - rr * 0.35, by + rr * 0.45)], fill=rgba(cor("marinho")))
        p = ease_out(dt / 0.3)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(_alpha(im, p * (1 - _saida(rest))), (0, int((1 - p) * 40)))
        return pil2np(out)


class Icone:
    """Ícone com mola e sombra; com "rotulo", o nome embaixo. O PNG de um app ou objeto real entra com as cores dele."""

    def __init__(self, e, W, H):
        lado = int(W * e.get("tamanho", 0.2))
        if e.get("arquivo"):
            im = Image.open(registrar(e["arquivo"])).convert("RGBA")
            im = im.crop(im.getbbox() or (0, 0, im.width, im.height))
            im = im.resize((lado, max(1, int(im.height * lado / im.width))), Image.LANCZOS)
        else:
            im = _icone_desenhado(e.get("nome", "pasta"), lado)
        self.spr, _ = _sombra_pil(im, max(6, lado // 10), 0.5, (0, max(4, lado // 14)))
        self.rot = _texto(e["rotulo"], fonte_estilo("sans", int(W * 0.034)), cor("nevoa")) if e.get("rotulo") else None

    def render(self, dt, rest):
        p = mola(dt / 0.5, 6, 10)
        sai = _saida(rest, 0.2)
        esc = max(0.05, (0.3 + 0.7 * p) * (1 - 0.6 * sai))
        s = self.spr.resize((max(2, int(self.spr.width * esc)), max(2, int(self.spr.height * esc))), Image.BILINEAR)
        W = max(self.spr.width, self.rot.width if self.rot else 0)
        H = self.spr.height + (self.rot.height if self.rot else 0)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(s, ((W - s.width) // 2, (self.spr.height - s.height) // 2))
        if self.rot and dt > 0.2:
            out.alpha_composite(_alpha(self.rot, clamp01((dt - 0.2) / 0.2)), ((W - self.rot.width) // 2, self.spr.height - 10))
        return pil2np(_alpha(out, clamp01(dt / 0.1) * (1 - sai)))


class Carrossel:
    """Miniaturas (prints de Reels de referência) em cartões arredondados que deslizam devagar, em fila."""

    def __init__(self, e, W, H):
        self.W = W
        alt = int(H * e.get("altura", 0.2))
        larg = int(alt * 9 / 16)
        self.cards = []
        for a in e.get("arquivos", [])[:6]:
            im = Image.open(registrar(a)).convert("RGBA")
            s = max(larg / im.width, alt / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            im = im.crop(((im.width - larg) // 2, (im.height - alt) // 2, (im.width - larg) // 2 + larg, (im.height - alt) // 2 + alt))
            m = Image.new("L", (larg, alt), 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, larg - 1, alt - 1], 18, fill=255)
            im.putalpha(m)
            self.cards.append(_sombra_pil(im, 14, 0.5, (0, 10))[0])
        if not self.cards:
            raise ErroDeMarca("carrossel precisa de \"arquivos\" (2 a 6 imagens)")
        self.passo = larg + int(W * 0.03)
        self.alt = self.cards[0].height

    def render(self, dt, rest):
        out = Image.new("RGBA", (self.W, self.alt), (0, 0, 0, 0))
        n = len(self.cards)
        total = self.passo * n
        desl = (dt * self.passo * 0.6) % total
        for k in range(n * 2):
            x = int(self.W / 2 - self.passo * 1.5 + k * self.passo - desl)
            if -self.passo < x < self.W:
                c = self.cards[k % n]
                p = clamp01(mola((dt - 0.08 * (k % n)) / 0.5, 6, 10))
                out.alpha_composite(_alpha(c, p), (x, int((1 - p) * 30)))
        return pil2np(_alpha(out, 1 - _saida(rest)))


class TituloCaixa:
    """Gancho em caixas justas: cada linha numa caixa clara do tamanho do texto, texto escuro em sans forte e um
    colchete na cor de destaque abraçando o canto. Linhas separadas por "/"."""

    def __init__(self, e, W, H):
        f = fonte_estilo("sans_forte", int(W * e.get("tam", 0.05)))
        self.linhas = []
        for ln in [x.strip() for x in e.get("texto", "").split("/") if x.strip()]:
            t = _texto(ln, f, cor("marinho"))
            box = Image.new("RGBA", (t.width + 24, int(f.size * 1.22)), rgba(cor("papel_2")))
            box.alpha_composite(t, (12, int((box.height - t.height) / 2)))
            self.linhas.append(box)
        self.W = max(b.width for b in self.linhas) + 30
        self.H = sum(b.height for b in self.linhas) + 30

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        y = 15
        for k, b in enumerate(self.linhas):
            p = ease_out((dt - 0.08 * k) / 0.25)
            w = int(b.width * p)
            if w > 2:
                im.alpha_composite(b.crop((0, 0, w, b.height)), (15, y))
            y += b.height
        c = rgba(cor("champanhe"))
        L, esp = int(self.H * 0.45), 6
        pc = ease_out(dt / 0.3)
        d.line([2, 2, 2, 2 + L * pc], fill=c, width=esp)
        d.line([2, 2, 2 + L * pc, 2], fill=c, width=esp)
        d.line([2, self.H - 3, 2, self.H - 3 - L * pc], fill=c, width=esp)
        d.line([2, self.H - 3, 2 + L * 0.6 * pc, self.H - 3], fill=c, width=esp)
        return pil2np(_alpha(im, 1 - _saida(rest, 0.15)))


class TituloEditorial:
    """Título de revista: partes empilhadas em fontes diferentes (condensada, manuscrita, serifa), número circulado."""

    def __init__(self, e, W, H):
        partes = e.get("partes") or [{"t": e.get("texto", "")}]
        tam = int(W * e.get("tam", 0.11))
        self.sprites = []
        for k, pt in enumerate(partes):
            fn = pt.get("fonte", "condensada" if k % 2 == 0 else "manuscrita")
            esc = 0.75 if fn == "manuscrita" else 1.0
            self.sprites.append(_texto(pt.get("t", ""), fonte_estilo(fn, int(tam * esc)), cor(pt.get("cor"), "champanhe" if k % 2 == 0 else "papel_2")))
        self.num = e.get("numero")
        self.W = max(s.width for s in self.sprites) + int(tam * 0.9)
        self.H = sum(int(s.height * 0.86) for s in self.sprites) + 20
        self.tam = tam

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        y = 0
        for k, s in enumerate(self.sprites):
            p = ease_out_back((dt - 0.12 * k) / 0.4, 1.4)
            if p > 0:
                x = (self.W - s.width) // 2 + (int((k % 2 * 2 - 1) * self.tam * 0.15) if len(self.sprites) > 2 else 0)
                im.alpha_composite(_alpha(s, clamp01(p)), (max(0, x), int(y + (1 - clamp01(p)) * 30)))
            y += int(s.height * 0.86)
        if self.num is not None and dt > 0.3:
            d = ImageDraw.Draw(im)
            r = self.tam * 0.24
            cx, cy = self.W - r - 6, r + 6
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgba(cor("champanhe")), width=4)
            f = fonte_estilo("sans", int(r * 1.2))
            t = str(self.num)
            d.text((cx - f.getlength(t) / 2, cy - f.size * 0.62), t, font=f, fill=rgba(cor("champanhe")))
        return pil2np(_alpha(im, 1 - _saida(rest)))


class Bilhete:
    """Letras de bilhete de resgate: cada letra num recorte de cor e fonte diferentes, levemente girado, uma a uma."""

    def __init__(self, e, W, H, semente=0):
        tam = int(W * e.get("tam", 0.075))
        rng = np.random.default_rng(1009 + semente + sum(map(ord, e.get("texto", ""))))
        fundos = ["papel_2", "champanhe", "marinho", "bronze", "papel"]
        fontes = ["condensada", "serifa", "sans_forte", "mono"]
        self.letras = []
        for ch in e.get("texto", ""):
            if ch == " ":
                self.letras.append(None)
                continue
            fb = fundos[int(rng.integers(len(fundos)))]
            ft = "papel_2" if fb in ("marinho", "bronze") else "marinho"
            f = fonte_estilo(fontes[int(rng.integers(len(fontes)))], int(tam * rng.uniform(0.85, 1.15)))
            t = _texto(ch, f, cor(ft))
            box = Image.new("RGBA", (t.width + 10, t.height + 6), rgba(cor(fb)))
            box.alpha_composite(t, (5, 3))
            box = box.rotate(float(rng.uniform(-9, 9)), expand=True, resample=Image.BICUBIC)
            self.letras.append(box)
        self.esp = int(tam * 0.35)
        self.W = sum(b.width - 4 if b else self.esp for b in self.letras) + 10
        self.H = max([b.height for b in self.letras if b] or [tam]) + 10

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        x = 5
        for k, b in enumerate(self.letras):
            if b is None:
                x += self.esp
                continue
            if dt >= 0.045 * k:
                p = clamp01(mola((dt - 0.045 * k) / 0.25, 7, 14))
                bb = b.resize((max(2, int(b.width * (0.5 + 0.5 * p))), max(2, int(b.height * (0.5 + 0.5 * p)))))
                im.alpha_composite(bb, (x + (b.width - bb.width) // 2, (self.H - bb.height) // 2))
            x += b.width - 4
        return pil2np(_alpha(im, 1 - _saida(rest)))


class Anotacao:
    """Rótulo pequeno em fonte mono, com cruz de mira e revelado letra a letra (anotação de interface)."""

    def __init__(self, e, W, H):
        self.editorial = e.get("estilo") == "editorial"
        self.txt = e.get("texto", "")
        self.c = cor(e.get("cor"), "papel_2")
        self.caixa = e.get("caixa", False)  # tarja escura translúcida atrás (rótulo legível sobre fundo claro)
        if self.editorial:  # "firmeza de/Caboclo": sobrelinha pequena em sans e o nome em serifa itálica, com ponto e fio
            tam = int(W * e.get("tam", 0.05))
            sobre, _, nome = self.txt.rpartition("/")
            self.sobre, self.nome = sobre.strip().upper(), nome.strip()
            self.fs, self.fn = fonte_estilo("sans", int(tam * 0.36)), fonte_estilo("serifa_italica", tam)
            self.c2 = cor(e.get("cor2"), "champanhe")
            larg = max(self.fs.getlength(" ".join(self.sobre)) if self.sobre else 0, self.fn.getlength(self.nome))
            self.W, self.H = int(larg) + 76, int(tam * (1.75 if self.sobre else 1.3))
            return
        self.f = fonte_estilo("mono", int(W * e.get("tam", 0.022)))
        self.W, self.H = int(self.f.getlength(self.txt)) + 60 + (16 if self.caixa else 0), int(self.f.size * 1.6)

    def render_editorial(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        p = ease_out(min(dt / 0.45, 1))
        cy = self.H // 2
        if self.caixa:
            d.rounded_rectangle([30, 0, self.W - 1, self.H - 1], self.H // 6, fill=rgba(cor("marinho"), int(150 * p)))
        r = 7
        d.ellipse([2, cy - r, 2 + 2 * r, cy + r], outline=rgba(self.c2), width=3)  # ponto sobre o objeto
        d.ellipse([2 + r - 2, cy - 2, 2 + r + 2, cy + 2], fill=rgba(self.c2))
        d.line([2 + 2 * r, cy, 2 + 2 * r + int(22 * p), cy], fill=rgba(self.c2), width=2)  # fio até o texto
        txt = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        dt_ = ImageDraw.Draw(txt)
        y = (self.H - (self.fn.size * 1.15 + (self.fs.size * 1.5 if self.sobre else 0))) / 2
        if self.sobre:
            dt_.text((46, y), " ".join(self.sobre), font=self.fs, fill=rgba(self.c2))
            y += self.fs.size * 1.5
        dt_.text((46, y - self.fn.size * 0.08), self.nome, font=self.fn, fill=rgba(self.c))
        a = np.array(txt)
        a[..., 3] = (a[..., 3] * p).astype(np.uint8)
        txt = Image.fromarray(a)
        im.alpha_composite(txt, (0, int((1 - p) * 10)))
        return pil2np(_alpha(im, 1 - _saida(rest, 0.25)))

    def render(self, dt, rest):
        if self.editorial:
            return self.render_editorial(dt, rest)
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        n = min(len(self.txt), int(dt * 40))
        cy = self.H // 2
        if self.caixa and n:
            fim = 32 + int(self.f.getlength(self.txt[:n])) + 14
            d.rounded_rectangle([0, 0, min(fim, self.W - 1), self.H - 1], self.H // 4, fill=rgba(cor("marinho"), 170))
        d.line([4, cy, 20, cy], fill=rgba(self.c), width=2)
        d.line([12, cy - 8, 12, cy + 8], fill=rgba(self.c), width=2)
        d.text((32, cy - self.f.size * 0.62), self.txt[:n], font=self.f, fill=rgba(self.c))
        return pil2np(_alpha(im, 1 - _saida(rest, 0.15)))


class Neon:
    """Letreiro de neon manuscrito: acende tremulando, brilha com halo e pode ter moldura arredondada."""

    def __init__(self, e, W, H):
        self.f = fonte_estilo("manuscrita", int(W * e.get("tam", 0.09)))
        self.linhas = [x.strip() for x in e.get("texto", "").split("/") if x.strip()]
        self.c = cor(e.get("cor"), "champanhe")
        self.caixa = e.get("caixa", True)
        lw = max(self.f.getlength(x) for x in self.linhas)
        self.lh = int(self.f.size * 1.1)
        self.W, self.H = int(lw + self.f.size * 1.6), int(self.lh * len(self.linhas) + self.f.size * 1.0)
        traco = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(traco)
        for k, ln in enumerate(self.linhas):
            w = self.f.getlength(ln)
            d.text(((self.W - w) / 2, self.f.size * 0.4 + k * self.lh), ln, font=self.f, fill=rgba(self.c))
        if self.caixa:
            d.rounded_rectangle([8, 8, self.W - 9, self.H - 9], self.H // 3, outline=rgba(self.c), width=max(4, self.f.size // 18))
        claro = tuple(min(255, int(v * 0.4 + 255 * 0.6)) for v in self.c)
        nucleo = np.array(traco)
        nucleo[..., :3] = np.where(nucleo[..., 3:4] > 0, claro, 0)
        self.nucleo = Image.fromarray(nucleo)
        self.halo1 = traco.filter(ImageFilter.GaussianBlur(self.f.size * 0.12))
        self.halo2 = traco.filter(ImageFilter.GaussianBlur(self.f.size * 0.35))

    def acesa(self, dt):
        """0..1: tremula nos primeiros 0,6 s (padrão fixo, determinístico) e fica acesa."""
        if dt > 0.6:
            return 0.92 + 0.08 * math.sin(dt * 23) * math.sin(dt * 7)
        padrao = [0, 1, 0, 0, 1, 1, 0, 1, 1, 1, 0.3, 1]
        return padrao[min(int(dt / 0.05), len(padrao) - 1)]

    def render(self, dt, rest):
        a = self.acesa(dt) * (1 - _saida(rest, 0.2))
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        for _ in range(2):  # halo em duas camadas, somado duas vezes: brilho de neon de verdade
            im.alpha_composite(_alpha(self.halo2, 0.9 * a))
            im.alpha_composite(_alpha(self.halo1, 1.0 * a))
        im.alpha_composite(_alpha(self.nucleo, 0.25 + 0.75 * a))
        return pil2np(im)


class TextoAtras:
    """Texto enorme em fonte condensada que entra por partes e fica ATRÁS da pessoa (o render cola a pessoa
    recortada por cima). Use com o look "pb_acento" para a tipografia ser a única cor."""

    def __init__(self, e, W, H):
        self.linhas = [x.strip() for x in e.get("texto", "").split("/") if x.strip()] or [""]
        tam = int(W * e.get("tam", 0.3))
        f = fonte_estilo(e.get("fonte", "condensada"), tam)
        larg = max(f.getlength(x) for x in self.linhas)
        if larg > W * 0.94 - 40:  # cabe na tela: reduz até a linha mais longa ocupar 94% da largura
            tam = int(tam * (W * 0.94 - 40) / larg)
        self.f = fonte_estilo(e.get("fonte", "condensada"), tam)
        self.c = cor(e.get("cor"), "champanhe")
        self.lh = int(self.f.size * 0.95)
        self.W = int(max(self.f.getlength(x) for x in self.linhas) + 40)
        self.H = self.lh * len(self.linhas) + int(self.f.size * 0.3)

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        k = 0
        for li, ln in enumerate(self.linhas):
            x = (self.W - self.f.getlength(ln)) / 2
            for ch in ln:
                p = ease_out_back((dt - 0.035 * k) / 0.32, 1.2)
                if p > 0:
                    dy = (1 - p) * self.lh * 0.6
                    d.text((x, li * self.lh + dy - self.f.size * 0.1), ch, font=self.f, fill=rgba(self.c, 255 * clamp01(p * 2)))
                x += self.f.getlength(ch)
                k += 1
        return pil2np(_alpha(im, 1 - _saida(rest, 0.2)))


class HudRosto:
    """HUD de rastreamento facial: cantos de mira, malha de pontos sobre o rosto, anéis nos olhos e rótulo mono.
    Segue a posição do rosto no quadro (o render informa a cada quadro)."""

    def __init__(self, e, W, H):
        self.W, self.H = W, H
        self.rot = e.get("rotulo", "RASTREAMENTO FACIAL")
        self.c = cor(e.get("cor"), "champanhe")
        self.f = fonte_estilo("mono", int(W * 0.02))
        rng = np.random.default_rng(77)
        ang = rng.uniform(0, 2 * math.pi, 70)
        raio = np.sqrt(rng.uniform(0, 1, 70))
        self.pontos = np.stack([np.cos(ang) * raio * 0.42, np.sin(ang) * raio * 0.55], 1)

    def desenhar(self, frame, dt, rest, rosto):
        if rosto is None:
            return
        cx, cy, h = rosto
        a = clamp01(dt / 0.2) * (1 - _saida(rest, 0.2))
        if a <= 0:
            return
        c = (int(self.c[2]), int(self.c[1]), int(self.c[0]))
        camada = frame.copy()
        w = h * 0.8
        x0, y0, x1, y1 = int(cx - w * 0.75), int(cy - h * 0.8), int(cx + w * 0.75), int(cy + h * 0.75)
        L = int(w * 0.18)
        for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            cv2.line(camada, (px, py), (px + sx * L, py), c, 3, cv2.LINE_AA)
            cv2.line(camada, (px, py), (px, py + sy * L), c, 3, cv2.LINE_AA)
        nv = int(len(self.pontos) * clamp01(dt / 0.6))
        for k, (dx, dy) in enumerate(self.pontos[:nv]):
            px, py = int(cx + dx * w * 1.2), int(cy + dy * h * 1.1)
            cv2.circle(camada, (px, py), 3, (255, 255, 255), -1, cv2.LINE_AA)
            if k and k % 3 == 0:
                qx, qy = self.pontos[k - 1]
                cv2.line(camada, (px, py), (int(cx + qx * w * 1.2), int(cy + qy * h * 1.1)), c, 1, cv2.LINE_AA)
        if dt > 0.4:
            for ox in (-0.2, 0.2):
                ex, ey = int(cx + ox * w), int(cy - 0.12 * h)
                for r, esp in ((int(w * 0.13), 2), (int(w * 0.17), 1)):
                    ang = (dt * 120) % 360
                    cv2.ellipse(camada, (ex, ey), (r, r), ang, 0, 270, (255, 255, 255), esp, cv2.LINE_AA)
        frame[:] = cv2.addWeighted(frame, 1 - a, camada, a, 0)
        n = min(len(self.rot), int(dt * 30))
        im = Image.new("RGBA", (int(self.f.getlength(self.rot)) + 10, int(self.f.size * 1.5)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((2, 2), self.rot[:n], font=self.f, fill=rgba(self.c, 255 * a))
        from .graficos import blend
        blend(frame, pil2np(im), x0, y0 - im.height - 8)


class RotuloSom:
    """Som visível: uma onda que pulsa e o nome do efeito sonoro em mono, no instante em que ele toca."""

    def __init__(self, e, W, H):
        self.txt = e.get("rotulo", "")
        self.f = fonte_estilo("mono", int(W * 0.03))
        self.c = cor(e.get("cor"), "champanhe")
        self.W, self.H = int(W * 0.5), int(W * 0.2)

    def render(self, dt, rest):
        im = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        env = math.exp(-3.5 * dt) * clamp01(dt / 0.05)
        n, cy = 34, self.H * 0.62
        for k in range(n):
            x = self.W * (0.04 + 0.92 * k / (n - 1))
            amp = self.H * 0.32 * env * (0.35 + 0.65 * abs(math.sin(k * 1.7 + dt * 18))) * math.sin(math.pi * k / (n - 1))
            d.line([x, cy - amp, x, cy + amp], fill=rgba(self.c, 230), width=4)
        tw = self.f.getlength(self.txt) + 22
        d.rounded_rectangle([self.W - tw - 4, 2, self.W - 4, self.f.size * 1.5 + 2], 10, outline=rgba(cor("papel_2"), 220), width=2)
        d.text((self.W - tw + 7, 4), "• " + self.txt[:int(dt * 30) + 1], font=self.f, fill=rgba(cor("papel_2")))
        return pil2np(_alpha(im, 1 - _saida(rest, 0.2)))


# tipo -> classe; os que recebem semente estão em COM_SEMENTE
TIPOS = {
    "passo": Passo, "digitacao": Digitacao, "janela": Janela, "arvore": Arvore, "mapa": Mapa,
    "comentario": Comentario, "icone": Icone, "carrossel": Carrossel, "titulo_caixa": TituloCaixa,
    "titulo_editorial": TituloEditorial, "bilhete": Bilhete, "anotacao": Anotacao, "neon": Neon,
    "texto_atras": TextoAtras, "hud_rosto": HudRosto,
}
COM_SEMENTE = {"bilhete"}
# posição padrão (y) de cada tipo; os de interface usam o palco
Y_PADRAO = {"passo": 0.08, "digitacao": 0.5, "janela": 0.5, "arvore": 0.5, "mapa": 0.5, "comentario": 0.86,
            "icone": 0.45, "carrossel": 0.55, "titulo_caixa": 0.09, "titulo_editorial": 0.6, "bilhete": 0.7,
            "anotacao": 0.12, "neon": 0.75, "texto_atras": 0.45}
AREA_PALCO = {"passo", "digitacao", "janela", "arvore", "mapa", "icone"}


def criar(e, W, H, semente=0):
    cls = TIPOS[e["tipo"]]
    return cls(e, W, H, semente) if e["tipo"] in COM_SEMENTE else cls(e, W, H)
