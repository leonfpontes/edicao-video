"""Caminhos e constantes do editor."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # pasta do repositório
MARCAS = RAIZ / "marcas"  # uma pasta por marca: marcas/<id>/marca.json + arquivos da marca
BIBLIOTECA = RAIZ / "biblioteca"  # o que é de todas as marcas: fontes, 3D, músicas, efeitos
FONTES_DIR = BIBLIOTECA / "fontes"
MODELOS = RAIZ / "modelos"  # redes de recorte, rosto e ruído
TESTES = RAIZ / "testes"

FPS = 30
FORMATOS = {"vertical": (1080, 1920), "feed": (1080, 1350), "horizontal": (1920, 1080)}
