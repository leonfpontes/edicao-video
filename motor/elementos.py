"""Elementos sobre o vídeo: títulos, destaques, Leo, objetos 3D, efeitos, imagens e b-roll."""
import math
import sys

import cv2
import numpy as np
from PIL import Image

from .bibliotecas import objeto_3d
from .efeitos import criar_efeito
from .graficos import Cartao, alpha_over, blend, cobrir, girar3d, pil2np, sombra, transformar
from .marca import ErroDeMarca, arquivo_marca, marca_ativa, registrar, tem_arquivo_marca, tem_leo
from .movimento import clamp01, ease_in, ease_out, ease_out_back, mola


class Leo:
    """Leo 3D: entra deslizando com giro e mola, 'respira' (flutua e balança) e sai deslizando."""

    def __init__(self, e, W, H):
        if not tem_leo():
            raise ErroDeMarca(f"o Leo é personagem do @pontes_brain: a marca {marca_ativa()} não o usa")
        pose = f"leo/cut-{e.get('pose', 'apontando')}.png"
        im = Image.open(arquivo_marca(pose if tem_arquivo_marca(pose) else "leo/leo3d-cut.png")).convert("RGBA")
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
    Entra girando com mola, flutua balançando e sai girando para o lado. A face (PNG transparente) vem da
    biblioteca (biblioteca/3d/logos/) ou da pasta da própria marca (marcas/<id>/3d/)."""

    def __init__(self, e, W, H, caminho):
        im = Image.open(caminho).convert("RGBA")
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


class Sprite3D:
    """Objeto já renderizado em 3D (biblioteca/3d/renders/): entra com mola girando no eixo Y, flutua
    balançando de leve, com sombra macia, e sai encolhendo. Mesmos parâmetros do objeto extrudado."""

    def __init__(self, e, W, H, caminho):
        im = Image.open(caminho).convert("RGBA")
        im = im.crop(im.getbbox())
        lado = int(W * e.get("tamanho", 0.22))
        im = im.resize((lado, int(im.height * lado / im.width)), Image.LANCZOS)
        pad = int(lado * 0.12)
        face = np.zeros((im.height + 2 * pad, im.width + 2 * pad, 4), np.uint8)
        face[pad:pad + im.height, pad:pad + im.width] = pil2np(im)
        self.face = face
        self.cx, self.cy = W * e.get("x", 0.5), H * e.get("y", 0.3)
        self.fase = e.get("fase", 0.0)
        self.cache = {}

    def sprite(self, graus):
        k = int(round(graus / 2) * 2)
        if k not in self.cache:
            spr = girar3d(self.face, k)
            self.cache[k] = sombra(spr, int(spr.shape[1] * 0.05), 0.42, (0, int(spr.shape[0] * 0.07)))[0]
        return self.cache[k]

    def desenhar(self, frame, dt, rest):
        ent = clamp01(dt / 0.6)
        sai = ease_in(1 - rest / 0.35) if rest < 0.35 else 0.0
        graus = -70 * (1 - mola(ent, 6, 9)) + 12 * math.sin(dt * 1.5 + self.fase) * ease_out(ent)
        esc = (0.3 + 0.7 * ease_out_back(ent, 1.8)) * (1 - 0.7 * sai)
        spr = transformar(self.sprite(max(-80, min(80, graus))), max(esc, 0.05), 4 * math.sin(dt * 1.2 + self.fase))
        h, w = spr.shape[:2]
        bob = 9 * math.sin(dt * 2.1 + self.fase)
        blend(frame, spr, self.cx - w / 2, self.cy - h / 2 + bob, clamp01(dt / 0.12) * (1 - sai))


class Elementos:
    """titulo | destaque | leo | objeto3d | efeito | imagem | broll — tempos na linha do tempo original."""

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
                caminho, it = objeto_3d(e["nome"])
                e["obj"] = (Sprite3D if it.get("tipo") == "render" else Objeto3D)(e, W, H, caminho)
            elif tp == "efeito":
                e["obj"] = criar_efeito(e, W, H, len(self.items))
            elif tp == "imagem":
                im = Image.open(registrar(e["arquivo"])).convert("RGBA")
                lw = int(W * e.get("largura", 0.6))
                im = im.resize((lw, int(im.height * lw / im.width)), Image.LANCZOS)
                e["img"], _ = sombra(pil2np(im), 20, 0.4)
                e.setdefault("y", 0.3)
            elif tp == "broll":
                p = registrar(e["arquivo"])
                if p.suffix.lower() in (".mp4", ".mov", ".m4v"):
                    e["cap"] = cv2.VideoCapture(str(p))
                else:
                    e["still"] = cv2.imread(str(p))
            self.items.append(e)

    def eventos(self):
        """Instantes de entrada (para o som de 'pop')."""
        return [e["o_ini"] for e in self.items if e["tipo"] in ("titulo", "destaque", "leo", "imagem", "objeto3d")
                or (e["tipo"] == "efeito" and e["obj"].pop)]

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

    def desenhar(self, frame, t, fase="elementos"):
        """fase "elementos": tudo que fica sob a legenda; fase "pos": efeitos de quadro inteiro (grão, vinheta,
        glitch…), aplicados por último, por cima de tudo."""
        for e in self.items:
            if e["tipo"] == "broll" or not (e["o_ini"] <= t < e["o_fim"]):
                continue
            dt, rest = t - e["o_ini"], e["o_fim"] - t
            if e["tipo"] == "efeito":
                if e["obj"].fase == fase:
                    e["obj"].desenhar(frame, dt, rest)
                continue
            if fase != "elementos":
                continue
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

