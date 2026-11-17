"""Planos de composição por segmento (estilo "tutorial em passos").

    {"id": 3, "ini": 10.8, "fim": 14.8, "plano": "dividido"}

- "rosto": a câmera ocupa a tela inteira (padrão).
- "dividido": metade de cima é o palco de motion (fundo escuro liso da marca); metade de baixo, o rosto.
- "motion": só o palco; a voz continua.

Os elementos com "area": "palco" usam coordenadas do palco (x e y de 0 a 1 dentro dele), então o mesmo
elemento serve no plano dividido (palco = metade de cima) e no plano motion (palco = tela inteira).
A troca entre planos é sempre em corte seco: é a regra do estilo.
"""
import cv2
import numpy as np

from .marca import CORES

PLANOS = {
    "rosto": "Câmera em tela cheia (padrão).",
    "dividido": "Palco de motion em cima, rosto embaixo; a legenda fica na linha que divide.",
    "motion": "Só o palco de motion; a voz continua.",
}

# legenda (centro do bloco, fração da altura) em cada plano
LEGENDA_Y = {"rosto": None, "dividido": 0.5, "motion": 0.72}


def _bgr(rgb):
    return np.array((rgb[2], rgb[1], rgb[0]), np.float32)


class Palco:
    """Fundo do motion: tom escuro da marca, liso, com luz suave no centro (profundidade sem textura)."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.42) / H) ** 2)
        luz = np.clip(1 - d * 1.6, 0, 1)[..., None] ** 2
        base, sup = _bgr(CORES["marinho"]), _bgr(CORES["marinho_2"])
        self.quadro = (base * (1 - 0.35 * luz) + sup * 0.35 * luz).clip(0, 255).astype(np.uint8)

    def area(self, plano):
        """(y0, altura) do palco no quadro final."""
        if plano == "dividido":
            return 0, self.H // 2
        return 0, self.H


def compor(plano, rosto, palco, W, H, corte_y=0.36):
    """Quadro do plano: rosto é o quadro da câmera já enquadrado (W×H); palco é o quadro do palco (W×H).
    corte_y: no dividido, onde fica o centro da faixa de rosto mostrada (fração da altura do quadro da câmera)."""
    if plano in (None, "rosto"):
        return rosto
    if plano == "motion":
        return palco.copy()
    if plano == "dividido":
        meia = H // 2
        out = palco.copy()
        y0 = int(np.clip(corte_y * H - meia / 2, 0, H - meia))
        out[meia:] = rosto[y0:y0 + meia]
        # linha de luz finíssima na divisão (separa sem chamar atenção)
        out[meia - 1:meia + 1] = cv2.addWeighted(out[meia - 1:meia + 1], 0.6, np.full_like(out[meia - 1:meia + 1], 255), 0.4, 0)
        return out
    raise ValueError(f"plano desconhecido: {plano} (opções: {', '.join(PLANOS)})")


def legenda_y(plano, padrao, cfg):
    """Posição vertical da legenda no plano (fração da altura). cfg pode trocar: "posicao_y_dividido", "posicao_y_motion"."""
    if plano in (None, "rosto"):
        return padrao
    return cfg.get(f"posicao_y_{plano}", LEGENDA_Y[plano])
