"""Biblioteca de efeitos (motor/efeitos.py): todos desenham, são determinísticos e só usam a paleta."""
import numpy as np
import pytest

from motor.efeitos import REGISTRO, catalogo_efeitos, criar_efeito
from motor.marca import ErroDeMarca

W, H = 270, 480
NOMES = sorted(REGISTRO)


def quadro(nome, t=0.6, dur=2.0):
    from motor.efeitos import EXEMPLOS
    e = dict({"tipo": "efeito", "nome": nome, "x": 0.5, "y": 0.4}, **EXEMPLOS.get(nome, {}))
    f = np.full((H, W, 3), 40, np.uint8)
    criar_efeito(e, W, H, 3).desenhar(f, t, dur - t)
    return f


def test_biblioteca_tem_os_efeitos_documentados():
    assert len(REGISTRO) >= 19
    for c in catalogo_efeitos():
        assert c["descricao"] and c["categoria"] and c["fase"] in ("elementos", "pos")


@pytest.mark.parametrize("nome", NOMES)
def test_efeito_desenha_algo(ativa, nome):
    ativa("pontes_brain")
    base = np.full((H, W, 3), 40, np.uint8)
    f = quadro(nome, t=0.6 if nome not in ("flash", "glitch", "tremor") else 0.1)
    assert f.shape == base.shape and f.dtype == np.uint8
    if nome not in ("tremor", "glitch"):  # deslocam a imagem: num quadro liso não muda nada
        assert np.abs(f.astype(int) - base).sum() > 0, nome


@pytest.mark.parametrize("nome", NOMES)
def test_efeito_deterministico(ativa, nome):
    ativa("girahub")
    assert np.array_equal(quadro(nome), quadro(nome))


def test_efeito_muda_com_a_paleta(ativa):
    ativa("pontes_brain")
    a = quadro("confete")
    ativa("girahub")
    assert not np.array_equal(a, quadro("confete"))


def test_efeito_desconhecido(ativa):
    ativa("modelo")
    with pytest.raises(ErroDeMarca):
        criar_efeito({"nome": "nao_existe"}, W, H)


def test_cor_fora_da_paleta(ativa):
    ativa("modelo")
    with pytest.raises(ErroDeMarca):
        criar_efeito({"nome": "confete", "cor": "#ff0000"}, W, H)
