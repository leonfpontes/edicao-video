"""Guarda de marca (motor/guarda.py): o render recusa EDL que misture marcas."""
import pytest

from motor import marca
from motor.guarda import conferir_auditoria, conferir_edl
from motor.marca import ErroDeMarca


def edl_base(mid, **extra):
    e = {"marca": mid, "elementos": [], "cta": {"ativo": False}}
    e.update(extra)
    return e


def test_edl_limpo_passa(ativa):
    ativa("girahub")
    conferir_edl(edl_base("girahub", elementos=[{"tipo": "titulo", "texto": "A fila em paz no portão"},
                                                {"tipo": "objeto3d", "nome": "ticket"},
                                                {"tipo": "efeito", "nome": "confete", "cor": "champanhe"}]))


def test_edl_sem_marca(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca, match="não diz a marca"):
        conferir_edl({"elementos": []})


def test_edl_de_outra_marca(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca, match="é da marca pontes_brain"):
        conferir_edl(edl_base("pontes_brain"))


def test_analise_de_outra_marca(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca, match="análise desta pasta"):
        conferir_edl(edl_base("girahub"), analise={"marca": "pontes_brain"})


@pytest.mark.parametrize("mid,texto,dono", [
    ("girahub", "Mentoria de produto com PDCA", "pontes_brain"),
    ("pontes_brain", "Conheça o GiraHub", "girahub"),
    ("leopontesrp", "link: leopontes.com.br/mentoria-produto", "pontes_brain"),
    ("pontes_brain", "segue o @leopontesrp", "leopontesrp"),
])
def test_texto_com_termo_de_outra_marca(ativa, mid, texto, dono):
    ativa(mid)
    with pytest.raises(ErroDeMarca, match=dono):
        conferir_edl(edl_base(mid, elementos=[{"tipo": "titulo", "texto": texto}]))


def test_cta_com_url_de_outra_marca(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca, match="cta"):
        conferir_edl(edl_base("girahub", cta={"ativo": True, "chamada": "Venha", "url": "leopontes.com.br/mentoria-produto"}))


def test_leo_fora_do_pontes_brain(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca, match="Leo"):
        conferir_edl(edl_base("girahub", elementos=[{"tipo": "leo", "pose": "joinha"}]))
    ativa("pontes_brain")
    conferir_edl(edl_base("pontes_brain", elementos=[{"tipo": "leo", "pose": "joinha"}]))


def test_arquivo_na_pasta_de_outra_marca(ativa):
    ativa("leopontesrp")
    outro = str(marca.pasta_marca("girahub") / "logo.png")
    with pytest.raises(ErroDeMarca, match="pasta da marca girahub"):
        conferir_edl(edl_base("leopontesrp", elementos=[{"tipo": "imagem", "arquivo": outro}]))
    with pytest.raises(ErroDeMarca, match="pasta da marca girahub"):
        conferir_edl(edl_base("leopontesrp", fundo={"tipo": "imagem", "imagem": outro}))


def test_objeto_3d_proprio_de_outra_marca(ativa):
    ativa("girahub")
    with pytest.raises(ErroDeMarca, match="lp"):
        conferir_edl(edl_base("girahub", elementos=[{"tipo": "objeto3d", "nome": "lp"}]))


def test_efeito_com_cor_solta(ativa):
    ativa("pontes_brain")
    with pytest.raises(ErroDeMarca, match="paleta"):
        conferir_edl(edl_base("pontes_brain", elementos=[{"tipo": "efeito", "nome": "confete", "cor": "#E9B04A"}]))


def test_auditoria_pega_arquivo_de_outra_marca(ativa):
    ativa("pontes_brain")
    marca.registrar(marca.pasta_marca("pontes_brain") / "logo.png")
    conferir_auditoria()
    marca.registrar(marca.pasta_marca("girahub") / "logo.png")
    with pytest.raises(ErroDeMarca, match="outra marca"):
        conferir_auditoria()
