import json
from pathlib import Path

import pytest

from motor import criar3d


def test_slug():
    assert criar3d.slug("Balão de fala!") == "balao-de-fala"


def test_cria_por_emoji_sem_rede(tmp_path, monkeypatch):
    if not any(Path(f).exists() for f in criar3d.FONTES_EMOJI):
        pytest.skip("sem fonte de emoji colorido nesta máquina")
    (tmp_path / "3d").mkdir()
    cat = tmp_path / "3d" / "catalogo.json"
    cat.write_text(json.dumps({"itens": []}))
    monkeypatch.setattr(criar3d, "BIBLIOTECA", tmp_path)
    monkeypatch.setattr(criar3d, "CATALOGO", cat)
    monkeypatch.setattr(criar3d, "de_fluent", lambda *a, **k: None)  # sem rede
    iid, como = criar3d.criar_3d("coco", emoji="🥥", tags=["teste"])
    assert (iid, como) == ("coco", "emoji extrudado")
    assert (tmp_path / "3d" / "criados" / "coco.png").exists()
    item = json.loads(cat.read_text())["itens"][0]
    assert item["licenca"] == "OFL 1.1" and item["arquivo"] == "criados/coco.png"


def test_sem_caminho_explica(monkeypatch):
    monkeypatch.setattr(criar3d, "de_fluent", lambda *a, **k: None)
    iid, motivo = criar3d.criar_3d("coisa-que-nao-existe-xyz")
    assert iid is None and "emoji" in motivo
