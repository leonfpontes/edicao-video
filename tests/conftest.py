"""Configuração comum dos testes: o pacote `motor` é importado da raiz do repositório."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor import marca  # noqa: E402


@pytest.fixture
def ativa():
    """Ativa uma marca para o teste e não deixa estado para o próximo."""
    def _ativar(mid):
        return marca.ativar(mid)
    yield _ativar
    marca.ATIVA.update(id=None, pasta=None)
    marca.CFG.clear()
    marca.CORES.clear()
