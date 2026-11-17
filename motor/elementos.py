"""Elementos sobre o vídeo: títulos, destaques, Leo, objetos 3D, efeitos, imagens, b-roll e o motion de estilo
(motor/motion.py: passo, janela, árvore, neon, texto atrás da pessoa, HUD…)."""
import math
import sys

import cv2
import numpy as np
from PIL import Image

from .audio import som_padrao
from .bibliotecas import objeto_3d
from .config import FPS
from .efeitos import criar_efeito
from .graficos import Cartao, alpha_over, blend, cobrir, girar3d, pil2np, sombra, transformar
from .marca import ErroDeMarca, arquivo_marca, marca_ativa, registrar, tem_arquivo_marca, tem_leo
from .motion import AREA_PALCO, TIPOS, Y_PADRAO, HudRosto, RotuloSom, criar
from .movimento import clamp01, ease_in, ease_out, ease_out_back, mola
from .perspectiva import TelaPerspectiva


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
    """titulo | destaque | leo | objeto3d | efeito | imagem | broll | som — tempos na linha do tempo original."""

    def __init__(self, lst, W, H, map_out, palavras=()):
        self.W, self.H, self.items = W, H, []
        self.plano = "rosto"  # plano do quadro atual (o render atualiza): define a área do palco
        self.rosto = None  # (cx, cy, altura) do rosto no quadro de saída, para o HUD
        self.caixas = None  # lista ligada pelo render nos quadros conferidos: caixas dos elementos desenhados
        self.M, self.t_src, self.fonte = None, 0.0, (W, H)  # enquadramento do quadro atual (o render atualiza)
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
                e["ini"] = a - e.get("antecipa", 0.0 if e["tipo"] == "som" else 0.12)
                e.setdefault("fim", b + e.get("segura", 1.2))
                if "ate" in e:
                    e["fim"] = achar(e["ate"], 1, a)[1] + e.get("segura", 0.25)
            if e["tipo"] == "som":  # só áudio: o ápice do som cai no início do elemento (ex.: riser chegando na palavra)
                e.setdefault("fim", e["ini"] + (0.9 if e.get("rotulo") else 0.5))
            if "saida" in e:  # tempos já na linha do tempo final (ex.: título sobre o gancho)
                e["o_ini"], e["o_fim"] = e["saida"]
            else:
                e["o_ini"], e["o_fim"] = map_out(e["ini"]), map_out(e["fim"])
            if e["o_fim"] <= e["o_ini"]:
                continue
            if e.get("seguir"):  # [[t da fonte, x, y], …] em fração da fonte: o elemento acompanha esse ponto
                e["seguir"] = np.array(e["seguir"], np.float64).reshape(-1, 3)
            tp = e["tipo"]
            if tp in ("titulo", "destaque"):
                e["obj"] = Cartao(e["texto"], W * (0.86 if tp == "titulo" else 0.8), tp, e.get("tam"))
                e.setdefault("y", 0.15 if tp == "titulo" else 0.12)
            elif tp == "leo":
                e["obj"] = Leo(e, W, H)
            elif tp == "objeto3d":
                try:
                    caminho, it = objeto_3d(e["nome"])
                except ErroDeMarca as erro:  # o roteiro pediu um objeto que não existe: o editor cria (criar3d.py)
                    if "desconhecido" not in str(erro) or not any(e.get(k) for k in ("fluent", "emoji", "texto_3d")):
                        raise
                    from .criar3d import criar_3d
                    iid, como = criar_3d(e["nome"], e.get("fluent"), e.get("emoji"), e.get("texto_3d"))
                    if not iid:
                        raise ErroDeMarca(f"não consegui criar o objeto 3D {e['nome']}: {como}") from erro
                    print(f"  objeto 3D criado: {iid} ({como})", flush=True)
                    caminho, it = objeto_3d(iid)
                e["obj"] = (Sprite3D if it.get("tipo") == "render" else Objeto3D)(e, W, H, caminho)
            elif tp == "efeito":
                e["obj"] = criar_efeito(e, W, H, len(self.items))
            elif tp == "imagem":
                im = Image.open(registrar(e["arquivo"])).convert("RGBA")
                lw = int(W * e.get("largura", 0.6))
                im = im.resize((lw, int(im.height * lw / im.width)), Image.LANCZOS)
                e["img"], _ = sombra(pil2np(im), 20, 0.4)
                e.setdefault("y", 0.3)
            elif tp in TIPOS:
                e["obj"] = criar(e, W, H, len(self.items))
                e.setdefault("y", Y_PADRAO.get(tp, 0.5))
                if tp in AREA_PALCO:
                    e.setdefault("area", "palco")
            elif tp == "som" and e.get("rotulo"):
                e["obj"] = RotuloSom(e, W, H)
                e.setdefault("y", 0.3)
            elif tp == "broll":
                e.pop("seguir", None)
                if e.get("perspectiva"):
                    e["persp"] = TelaPerspectiva(e["perspectiva"] if isinstance(e["perspectiva"], dict) else {}, W, H)
                p = registrar(e["arquivo"])
                if p.suffix.lower() in (".mp4", ".mov", ".m4v"):
                    e["cap"] = cv2.VideoCapture(str(p))
                else:
                    e["still"] = cv2.imread(str(p))
            self.items.append(e)

    def eventos(self, modo="gerado"):
        """Sons de entrada: [(instante na saída, id do som ou "pop", ajuste em dB)].
        "som": "<id>" no elemento escolhe o som; "som": false silencia. Sem escolha, o modo da marca decide:
        "biblioteca" usa o som padrão do tipo (ou do efeito) e "gerado" usa o pop sintético de sempre."""
        out = []
        for e in self.items:
            tp, pedido, g = e["tipo"], e.get("som"), e.get("volume_db", 0)
            if tp == "som":
                out.append((e["o_ini"], e["nome"], g))
            elif pedido is False or pedido == "":
                continue
            elif isinstance(pedido, str):
                out.append((e["o_ini"], pedido, g))
            elif modo == "biblioteca":
                sid = e["obj"].som if tp == "efeito" else som_padrao("elementos", tp)
                if sid:
                    out.append((e["o_ini"], sid, g))
                    batidas = getattr(e["obj"], "batidas", None) if tp == "efeito" else None
                    out += [(e["o_ini"] + b, sid, g) for b in (batidas() if batidas else []) if e["o_ini"] + b < e["o_fim"]]
            elif tp in ("titulo", "destaque", "leo", "imagem", "objeto3d") or tp in TIPOS or (tp == "efeito" and e["obj"].pop):
                out.append((e["o_ini"], "pop", g))
        return out

    def ativo(self, t, tipo):
        return any(e["tipo"] == tipo and e["o_ini"] <= t < e["o_fim"] for e in self.items)

    def ativos(self, t, tipo):
        return [e for e in self.items if e["tipo"] == tipo and e["o_ini"] <= t < e["o_fim"]]

    def broll_ativo(self, t):
        return next((e for e in self.items if e["tipo"] == "broll" and e["o_ini"] <= t < e["o_fim"]), None)

    def broll(self, t):
        for e in self.items:
            if e["tipo"] == "broll" and e["o_ini"] <= t < e["o_fim"]:
                if "cap" in e:  # quadro pelo instante (não pela ordem de leitura): o render em trechos paralelos dá o mesmo
                    cap = e["cap"]
                    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
                    fps = cap.get(cv2.CAP_PROP_FPS) or FPS  # na velocidade real do b-roll (gravação de tela a 60 fps não fica lenta)
                    k = int(round((t - e["o_ini"]) * fps)) % n
                    if e.get("pos") != k:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, k)
                    ok, f = cap.read()
                    if not ok:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, f = cap.read()
                    e["pos"] = k + 1
                else:
                    f = e["still"]
                p = (t - e["o_ini"]) / max(e["o_fim"] - e["o_ini"], 0.01)
                if "persp" in e:
                    return e["persp"].quadro(f, p)
                return cobrir(f, self.W, self.H, 1.0 + 0.08 * p)
        return None

    def alvo(self, e):
        """Ponto da trilha "seguir" no quadro de saída (px), com o deslocamento "dx"/"dy" (fração da tela) e preso à
        área segura. A trilha está na fonte; o enquadramento (zoom, rosto, punch) é aplicado aqui."""
        tr = e["seguir"]
        xs = float(np.interp(self.t_src, tr[:, 0], tr[:, 1])) * self.fonte[0]
        ys = float(np.interp(self.t_src, tr[:, 0], tr[:, 2])) * self.fonte[1]
        M = self.M if self.M is not None else np.float32([[self.W / self.fonte[0], 0, 0], [0, self.H / self.fonte[1], 0]])
        X = M[0, 0] * xs + M[0, 1] * ys + M[0, 2] + e.get("dx", 0) * self.W
        Y = M[1, 0] * xs + M[1, 1] * ys + M[1, 2] + e.get("dy", 0) * self.H
        return min(max(X, 0.08 * self.W), 0.86 * self.W), min(max(Y, 0.1 * self.H), 0.8 * self.H)

    def seguir(self, e):
        X, Y = self.alvo(e)
        ob = e.get("obj")
        if e["tipo"] == "efeito":
            if not hasattr(ob, "_x0"):
                ob._x0, ob._y0, ob._pts0 = ob.x, ob.y, getattr(ob, "pts", None)
            ob.x, ob.y = X, Y
            if isinstance(ob._pts0, np.ndarray) and ob._pts0.ndim == 2 and ob._pts0.shape[1] == 2:
                ob.pts = ob._pts0 + np.array([X - ob._x0, Y - ob._y0])  # traços já desenhados (círculo, seta) andam juntos
        elif hasattr(ob, "cx") and hasattr(ob, "cy"):
            ob.cx, ob.cy = X, Y
        elif e["tipo"] in ("titulo", "destaque", "titulo_caixa"):  # cartão grande: centro longe das bordas e acima da legenda
            e["x"], e["y"] = min(max(X / self.W, 0.3), 0.66), min(max(Y / self.H, 0.14), 0.55)
        else:  # rótulo pequeno (anotação): a mira cai no objeto e o texto sai para a direita, sem deixar a área segura
            meia = getattr(ob, "W", 0) / 2 / self.W
            x = X / self.W + (meia if e["tipo"] == "anotacao" else 0)
            meia_h = getattr(ob, "H", 0) / 2 / self.H
            y = min(max(Y / self.H, 0.1 + meia_h), 0.62)
            e["x"], e["y"] = min(max(x, 0.06 + meia), (0.85 if y > 0.5 else 0.94) - meia), y  # longe dos botões do Reels

    def posicao(self, e, w, h):
        """Canto superior esquerdo do sprite: x/y são o centro, na tela ou dentro do palco ("area": "palco")."""
        y0, alt = 0, self.H
        if e.get("area") == "palco" and self.plano == "dividido":
            alt = self.H // 2
        return self.W * e.get("x", 0.5) - w / 2, y0 + alt * e["y"] - h / 2

    def desenhar(self, frame, t, fase="elementos"):
        """fase "atras": o que fica atrás da pessoa (texto_atras; o render cola a pessoa por cima);
        fase "elementos": tudo que fica sob a legenda; fase "pos": efeitos de quadro inteiro (grão, vinheta,
        glitch…), aplicados por último, por cima de tudo."""
        for e in self.items:
            if e["tipo"] == "broll" or (e["tipo"] == "som" and "obj" not in e) or not (e["o_ini"] <= t < e["o_fim"]):
                continue
            if (e["tipo"] == "texto_atras") != (fase == "atras"):
                continue
            if e.get("area") == "palco" and self.plano == "rosto" and not e.get("sempre"):
                continue  # motion de palco só aparece nos planos dividido e motion
            dt, rest = t - e["o_ini"], e["o_fim"] - t
            if isinstance(e.get("seguir"), np.ndarray):
                self.seguir(e)
            if isinstance(e.get("obj"), HudRosto):
                if fase == "elementos":
                    e["obj"].desenhar(frame, dt, rest, self.rosto)
                continue
            if e["tipo"] == "efeito":
                if e["obj"].fase == fase:
                    e["obj"].desenhar(frame, dt, rest)
                continue
            if fase not in ("elementos", "atras"):
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
            x, y = self.posicao(e, w, h)
            blend(frame, img, x, y, alpha)
            if self.caixas is not None and alpha > 0.5:  # para a conferência visual: onde o elemento ficou
                ys, xs = (img[..., 3] > 40).nonzero() if img.shape[2] == 4 else ([0, h - 1], [0, w - 1])
                if len(xs):
                    rot = e.get("texto") or e.get("nome") or e["tipo"]
                    self.caixas.append((f"{e['tipo']} \"{str(rot)[:30]}\"", e["tipo"], x + min(xs), y + min(ys), x + max(xs), y + max(ys)))

