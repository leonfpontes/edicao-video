from motor.legendas import Legendas


def test_correcao_com_pontuacao_colada():
    pal = [{"t": "de", "ini": 0.0, "fim": 0.2}, {"t": "echu,", "ini": 0.2, "fim": 0.6}, {"t": "fá.", "ini": 0.7, "fim": 1.0}]
    leg = Legendas(pal, {"correcoes": {"echu": "Exu", "fá": "Ifá"}}, 1080, 1920, [(0, 2)])
    textos = [w["t"] for b in leg.blocos for w in b]
    assert "Exu" in textos and "Ifá" in textos
