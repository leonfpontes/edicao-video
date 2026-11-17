"""Leitura da cena e direção a partir dela (sem vídeo: dados sintéticos)."""
import numpy as np

from motor.cena import _juntar, aplicar_cena, cabeca, camera, dirigir_cena


def test_juntar_gestos_em_eventos():
    am = [(0.1 * k, "dedo_cima", 0.5, 0.4) for k in range(10)] + [(3.0, "joinha", 0.4, 0.5)]
    ev = _juntar(am, "tipo")
    assert len(ev) == 1 and ev[0]["tipo"] == "dedo_cima" and len(ev[0]["trilha"]) == 10


def test_aceno_sim_pela_inclinacao():
    rostos = [[0.1 * k, 0.5, 0.4, 0.3, 0.12 + 0.09 * np.sin(k * 0.6), 0.0] for k in range(40)]
    ev = cabeca(rostos)
    assert ev and ev[0]["tipo"] == "aceno_sim"


def test_giro_da_camera_com_trilha():
    passos = [[0.1 * k, -0.04, 0.0] for k in range(30)]  # a imagem corre para a esquerda 1,2 tela em 3 s
    ev = camera(passos, [], 3.0)
    assert ev[0]["tipo"] == "giro" and ev[0]["trilha"][-1][1] < 0


def test_direcao_segue_o_gesto_e_respeita_texto():
    cena = {"gestos": [{"tipo": "dedo_cima", "ini": 1.0, "fim": 2.0, "trilha": [[1.0, 0.5, 0.4], [2.0, 0.6, 0.3]]},
                       {"tipo": "aponta_camera", "ini": 4.0, "fim": 5.0, "trilha": [[4.0, 0.5, 0.5]]}],
            "cabeca": [], "camera": [], "com_rosto": [round(0.1 * k, 1) for k in range(60)]}
    segs = [{"id": 0, "ini": 0.0, "fim": 6.0}]
    pc = dirigir_cena(cena, [], segs)
    nomes = [e["nome"] for e in pc["elementos"]]
    assert nomes == ["brilhos", "ondas"] and all("seguir" in e for e in pc["elementos"])
    assert pc["zooms"][0]["modo"] == "punch"
    assert dirigir_cena(cena, [], segs, calmo=True)["zooms"][0]["modo"] == "suave"
    edl = aplicar_cena({"segmentos": segs, "elementos": [{"tipo": "efeito", "nome": "check", "ini": 1.2, "fim": 1.8}]}, pc)
    assert [e.get("nome") for e in edl["elementos"]] == ["check", "ondas"]  # marcação não cobre marcação


def test_mao_sem_rosto_nao_vira_efeito_em_marca_calma():
    cena = {"gestos": [{"tipo": "joinha_baixo", "ini": 1.0, "fim": 2.0, "trilha": [[1.0, 0.5, 0.4]]}],
            "cabeca": [], "camera": [], "com_rosto": []}
    assert dirigir_cena(cena, [], [{"id": 0, "ini": 0, "fim": 5}])["elementos"] == []
