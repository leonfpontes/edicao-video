# Changelog

## 2.0.0 (2026-10-29)

Repositório profissionalizado, com bibliotecas compartilhadas e isolamento entre marcas.

### Novo

- **Isolamento entre marcas**: `--marca` obrigatório (sem padrão), pasta por marca com sandbox de arquivos, vinhetas,
  fundos e Leo com dono, termos exclusivos por marca, guarda do EDL (`motor/guarda.py`), auditoria dos arquivos abertos,
  selo da marca nos metadados do vídeo e `editor.py conferir`.
- **Biblioteca 3D**: 167 objetos (119 renders do Fluent Emoji 3D, 48 logos extrudados do Simple Icons), com busca.
- **Biblioteca de músicas**: 35 faixas reais CC BY 4.0, com clima, energia, BPM, gênero, instrumentos e crédito;
  download conferido por sha256 e `creditos.txt` no render.
- **Biblioteca de efeitos**: 20 layers procedurais na paleta da marca (luz, textura, impacto, celebração, anotação,
  informação), ancorados na fala.
- `editor.py marcas`, `editor.py biblioteca listar|baixar|verificar|previa|catalogo`.
- `manifesto.json` em todo render.
- Testes de unidade (pytest), CI no GitHub Actions, Makefile, `pyproject.toml`.
- README vitrine, CLAUDE.md, AGENTS.md, CONTRIBUTING.md e docs/.

### Mudou

- `editor.py` virou o pacote `motor/` (mesmo visual, regressão com diferença 0,00 em todas as marcas).
- `marcas/<id>.json` → `marcas/<id>/marca.json`, com os arquivos da marca ao lado.
- `assets/` dividido entre `marcas/<id>/` (identidade) e `biblioteca/` (compartilhado).
- Skills em `skills/<skill>/SKILL.md`.
- Música no EDL por `"faixa"` (id do catálogo); `"arquivo"` antigo continua funcionando.
- `musica_obrigatoria` → `"musica": {"politica": "proibida" | "opcional" | "obrigatoria"}`. O @pontes_brain passa a
  recusar música no vídeo (o Leonardo põe a música no Instagram).

### Removido

- `PROMPT-MESTRE.md` e `PROMPT-instagram-pessoal.md` (duplicavam as skills).
- `assets/musicas/` (as faixas agora vêm da biblioteca).

## 1.x

Editor de arquivo único para @pontes_brain, depois GiraHub e @leopontesrp.
