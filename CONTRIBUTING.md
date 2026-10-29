# Como contribuir

1. Crie uma branch a partir da `main` atualizada.
2. Prepare o ambiente: `bash setup-mac.sh` (Mac) ou `pip install -r requirements-dev.txt` com ffmpeg instalado.
3. Faça a mudança seguindo o [CLAUDE.md](CLAUDE.md) e o [AGENTS.md](AGENTS.md).
4. Rode `make tudo`. Precisa passar inteiro: ruff, pytest, `biblioteca verificar` e `editor.py testar` em `TUDO OK`.
5. Mudança visual intencional: `editor.py testar --marca <marca> --atualizar` e a folha nova no PR. Regere as imagens do
   README com `python ferramentas/gerar_imagens_readme.py` se algo visível mudou.
6. Atualize o [CHANGELOG.md](CHANGELOG.md), a documentação em `docs/` e as skills afetadas.
7. Abra o PR com o template e marque as marcas afetadas.

## Estilo

- Português em nomes, comentários, mensagens e docs, em frases completas.
- Python 3.11+, linhas até 160 colunas, imports ordenados (`ruff check --fix`).
- Sem dependência nova sem necessidade. Rede só com `urllib`.

## Acrescentar à biblioteca

- **3D**: `editor.py biblioteca baixar 3d "<Nome no Fluent>"` ou edite `ferramentas/montar_3d.py`.
- **Música**: edite a curadoria em `ferramentas/montar_musicas.py` (só licença livre) e rode o script.
- **Efeito**: nova classe com `@efeito(...)` em `motor/efeitos.py`, depois `editor.py biblioteca catalogo`.

Detalhes em [docs/bibliotecas.md](docs/bibliotecas.md).
