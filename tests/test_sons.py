"""Biblioteca de efeitos sonoros (biblioteca/sons/) e o mapa de sons do motor."""
import numpy as np
import pytest

from motor import bibliotecas as bib
from motor.audio import SONS_PADRAO, mixar_eventos, modo_sons, som_padrao
from motor.camera import transicao
from motor.config import BIBLIOTECA
from motor.efeitos import catalogo_efeitos
from motor.elementos import Elementos
from motor.guarda import conferir_edl
from motor.marca import ErroDeMarca

IDS = {it["id"] for it in bib.itens("sons")}


def test_catalogo_de_sons_livre_e_completo():
    sons = bib.itens("sons")
    assert len(sons) >= 35
    assert len(IDS) == len(sons)
    for it in sons:
        assert it["licenca"] in bib.LICENCAS_LIVRES, it["id"]
        assert (BIBLIOTECA / "sons" / it["arquivo"]).exists(), it["id"]
        assert 0 <= it["ataque"] <= it["duracao"], it["id"]
        assert it["usos"] and it["tags"] and it["credito"], it["id"]
        assert -20 <= it["volume_db"] <= 0, it["id"]


def test_sons_padrao_existem():
    ids = set()
    for v in SONS_PADRAO.values():
        for x in (v.values() if isinstance(v, dict) else [v]):
            ids.update(x if isinstance(x, list) else [x])
    assert ids <= IDS, ids - IDS
    efeitos = {e["som"] for e in catalogo_efeitos() if e.get("som")}
    assert efeitos <= IDS, efeitos - IDS


def test_modo_por_marca(ativa):
    ativa("pontes_brain")
    assert modo_sons() == "biblioteca"
    assert som_padrao("transicoes", "push", 0) != som_padrao("transicoes", "push", 1)  # alterna as variações
    ativa("girahub")
    assert modo_sons() == "gerado"  # as outras marcas seguem com o whoosh e o pop de antes


def test_eventos_dos_elementos(ativa):
    ativa("pontes_brain")
    pal = [{"t": w, "ini": i * 0.5, "fim": i * 0.5 + 0.4} for i, w in enumerate("isso muda tudo agora".split())]
    els = Elementos([{"tipo": "destaque", "texto": "Muda", "na": "muda"},
                     {"tipo": "som", "nome": "riser-curto", "na": "tudo"},
                     {"tipo": "titulo", "texto": "Agora", "na": "agora", "som": False},
                     {"tipo": "efeito", "nome": "checklist", "itens": ["a", "b"], "ini": 0, "fim": 3}],
                    1080, 1920, lambda t: t, pal)
    ev = els.eventos("biblioteca")
    nomes = [n for _, n, _ in ev]
    assert "pop-limpo" in nomes and "riser-curto" in nomes and nomes.count("tique") == 3
    riser = next(t for t, n, _ in ev if n == "riser-curto")
    assert riser == pytest.approx(1.0)  # "tipo": "som" não antecipa: o ápice cai na palavra
    assert all(n == "pop" for _, n, _ in els.eventos("gerado") if n != "riser-curto")


def test_guarda_recusa_som_desconhecido(ativa):
    ativa("pontes_brain")
    with pytest.raises(ErroDeMarca, match="som desconhecido"):
        conferir_edl({"marca": "pontes_brain", "segmentos": [{"transicao": "push", "som": "nao-existe"}], "elementos": []})
    with pytest.raises(ErroDeMarca, match="som desconhecido"):
        conferir_edl({"marca": "pontes_brain", "elementos": [{"tipo": "som", "nome": "trombeta"}]})


def test_mixar_agrupa_por_arquivo():
    ins, fc, rot = mixar_eventos([(0.5, "a.ogg", -6), (1.0, "a.ogg", -6), (2.0, "b.ogg", -3)], 1)
    assert ins == ["-i", "a.ogg", "-i", "b.ogg"]
    assert "asplit=2" in fc and len(rot) == 3 and "adelay=2000|2000" in fc


@pytest.mark.parametrize("tipo", ["giro", "rasgo", "vidro", "luz"])
def test_transicoes_novas(ativa, tipo):
    ativa("pontes_brain")
    a = np.full((480, 270, 3), 30, np.uint8)
    b = np.full((480, 270, 3), 200, np.uint8)
    meio = transicao(a, b, 0.5, tipo, 270, 480)
    assert meio.shape == a.shape and meio.dtype == np.uint8
    assert np.abs(transicao(a, b, 0.97, tipo, 270, 480).astype(int) - b).mean() < 60  # termina no quadro novo
