"""Diretor automático: vícios, tomadas repetidas, ênfases, gancho, zooms e elementos sugeridos."""
from motor.diretor import alternar_zoom, aplicar, aplicar_cortes, dirigir, elementos_sugeridos, enfases, frases, nota_gancho, tomadas_repetidas, vicios


def fala(txt, t0=0.0, dur=0.3, pausa=0.05, pausas=None):
    """Palavras com tempos: pausas = {índice: segundos de pausa ANTES da palavra}."""
    out, t = [], t0
    for i, w in enumerate(txt.split()):
        t += (pausas or {}).get(i, 0)
        out.append({"t": w, "ini": round(t, 3), "fim": round(t + dur, 3), "p": 0.9})
        t += dur + pausa
    return out


def test_vicios():
    ws = fala("ãh então o projeto tipo, funciona né")
    ws[-1]["fim"] += 0
    assert {norm(ws, i) for i in vicios(ws)} == {"ãh", "tipo,", "né"}
    assert vicios(fala("eu eu acho que é é isso")) == {0}  # gaguejada sai; "é é" fica (pode ser fala real)
    assert not vicios(fala("um projeto de um ano"))  # "um" é palavra, não vício


def norm(ws, i):
    return ws[i]["t"]


def test_tomada_repetida_fica_a_ultima():
    ws = fala("o segredo do editor é. não, peraí. o segredo do editor é a folha de estilo.", pausa=0.05)
    fr = frases(ws)
    tirar = tomadas_repetidas(ws, fr)
    assert tirar == [(0, 7)]
    plano = dirigir(ws)
    assert all(c[2] == "tomada repetida" for c in plano["cortes"])
    assert plano["cortes"][0][1] <= ws[7]["ini"]


def test_frase_diferente_nao_e_retomada():
    ws = fala("o editor corta as pausas. o motor faz o resto.")
    assert tomadas_repetidas(ws, frases(ws)) == []


def test_aplicar_cortes_divide_o_segmento():
    segs = [{"id": 0, "ini": 0.0, "fim": 5.0, "zoom": 1.0}]
    out = aplicar_cortes(segs, [(1.0, 1.6, "vício"), (3.0, 3.2, "vício")])
    assert [(s["ini"], s["fim"]) for s in out] == [(0.0, 1.04), (1.6, 3.04), (3.2, 5.0)]
    assert [s["id"] for s in out] == [0, 1, 2]


def test_zoom_alterna_nos_jump_cuts():
    segs = [{"ini": 0, "fim": 2}, {"ini": 2.5, "fim": 4}, {"ini": 4.6, "fim": 6}, {"ini": 6.05, "fim": 7}]
    alternar_zoom(segs)
    assert [s["zoom"] for s in segs] == [1.0, 1.08, 1.0, 1.0]
    assert segs[1]["salto"] and segs[2]["salto"] and "salto" not in segs[3]


def test_enfase_prefere_numeros_e_palavras_fortes():
    ws = fala("a gente cresceu 87% em um ano sem nenhum segredo", pausas={9: 0.4})
    esc = [ws[i]["t"] for i, _ in enfases(ws, [0.0] * len(ws), espaco=0.5)]
    assert "87%" in esc and "segredo" in esc and "a" not in esc


def test_gancho():
    ruim, _ = nota_gancho(fala("oi gente tudo bem hoje eu vou falar", dur=0.5, pausa=0.2))
    bom, motivos = nota_gancho(fala("você está perdendo 80% das vendas?", dur=0.25))
    assert bom >= 8 > 4 >= ruim and motivos


def test_gancho_sugere_frase_mais_forte():
    ws = fala("oi gente tudo bem. hoje vou falar de vendas. você sabe por que ninguém compra de você?", dur=0.35)
    g = dirigir(ws)["gancho"]
    assert g["sugestao"]["texto"].startswith("você sabe")


def test_elementos_sugeridos():
    ws = fala("o primeiro passo é instalar o motor e o resultado subiu 40% no mês. fazer assim é errado", pausas={14: 2.0})
    els = elementos_sugeridos(ws, list(range(len(ws))), "tutorial_passos")
    tipos = [(e["tipo"], e.get("nome")) for e in els]
    assert ("passo", None) in tipos and ("efeito", "contador") in tipos and ("efeito", "xis") in tipos
    passo = next(e for e in els if e["tipo"] == "passo")
    assert passo["numero"] == 1 and passo["na"] == "primeiro passo"
    assert next(e for e in els if e.get("nome") == "contador")["ate"] == 40
    outro = elementos_sugeridos(ws, list(range(len(ws))), None)
    assert ("destaque", None) in [(e["tipo"], e.get("nome")) for e in outro]


def test_aplicar_no_rascunho():
    ws = fala("ãh o primeiro passo é instalar o motor e depois é só gravar o vídeo inteiro de uma vez", pausas={1: 0.2})
    edl = {"segmentos": [{"id": 0, "ini": 0.0, "fim": ws[-1]["fim"], "zoom": 1.0, "texto": ""}], "legendas": {"ativo": True},
           "zooms": [], "elementos": []}
    plano = dirigir(ws, estilo="tutorial_passos")
    edl = aplicar(edl, plano, ws)
    assert edl["segmentos"][0]["ini"] >= ws[0]["fim"] - 0.1  # o "ãh" saiu
    assert "ãh" not in edl["segmentos"][0]["texto"]
    assert edl["elementos"] and "_motivo" not in edl["elementos"][0]


def test_um_artigo_nao_e_numero():
    from motor.diretor import numero
    assert numero("um") is None and numero("uma,") is None
    assert numero("um", artigo=True) == 1 and numero("três") == 3 and numero("40%") == 40


def test_abertura_com_anuncio_nao_ganha_ponto_de_numero():
    from motor.diretor import nota_gancho
    ws = [{"t": t, "ini": i * 0.3, "fim": i * 0.3 + 0.25} for i, t in enumerate("Agora eu vou fazer um vídeo mostrando".split())]
    nota, motivos = nota_gancho(ws)
    assert nota < 6 and "número concreto" not in motivos
