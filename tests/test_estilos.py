"""Estilos de edição: presets, planos, looks, motion de interface, tela em perspectiva e a guarda dos campos novos."""
import numpy as np
import pytest

from motor.estilos import LOOKS, PRESETS, aplicar_estilo, aplicar_look, fonte_estilo
from motor.guarda import conferir_edl, textos_do_edl
from motor.marca import ErroDeMarca
from motor.motion import TIPOS, HudRosto, RotuloSom, criar
from motor.perspectiva import TelaPerspectiva, bolha, camera_em
from motor.planos import Palco, compor, legenda_y

W, H = 540, 960

EXEMPLOS = {
    "passo": {"numero": 2, "texto": "Instala as ferramentas"},
    "digitacao": {"texto": "Editor de vídeo com IA", "caixa": True},
    "janela": {"titulo": "Como posso ajudar?", "linhas": ["Corta toda pausa maior que [[0,15 s]].", "Segue a folha de estilo."]},
    "arvore": {"raiz": "Editor", "filhos": ["Bruto", "Referências", "Prontos"]},
    "mapa": {"centro": "Editor", "itens": ["Passo 1. Monta", "Passo 2. Instala", "Passo 3. Trava", "Passo 4. Grava"]},
    "comentario": {"texto": "MOTION"},
    "icone": {"nome": "pasta", "rotulo": "Vídeo bruto"},
    "titulo_caixa": {"texto": "Uma empresa inteira / com IA"},
    "titulo_editorial": {"partes": [{"t": "O ESTILO"}, {"t": "das"}, {"t": "PALAVRAS"}], "numero": 1},
    "bilhete": {"texto": "COMPLETAMENTE"},
    "anotacao": {"texto": "+ E NÃO SÃO", "cor": "champanhe"},
    "neon": {"texto": "CLICA EM / SAIBA MAIS"},
    "texto_atras": {"texto": "PALAVRAS"},
}
SPRITES = sorted(EXEMPLOS)


def sprite(tp, dt=1.2, rest=2.0):
    return criar(dict({"tipo": tp}, **EXEMPLOS[tp]), W, H, 3).render(dt, rest)


def test_todo_tipo_tem_exemplo():
    assert set(TIPOS) - {"hud_rosto", "carrossel"} == set(EXEMPLOS)


@pytest.mark.parametrize("tp", SPRITES)
def test_motion_desenha_e_e_deterministico(ativa, tp):
    ativa("pontes_brain")
    a = sprite(tp)
    assert a.ndim == 3 and a.shape[2] == 4 and a[..., 3].max() > 0, tp
    assert np.array_equal(a, sprite(tp))


@pytest.mark.parametrize("tp", SPRITES)
def test_motion_usa_a_paleta(ativa, tp):
    ativa("pontes_brain")
    a = sprite(tp)
    ativa("girahub")
    b = sprite(tp)
    assert a.shape != b.shape or not np.array_equal(a, b), tp


def test_motion_recusa_hex(ativa):
    ativa("modelo")
    with pytest.raises(ErroDeMarca):
        criar({"tipo": "neon", "texto": "oi", "cor": "#ff0000"}, W, H)


def test_texto_atras_cabe_na_tela(ativa):
    ativa("modelo")
    a = criar({"tipo": "texto_atras", "texto": "PALAVRAS ENORMES DEMAIS", "tam": 0.5}, W, H).render(2, 2)
    assert a.shape[1] <= W


def test_hud_e_rotulo_de_som(ativa):
    ativa("modelo")
    f = np.full((H, W, 3), 60, np.uint8)
    HudRosto({"rotulo": "RASTREAMENTO"}, W, H).desenhar(f, 0.8, 1.0, (W / 2, H * 0.35, H * 0.15))
    assert np.abs(f.astype(int) - 60).sum() > 0
    assert RotuloSom({"rotulo": "WHOOSH"}, W, H).render(0.2, 0.6)[..., 3].max() > 0


def test_planos(ativa):
    ativa("modelo")
    palco = Palco(W, H)
    rosto = np.full((H, W, 3), 200, np.uint8)
    assert compor("rosto", rosto, palco.quadro, W, H) is rosto
    m = compor("motion", rosto, palco.quadro, W, H)
    assert np.array_equal(m, palco.quadro)
    d = compor("dividido", rosto, palco.quadro, W, H)
    assert np.array_equal(d[H // 2 + 4:], rosto[:H - H // 2 - 4]) or (d[H // 2 + 4:] == 200).all()
    assert np.array_equal(d[:H // 2 - 2], palco.quadro[:H // 2 - 2])
    assert legenda_y("dividido", 0.68, {}) == 0.5 and legenda_y("rosto", 0.68, {}) == 0.68
    with pytest.raises(ValueError):
        compor("outro", rosto, palco.quadro, W, H)


@pytest.mark.parametrize("look", sorted(LOOKS))
def test_looks(ativa, look):
    ativa("pontes_brain")
    rng = np.random.default_rng(1)
    f = rng.integers(0, 255, (96, 54, 3), np.uint8)
    alfa = np.zeros((96, 54, 1), np.float32)
    alfa[30:70, 15:40] = 1
    out = aplicar_look(f, look, alfa)
    assert out.shape == f.shape and out.dtype == np.uint8 and not np.array_equal(out, f)


def test_look_adesivo_exige_recorte(ativa):
    ativa("modelo")
    with pytest.raises(ErroDeMarca):
        aplicar_look(np.zeros((10, 10, 3), np.uint8), "adesivo")


def test_preset_por_baixo_do_edl():
    edl = aplicar_estilo({"estilo": "tutorial_passos", "legendas": {"posicao_y": 0.7}})
    assert edl["legendas"]["estilo"] == "limpa" and edl["legendas"]["posicao_y"] == 0.7
    assert aplicar_estilo({"x": 1}) == {"x": 1}
    with pytest.raises(ErroDeMarca):
        aplicar_estilo({"estilo": "nao_existe"})
    assert set(PRESETS) == {"tutorial_passos", "tela_perspectiva", "vitrine"}


def test_fontes_de_estilo(ativa):
    ativa("modelo")
    for papel in ("serifa_italica", "serifa", "condensada", "mono", "manuscrita", "sans"):
        assert fonte_estilo(papel, 40).getlength("Passo") > 0
    with pytest.raises(ErroDeMarca):
        fonte_estilo("gotica", 40)


def test_perspectiva_e_bolha(ativa):
    ativa("modelo")
    tela = np.full((300, 480, 3), 230, np.uint8)
    tp = TelaPerspectiva({"foco": 0.5}, W, H)
    q0, q1 = tp.quadro(tela, 0.0), tp.quadro(tela, 1.0)
    assert q0.shape == (H, W, 3) and not np.array_equal(q0, q1)
    assert camera_em(None, 0.5)["zoom"] > camera_em(None, 0.0)["zoom"]
    base = np.zeros((H, W, 3), np.uint8)
    out = bolha(base.copy(), np.full((H, W, 3), 180, np.uint8), {"x": 0.3, "y": 0.8, "raio": 0.15}, W, H)
    assert out[int(H * 0.8), int(W * 0.3)].mean() > 150


def test_guarda_campos_novos(ativa):
    ativa("pontes_brain")
    edl = {"marca": "pontes_brain", "estilo": "vitrine",
           "segmentos": [{"ini": 0, "fim": 1, "plano": "dividido", "look": "pb"}],
           "elementos": [{"tipo": "mapa", "centro": "x", "itens": ["girahub"]}]}
    with pytest.raises(ErroDeMarca, match="girahub"):
        conferir_edl(edl)
    edl["elementos"] = [{"tipo": "neon", "texto": "oi", "cor": "#00ff00"}]
    with pytest.raises(ErroDeMarca, match="paleta"):
        conferir_edl(edl)
    edl["elementos"] = []
    edl["segmentos"][0]["plano"] = "lateral"
    with pytest.raises(ErroDeMarca, match="plano"):
        conferir_edl(edl)
    edl["segmentos"][0]["plano"] = "motion"
    conferir_edl(edl)
    assert ("elementos[0].linhas[1]", "b") in textos_do_edl({"elementos": [{"tipo": "janela", "linhas": ["a", "b"]}]})


def test_legenda_quebra_por_sentido(ativa):
    from motor.legendas import Legendas
    ativa("modelo")
    pal = [{"t": w, "ini": 0.3 * i, "fim": 0.3 * i + 0.28, "p": 1} for i, w in enumerate("o editor de vídeo corta tudo sozinho".split())]
    lg = Legendas(pal, {"palavras_por_bloco": 3}, W, H, [(0, 99)])
    assert [" ".join(w["t"] for w in b) for b in lg.blocos][0] == "o editor de vídeo"  # não termina em "de"
    sem = Legendas(pal, {"palavras_por_bloco": 3, "quebra_sentido": False}, W, H, [(0, 99)])
    assert len(sem.blocos[0]) == 3


def test_legenda_emoji(ativa):
    from motor.legendas import Legendas
    ativa("pontes_brain")
    pal = [{"t": w, "ini": 0.3 * i, "fim": 0.3 * i + 0.28, "p": 1} for i, w in enumerate("isso dá muito dinheiro".split())]
    lg = Legendas(pal, {"emoji": True}, W, H, [(0, 99)])
    bi = lg.bloco_em(1.0)
    assert lg.emoji(bi, 0.5) is None and lg.emoji(bi, 1.3).shape[2] == 4
    assert Legendas(pal, {}, W, H, [(0, 99)]).emoji(bi, 1.3) is None
