PY ?= .venv/bin/python

.PHONY: instalar musicas lint testes regressao verificar tudo

instalar:            ## instala tudo no Mac (ffmpeg, Python, modelos)
	bash setup-mac.sh

musicas:             ## baixa as faixas da biblioteca de músicas (≈ 230 MB, fora do Git)
	$(PY) editor.py biblioteca baixar musicas

lint:
	$(PY) -m ruff check .

testes:              ## testes de unidade (rápidos, sem vídeo)
	$(PY) -m pytest

verificar:           ## catálogos, licenças e arquivos das bibliotecas
	$(PY) editor.py biblioteca verificar

regressao:           ## regressão visual + render ponta a ponta de todas as marcas
	$(PY) editor.py testar

tudo: lint testes verificar regressao
