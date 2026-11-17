"""Legenda palavra a palavra com a marcação na cor de destaque da marca.

Estilos ("estilo" em legendas):
- "marcada" (padrão): palavra atual com marcação na cor de destaque, contorno escuro.
- "limpa": 1 ou 2 palavras, branco quase puro, sem caixa e sem contorno, só uma sombra macia (tutorial em passos).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .graficos import fonte, pil2np
from .marca import CORES
from .movimento import clamp01, ease_out, lerp, mola

# Palavras que não fecham um bloco de legenda (artigos, preposições, conjunções).
FRACAS = set("a o as os um uma de da do das dos em na no nas nos por pra pro para com sem que e ou mas se ao à".split())

# Palavra falada -> objeto 3D da biblioteca que pula acima da legenda ("emoji": true em legendas).
EMOJIS = {
    "dinheiro": "dinheiro", "grana": "dinheiro", "lucro": "dinheiro-voando", "ideia": "lampada", "ideias": "lampada",
    "fogo": "fogo", "cresceu": "grafico-subindo", "crescer": "grafico-subindo", "crescimento": "grafico-subindo",
    "caiu": "grafico-descendo", "queda": "grafico-descendo", "foguete": "foguete", "decolar": "foguete",
    "coração": "coracao", "amor": "coracao", "cérebro": "cerebro", "pensar": "cerebro", "certo": "check",
    "atenção": "alerta", "cuidado": "alerta", "dúvida": "interrogacao", "pergunta": "interrogacao", "meta": "alvo",
    "objetivo": "alvo", "alvo": "alvo", "segredo": "cadeado", "chave": "chave", "ferramenta": "ferramentas",
    "ferramentas": "ferramentas", "livro": "livros", "estudar": "livros", "celular": "celular", "computador": "computador",
    "email": "envelope", "e-mail": "envelope", "festa": "festa", "comemorar": "festa", "força": "musculo",
    "vitória": "medalha", "prêmio": "medalha", "calendário": "calendario", "café": "cafe", "trabalho": "maleta",
    "equipe": "grupo", "time": "grupo", "câmera": "camera", "música": "notas-musicais", "link": "link",
    "procurar": "lupa", "pesquisa": "lupa", "tempo": "ampulheta", "prazo": "despertador", "ferramenta,": "ferramentas",
    "sucesso": "estrela-brilhante", "incrível": "cabeca-explodindo", "diamante": "diamante", "gráfico": "grafico-barras",
}


class Legendas:
    """Legenda palavra a palavra: cada palavra surge com mola no instante em que é falada e a
    marcação champanhe desliza de uma palavra para a próxima."""

    def __init__(self, palavras, cfg, W, H, keep):
        self.cfg, self.W, self.H = cfg, W, H
        corr = {k.lower(): v for k, v in cfg.get("correcoes", {}).items()}
        enf = {e.lower().strip(".,!?") for e in cfg.get("enfase", [])}
        dentro = lambda t: any(a <= t < b for a, b in keep)
        ws = []
        for w in palavras:
            if not dentro((w["ini"] + w["fim"]) / 2):
                continue
            nu = w["t"].strip(".,!?;:")  # a correção vale com ou sem pontuação colada ("echu," vira "Exu,")
            t = (w["t"].replace(nu, corr[nu.lower()]) if nu and nu.lower() in corr else corr.get(w["t"].lower(), w["t"]))
            if cfg.get("sem_pontuacao", True):
                t = t.rstrip(",.;:") if not t.endswith(("?", "!")) else t
            if t:
                ws.append(dict(w, t=t, orig=w["t"], enf=t.lower().strip(".,!?;:") in enf))
        n = cfg.get("palavras_por_bloco", 3)
        sentido = cfg.get("quebra_sentido", True)
        self.blocos, cur = [], []
        for i, w in enumerate(ws):
            cur.append(w)
            fim_frase = w["orig"][-1] in ".!?:,"
            pausa = i + 1 < len(ws) and ws[i + 1]["ini"] - w["fim"] > 0.4
            # quebra por sentido: o bloco não termina em "de", "o", "que"… (a palavra seguinte vem junto)
            presa = sentido and len(cur) == n and n > 1 and w["t"].lower() in FRACAS and i + 1 < len(ws)
            if (len(cur) >= n and not presa) or len(cur) > n or fim_frase or pausa or i == len(ws) - 1:
                self.blocos.append(cur)
                cur = []
        self.emojis = {}  # bloco -> (nome do objeto 3D, instante da palavra)
        if cfg.get("emoji"):
            mapa = dict(EMOJIS, **{k.lower(): v for k, v in (cfg.get("emoji") if isinstance(cfg.get("emoji"), dict) else {}).items()})
            ultimo = -9.0
            for bi, bl in enumerate(self.blocos):
                for w in bl:
                    nome = mapa.get(w["t"].lower().strip(".,!?;:"))
                    if nome and w["ini"] - ultimo > cfg.get("emoji_espaco", 4.0):
                        self.emojis[bi] = (nome, w["ini"])
                        ultimo = w["ini"]
                        break
        self.cache_emoji = {}
        self.limpa = cfg.get("estilo") == "limpa"
        tam = cfg.get("tamanho", (64 if self.limpa else 76) if W < 1500 else 56)
        self.f = fonte("Bold" if self.limpa else "Black", tam)
        self.lay = {}

    def emoji(self, i, t):
        """Objeto 3D (da biblioteca) que pula acima do bloco i quando a palavra dele é falada, ou None."""
        if i not in self.emojis:
            return None
        nome, t0 = self.emojis[i]
        dt = t - t0
        if dt < 0:
            return None
        if nome not in self.cache_emoji:
            from .bibliotecas import objeto_3d
            caminho, _ = objeto_3d(nome)
            im = Image.open(caminho).convert("RGBA")
            lado = int(self.W * self.cfg.get("emoji_tam", 0.13))
            self.cache_emoji[nome] = im.resize((lado, int(im.height * lado / im.width)), Image.LANCZOS)
        im = self.cache_emoji[nome]
        s = 0.2 + 0.8 * clamp01(mola(dt / 0.45, 7, 11))
        if s < 0.995:
            im = im.resize((max(2, int(im.width * s)), max(2, int(im.height * s))), Image.BILINEAR)
        return pil2np(im)

    def bloco_em(self, t):
        for i, b in enumerate(self.blocos):
            fim = self.blocos[i + 1][0]["ini"] if i + 1 < len(self.blocos) else b[-1]["fim"] + 0.5
            fim = min(fim, b[-1]["fim"] + 0.7)
            if b[0]["ini"] - 0.04 <= t < fim:
                return i
        return None

    def layout(self, i):
        if i in self.lay:
            return self.lay[i]
        b, f, gap = self.blocos[i], self.f, 20
        up = self.cfg.get("maiusculas")
        txt = [w["t"].upper() if up else w["t"] for w in b]
        larg = [f.getlength(x) for x in txt]
        linhas = [list(range(len(txt)))]
        # quebra em duas linhas antes de a caixa (texto + 80 px) passar de 70% da largura: centrada, fica entre 15% e 85%,
        # fora dos botões do Reels à direita
        if sum(larg) + gap * (len(txt) - 1) + 80 > self.W * self.cfg.get("largura_max", 0.70) and len(txt) > 1:
            m = (len(txt) + 1) // 2
            linhas = [list(range(m)), list(range(m, len(txt)))]
        lh = int(f.size * 1.34)
        Wc = int(max(sum(larg[k] for k in L) + gap * (len(L) - 1) for L in linhas)) + 80
        Hc = lh * len(linhas) + 40
        pos = {}
        for li, L in enumerate(linhas):
            x = (Wc - (sum(larg[k] for k in L) + gap * (len(L) - 1))) / 2
            for k in L:
                pos[k] = (x, 18 + li * lh, larg[k])
                x += larg[k] + gap
        sprites = []
        for k, t in enumerate(txt):
            def spr(cor, stroke):
                im = Image.new("RGBA", (int(larg[k]) + 24, lh + 12), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((12, 4), t, font=f, fill=cor, stroke_width=stroke, stroke_fill=CORES["marinho"])
                return im
            normal = spr(CORES["champanhe"] if b[k]["enf"] else (255, 255, 255), 7)
            sprites.append((normal, spr(CORES["marinho"], 0)))
        self.lay[i] = (Wc, Hc, pos, sprites, lh)
        return self.lay[i]

    def render(self, i, t):
        if self.limpa:
            return self.render_limpa(i, t)
        b = self.blocos[i]
        Wc, Hc, pos, sprites, lh = self.layout(i)
        im = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        cur = max([k for k, w in enumerate(b) if w["ini"] - 0.03 <= t] or [0])
        # marcação desliza da palavra anterior para a atual
        pr = ease_out((t - b[cur]["ini"]) / 0.12)
        x, y, w = pos[cur]
        if cur > 0 and pos[cur - 1][1] == y:
            px, _, pw = pos[cur - 1]
            x, w = lerp(px, x, pr), lerp(pw, w, pr)
            esc = 1.0
        else:
            esc = 0.6 + 0.4 * clamp01(mola((t - b[cur]["ini"]) / 0.35))
        so_enfase = self.cfg.get("marcacao") == "enfase"  # a marcação fica só nas palavras de ênfase (sem deslizar)
        cx, cy = x + w / 2, y + lh / 2 + 2
        hw, hh = (w / 2 + 16) * esc, (lh / 2 + 2) * esc
        if not so_enfase:
            ImageDraw.Draw(im).rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh], 10, fill=CORES["champanhe"] + (255,))
        for k, wd in enumerate(b):
            dt = t - wd["ini"]
            if dt < -0.03:
                continue
            p = clamp01(mola(max(dt, 0) / 0.32, 8, 13))
            if so_enfase and wd["enf"]:
                ex, ey, ew = pos[k]
                q = 0.6 + 0.4 * clamp01(mola(max(dt, 0) / 0.35))
                ehw, ehh = (ew / 2 + 16) * q, (lh / 2 + 2) * q
                ecx, ecy = ex + ew / 2, ey + lh / 2 + 2
                ImageDraw.Draw(im).rounded_rectangle([ecx - ehw, ecy - ehh, ecx + ehw, ecy + ehh], 10, fill=CORES["champanhe"] + (255,))
            sp = (sprites[k][1] if wd["enf"] else sprites[k][0]) if so_enfase else (sprites[k][1] if k == cur else sprites[k][0])
            s = 0.55 + 0.45 * p
            if s < 0.995:
                sp = sp.resize((max(2, int(sp.width * s)), max(2, int(sp.height * s))), Image.BILINEAR)
            x, y, w = pos[k]
            dy = (1 - clamp01(p)) * 22
            im.alpha_composite(sp, (int(x + w / 2 - sp.width / 2), int(y + lh / 2 + 4 - sp.height / 2 + dy)))
        return pil2np(im)


    def render_limpa(self, i, t):
        """Palavras brancas com sombra macia; cada uma sobe 10 px e acende quando é falada. Sem marcação."""
        b = self.blocos[i]
        Wc, Hc, pos, _, lh = self.layout(i)
        txt = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        d = ImageDraw.Draw(txt)
        up = self.cfg.get("maiusculas")
        for k, wd in enumerate(b):
            dt = t - wd["ini"]
            if dt < -0.03:
                continue
            p = clamp01(max(dt, 0) / 0.14)
            x, y, _ = pos[k]
            cor = CORES["champanhe"] if wd["enf"] else CORES["papel_2"]
            d.text((x + 12, y + 4 + (1 - p) * 10), wd["t"].upper() if up else wd["t"], font=self.f,
                   fill=tuple(cor) + (int(255 * (0.35 + 0.65 * p)),))
        a = np.array(txt)[..., 3]
        sombra = Image.fromarray(a).filter(ImageFilter.GaussianBlur(9))
        out = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        camada = Image.new("RGBA", (Wc, Hc), tuple(CORES["marinho"]) + (0,))
        camada.putalpha(sombra.point(lambda v: int(v * 0.75)))
        out.alpha_composite(camada, (0, 4))
        out.alpha_composite(txt)
        return pil2np(out)
