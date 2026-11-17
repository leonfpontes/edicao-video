import numpy as np

from motor.camera import borda_exposta, matriz_enquadre
from motor.qa import borda_ruim


def test_enquadre_nunca_sai_da_fonte():
    # respiração abaixo de 1, rosto colado na borda e tremor forte: o recorte continua dentro da fonte
    for z in (0.97, 1.0, 1.2):
        for face in ((0.02, 0.1, 0.3), (0.98, 0.95, 0.3), (0.5, 0.5, 0.3)):
            for desloc in ((0, 0), (40, -40), (-60, 60)):
                M = matriz_enquadre(1080, 1920, 1080, 1920, z, face, desloc)
                assert borda_exposta(M, 1080, 1920, 1080, 1920) == 0


def test_borda_exposta_acusa_recorte_fora():
    M = np.float32([[1, 0, 30], [0, 1, 0]])  # quadro deslocado 30 px: a coluna da esquerda fica sem imagem
    assert borda_exposta(M, 1080, 1920, 1080, 1920) > 0


def test_faixa_preta_na_borda():
    q = np.random.default_rng(1).integers(40, 220, (320, 180, 3), dtype=np.uint8)
    assert borda_ruim(q) == []
    q[:, :20] = 0
    assert borda_ruim(q) == [("esquerda", 20)]
