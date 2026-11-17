"""Entrega: SRT, entrada da agenda do insta_report, envio para o clone e b-roll do Pexels (sem rede)."""
import json

import pytest

from motor import banco
from motor.exportar import _tempo_srt, entrada_agenda, enviar_insta_report


class Ctx:
    pass


def test_tempo_srt():
    assert _tempo_srt(0) == "00:00:00,000" and _tempo_srt(3723.456) == "01:02:03,456"


def test_entrada_agenda(ativa):
    ativa("pontes_brain")
    e = entrada_agenda(Ctx(), "2026-11-20T19:00:00-03:00", "legenda", "título")
    assert e["id"] == "pb-1120-1900" and e["conta"] == "pontes_brain" and e["formato"] == "reel"
    assert e["midia"] == ["midia/pb-1120-1900.mp4"] and e["status"] == "agendado"
    ativa("leopontesrp")
    assert entrada_agenda(Ctx(), "2026-11-20T19:00:00-03:00", "", "")["midia"][0].startswith("midia/leopontesrp/")
    with pytest.raises(SystemExit):
        entrada_agenda(Ctx(), "2026-11-20T19:00:00", "", "")


def test_enviar_insta_report_acrescenta_no_fim(ativa, tmp_path):
    ativa("pontes_brain")
    raiz = tmp_path / "insta"
    (raiz / "instagram").mkdir(parents=True)
    agenda = {"contas": {"pontes_brain": {}}, "posts": [{"id": "pb-1120-1900", "conta": "pontes_brain"}]}
    (raiz / "instagram" / "agenda.json").write_text(json.dumps(agenda, ensure_ascii=False, indent=1) + "\n")
    video = tmp_path / "v"
    video.mkdir()
    (video / "reel.mp4").write_bytes(b"mp4")
    (video / "capa.jpg").write_bytes(b"jpg")
    e = enviar_insta_report(entrada_agenda(Ctx(), "2026-11-20T19:00:00-03:00", "x", "t"), video, raiz)
    assert e["id"] == "pb-1120-1900b"  # id repetido ganha sufixo
    d = json.loads((raiz / "instagram" / "agenda.json").read_text())
    assert d["posts"][-1]["id"] == "pb-1120-1900b" and len(d["posts"]) == 2
    assert (raiz / "instagram" / e["midia"][0]).read_bytes() == b"mp4"


def test_pexels_escolhe_o_vertical(monkeypatch, tmp_path):
    resposta = {"videos": [{"id": 7, "url": "https://pexels.com/v/7", "duration": 9, "user": {"name": "Ana"},
                            "video_files": [{"width": 1920, "height": 1080, "link": "h"}, {"width": 1080, "height": 1920, "link": "v1080"},
                                            {"width": 2160, "height": 3840, "link": "v4k"}]}]}
    pedidos = []

    def falso(url, chave, timeout=30):
        pedidos.append(url)
        return json.dumps(resposta).encode() if "search" in url else b"video"
    monkeypatch.setattr(banco, "_get", falso)
    ops = banco.buscar("reunião", chave="k")
    assert ops[0]["link"] == "v1080" and "orientation=portrait" in pedidos[0]
    arq = banco.baixar(ops[0], tmp_path, chave="k")
    assert arq.read_bytes() == b"video" and json.load(open(arq.with_suffix(".json")))["licenca"].startswith("Pexels")


def test_pexels_sem_chave(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        banco.chave_api()
