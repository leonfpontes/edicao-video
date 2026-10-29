"""Configuração e isolamento das marcas (motor/marca.py)."""
import copy

import pytest

from motor import marca
from motor.guarda import achar_termos, termos_de_outras
from motor.marca import ErroDeMarca

MARCAS = marca.listar_marcas()


def test_marcas_esperadas_existem():
    assert {"pontes_brain", "girahub", "leopontesrp", "modelo"} <= set(MARCAS)


@pytest.mark.parametrize("mid", MARCAS)
def test_marca_valida(mid):
    cfg = marca.ler_marca(mid)
    assert marca.validar_marca(cfg, mid) == []


def test_sem_marca_padrao():
    marca.ATIVA.update(id=None, pasta=None)
    with pytest.raises(ErroDeMarca):
        marca.marca_ativa()
    with pytest.raises(ErroDeMarca):
        marca.arquivo_marca("logo.png")


def test_ativar_troca_todas_as_cores(ativa):
    ativa("pontes_brain")
    azul = dict(marca.CORES)
    ativa("girahub")
    assert set(marca.CORES) == set(marca.PAPEIS_COR)
    assert all(marca.CORES[k] != azul[k] for k in ("marinho", "champanhe"))
    assert not marca.tem_leo()


def test_arquivo_marca_nao_sai_da_pasta(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca):
        marca.arquivo_marca("../pontes_brain/logo.png")
    with pytest.raises(ErroDeMarca):
        marca.arquivo_marca(str(marca.pasta_marca("pontes_brain") / "logo.png"))
    with pytest.raises(ErroDeMarca):
        marca.arquivo_marca("leo/cut-apontando.png")
    assert marca.arquivo_marca("logo.png").parent.name == "girahub"


@pytest.mark.parametrize("tipo,dono", [("pdca_lp", "pontes_brain"), ("ticket", "girahub")])
def test_vinheta_propria_nao_serve_a_outra(tipo, dono):
    for mid in MARCAS:
        if mid == dono:
            continue
        cfg = copy.deepcopy(marca.ler_marca(mid))
        cfg["intro"]["tipo"] = tipo
        assert any("exclusiva" in p for p in marca.validar_marca(cfg, mid))


@pytest.mark.parametrize("motivo,dono", [("pdca", "pontes_brain"), ("ticket", "girahub")])
def test_fundo_proprio_nao_serve_a_outro(motivo, dono):
    for mid in MARCAS:
        if mid == dono:
            continue
        cfg = copy.deepcopy(marca.ler_marca(mid))
        cfg["fundo_motivo"] = motivo
        assert any("exclusivo" in p for p in marca.validar_marca(cfg, mid))


def test_cor_faltando_e_erro():
    cfg = copy.deepcopy(marca.ler_marca("modelo"))
    del cfg["cores"]["bronze"]
    assert any("bronze" in p for p in marca.validar_marca(cfg, "modelo"))


@pytest.mark.parametrize("mid", MARCAS)
def test_configuracao_da_marca_nao_cita_outra(mid):
    """O próprio marca.json (nome, vinheta, CTA, vocabulário) não pode carregar termo exclusivo de outra marca."""
    cfg = marca.ler_marca(mid)
    termos = termos_de_outras(mid)
    textos = [cfg["nome"], cfg["intro"].get("nome", ""), cfg["intro"].get("sub", ""), cfg.get("vocabulario", "")]
    textos += [str(v) for v in (cfg.get("cta") or {}).values()]
    for t in textos:
        assert achar_termos(t, termos) == [], (mid, t)


def test_termo_compara_sem_acento_e_caixa():
    termos = {"senha da gira": "girahub", "leopontes.com.br": "pontes_brain"}
    assert achar_termos("A SENHA DA GÍRA chegou", termos)
    assert achar_termos("visite leopontes.com.br/mentoria", termos)
    assert not achar_termos("senhas da giratória", termos)
