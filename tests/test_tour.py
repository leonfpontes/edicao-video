import numpy as np

from motor.analisar import ativar, rascunho_edl
from motor.pausas import aparar_palavras
from motor.tour import capitulos, dirigir_tour, nomes_citados, rotulos


def _ws(frase, t0, passo=0.35):
    out, t = [], t0
    for p in frase.split():
        out.append({"t": p, "ini": round(t, 2), "fim": round(t + 0.3, 2), "p": 0.9})
        t += passo
    return out


# ───────────────────────────── pausas pelo áudio ─────────────────────────────
def test_palavra_esticada_sobre_silencio_acaba_no_audio():
    db = np.full(600, -55.0)  # 6 s de silêncio de fundo, a 10 ms
    db[100:140] = -20  # "algumas" falado de 1,0 a 1,4 s
    db[400:440] = -20  # próxima palavra em 4,0 s
    ws = [{"t": "algumas", "ini": 1.0, "fim": 4.0, "p": 0.9}, {"t": "coisas", "ini": 4.0, "fim": 4.4, "p": 0.9}]
    novas, n = aparar_palavras(ws, db)
    assert n == 1
    assert 1.35 <= novas[0]["fim"] <= 1.5 and novas[1] == ws[1]


def test_palavra_que_comeca_depois_do_silencio():
    db = np.full(400, -55.0)
    db[250:290] = -20
    novas, n = aparar_palavras([{"t": "tenho", "ini": 1.0, "fim": 2.9, "p": 0.9}], db)
    assert n == 1 and 2.4 <= novas[0]["ini"] <= 2.5


def test_palavra_normal_nao_muda():
    db = np.full(300, -20.0)
    ws = [{"t": "firmeza", "ini": 1.0, "fim": 1.6, "p": 0.9}]
    assert aparar_palavras(ws, db) == (ws, 0)


def test_rascunho_corta_a_pausa_no_meio_da_palavra():
    ativar("girahub")
    ws = [{"t": "algumas", "ini": 1.0, "fim": 4.0, "p": 0.9, "pausa": [1.5, 3.5]}, {"t": "coisas", "ini": 4.0, "fim": 4.4, "p": 0.9}]
    segs = rascunho_edl("x.mov", ws, dur=5.0)["segmentos"]
    assert len(segs) == 2 and segs[0]["fim"] < 1.7 and segs[1]["ini"] > 3.3


# ───────────────────────────── nomes, capítulos e rótulos ─────────────────────────────
def test_nomes_citados_com_lista_e_titulos():
    ws = _ws("Aqui eu tenho uma firmeza de baiano, quartinha de anjo de guarda e minha firmeza de seu Zé.", 0.0)
    nomes = {(x["sobre"], x["nome"]) for x in nomes_citados(ws) if x["forma"] == "de"}
    assert ("firmeza de", "Baiano") in nomes
    assert ("quartinha de", "Anjo de guarda") in nomes
    assert ("firmeza de", "seu Zé") in nomes


def test_nomes_aplicam_correcoes_e_para():
    ws = _ws("tenho as minhas firmezas de echu e uma firmeza aqui para a prosperidade", 0.0)
    nomes = {(x["sobre"], x["nome"]) for x in nomes_citados(ws, {"echu": "Exu"}) if x["forma"] == "de"}
    assert ("firmezas de", "Exu") in nomes
    assert ("firmeza para a", "prosperidade") in nomes  # "para quê" não ganha maiúscula


def _cena(trocas):
    """Assinatura de cor por segundo: cada cômodo com uma cor."""
    out, cor = [], 0
    for t in range(0, 60):
        if t in trocas:
            cor += 90
        out.append([float(t)] + [cor] * 48)
    return {"assinaturas": out, "apontar": [{"tipo": "aponta_objeto", "ini": 24.6, "fim": 25.8, "trilha": [[25.0, 0.7, 0.4]]}]}


def _video_tour():
    ws = (_ws("Bom, esse cantinho aqui fica do lado do meu escritório.", 0.5)
          + _ws("Aqui eu tenho minhas guias e um pouco de tudo.", 6.0)
          + _ws("Voltando pra cá, eu tenho um congá singelo.", 20.0)
          + _ws("Aqui eu tenho uma firmeza de caboclo bem bonita.", 24.0)
          + _ws("Vamos seguir. Aqui na sala tem mais coisa.", 40.0)
          + _ws("Isso é tudo o que eu queria mostrar hoje.", 52.0))
    segs = [{"id": k, "ini": a, "fim": b, "zoom": 1.0, "transicao": None}
            for k, (a, b) in enumerate([(0.4, 4.3), (5.9, 9.4), (19.9, 23.0), (23.9, 27.5), (39.9, 43.1), (51.9, 55.2)])]
    return ws, segs


def test_capitulos_por_comodo_com_titulo():
    ws, segs = _video_tour()
    caps = capitulos(_cena({20, 40}), ws, segs)
    assert [c["titulo"] for c in caps] == ["O cantinho", "O congá", "A sala"]
    assert [c["seg"] for c in caps] == [0, 2, 4]


def test_rotulo_preso_ao_dedo():
    ws, segs = _video_tour()
    r = rotulos(_cena({20, 40}), ws, segs)
    assert len(r) == 1
    assert r[0]["texto"] == "firmeza de/Caboclo" and r[0]["fixar"][1:] == [0.7, 0.4] and r[0]["sem_legenda"]


def test_dirigir_tour_poe_passos_transicao_e_nao_cobre_texto():
    ws, segs = _video_tour()
    edl = {"segmentos": segs, "elementos": [{"tipo": "titulo", "texto": "Já existe", "ini": 24.0, "fim": 27.0}], "legendas": {}}
    edl, linhas = dirigir_tour(_cena({20, 40}), ws, edl)
    passos = [e for e in edl["elementos"] if e["tipo"] == "passo"]
    assert [p["numero"] for p in passos] == [1, 2, 3]
    assert segs[2]["transicao"] == "luz" and segs[0]["transicao"] is None
    assert not any(e["tipo"] == "anotacao" for e in edl["elementos"])  # o título que já estava ganha
    assert all(not k.startswith("_") for e in edl["elementos"] for k in e)
    assert any("capítulo 2" in x for x in linhas)
