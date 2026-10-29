"""Catálogos das bibliotecas compartilhadas (3D, músicas, efeitos)."""
import json

import pytest

from motor import bibliotecas as bib
from motor.config import BIBLIOTECA
from motor.efeitos import catalogo_efeitos
from motor.marca import ErroDeMarca, listar_marcas


@pytest.mark.parametrize("qual", ["3d", "musicas"])
def test_ids_unicos_e_licencas_livres(qual):
    ids = [it["id"] for it in bib.itens(qual)]
    assert len(ids) == len(set(ids))
    for it in bib.itens(qual):
        assert it["licenca"] in bib.LICENCAS_LIVRES, it["id"]
        assert set(it.get("marcas", [])) <= set(listar_marcas()), it["id"]


def test_arquivos_3d_existem():
    for it in bib.itens("3d"):
        assert (BIBLIOTECA / "3d" / it["arquivo"]).exists(), it["id"]


def test_3d_tem_renders_e_logos():
    tipos = {it["tipo"] for it in bib.itens("3d")}
    assert {"render", "extrusao"} <= tipos
    assert len(bib.itens("3d")) >= 150


def test_musicas_bem_tagueadas():
    faixas = bib.itens("musicas")
    assert len(faixas) >= 30
    for it in faixas:
        for campo in ("titulo", "artista", "genero", "clima", "energia", "credito", "url", "sha256", "duracao_txt"):
            assert it.get(campo), (it["id"], campo)
        assert it.get("bpm") or it.get("bpm_fonte") == "livre", it["id"]
        assert it["artista"] in it["credito"]


def test_buscar_musica_por_clima():
    calmas = bib.buscar("musicas", clima="calmo")
    assert calmas and all("calmo" in it["clima"] for it in calmas)


def test_faixa_desconhecida_e_erro(ativa):
    ativa("pontes_brain")
    with pytest.raises(ErroDeMarca):
        bib.musica_do_edl({"faixa": "nao-existe"})


def test_musica_propria_sem_licenca_e_recusada(ativa, tmp_path):
    ativa("pontes_brain")
    mp3 = tmp_path / "minha.mp3"
    mp3.write_bytes(b"x")
    with pytest.raises(ErroDeMarca):
        bib.musica_do_edl({"arquivo": str(mp3)})


def test_politica_proibida_e_obrigatoria(ativa):
    ativa("leopontesrp")  # música obrigatória
    with pytest.raises(ErroDeMarca):
        bib.musica_do_edl(None)


def test_objeto_3d_proprio_da_marca(ativa):
    ativa("pontes_brain")
    assert bib.objeto_3d("lp")
    ativa("girahub")
    assert bib.objeto_3d("ticket")
    with pytest.raises(ErroDeMarca):
        bib.objeto_3d("lp")
    assert bib.objeto_3d("claude")  # compartilhado serve a todas


def test_catalogo_de_efeitos_em_dia():
    gravado = json.loads((BIBLIOTECA / "efeitos" / "catalogo.json").read_text())["itens"]
    assert gravado == json.loads(json.dumps(catalogo_efeitos(), ensure_ascii=False))


def test_item_pelo_nome_em_ingles():
    assert bib.item("3d", "rocket")["id"] == "foguete"
