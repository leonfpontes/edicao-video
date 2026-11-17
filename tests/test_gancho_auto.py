from motor.diretor import dirigir, montar_gancho


def _ws(frase, t0):
    out, t = [], t0
    for p in frase.split():
        out.append({"t": p, "ini": round(t, 2), "fim": round(t + 0.3, 2), "p": 0.9})
        t += 0.35
    return out


def test_gancho_move_a_frase_forte_e_tira_o_anuncio():
    ws = _ws("Agora eu vou fazer um vídeo mostrando a minha casa.", 0.0) + _ws("Bom, aqui fica a sala de estar.", 5.0) \
        + _ws("Você sabia que nunca ninguém te contou o maior segredo da casa?", 10.0)
    plano = dirigir(ws, db=[0.0] * len(ws))
    assert plano["gancho"].get("sugestao")
    edl = {"segmentos": [{"id": 0, "ini": 0.0, "fim": 15.0, "zoom": 1.0, "transicao": None}], "intro": {"ativo": True}}
    edl = montar_gancho(edl, plano, ws)
    segs = edl["segmentos"]
    assert segs[0]["gancho"] and segs[0]["ini"] >= 9.9
    assert edl["intro"]["apos_gancho"] is True
    assert all(s["ini"] >= 3.0 for s in segs[1:])  # o anúncio do começo saiu
    assert not any(s["ini"] < segs[0]["fim"] and s["fim"] > segs[0]["ini"] for s in segs[1:])  # sem repetir o gancho
