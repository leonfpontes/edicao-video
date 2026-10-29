# CLAUDE.md

Guia para agentes de IA (Claude Code e similares) neste repositório. Leia inteiro antes de editar um vídeo ou mexer no
código. Os papéis e as regras comuns a qualquer agente estão em [AGENTS.md](AGENTS.md); este arquivo acrescenta o que é
específico do Claude Code.

## O que é

Editor de vídeo automático e multimarca. Você grava falando para a câmera; o agente decide cortes, efeitos e música num
`edl.json` e o motor renderiza o Reel com a identidade da marca. Dono: Leonardo Pontes. Marcas: `pontes_brain`
(@pontes_brain), `girahub` (GiraHub, @girahuboficial) e `leopontesrp` (@leopontesrp). `modelo` é o molde para marca nova.

## Antes de tudo

- **Descubra a marca** do vídeo. Na dúvida, pergunte. Nunca chute: não existe marca padrão e a escolha errada é o pior
  erro possível aqui.
- **Use a skill da marca**: `skills/editor-video-<marca>/SKILL.md` (no Claude Code, as skills `editor-video-pontes-brain`,
  `editor-video-girahub` e `editor-video-leopontesrp`). Uma skill por marca; nunca use a de outra.
- Sem `.venv`? `bash setup-mac.sh`. Sem músicas baixadas? `make musicas`.

## Regras que não se quebram

1. **Uma marca por vídeo.** `analisar --marca <marca>` numa pasta própria. O `edl.json` leva `"marca"`. Nada de uma marca
   (cores, logo, vinheta, Leo, termos, CTA, arquivos de `marcas/<outra>/`) entra no vídeo de outra. A guarda recusa; não
   tente contorná-la.
2. **Confira antes de entregar**: abra `previa.jpg`, extraia quadros de cada corte e elemento, meça o áudio e rode
   `editor.py conferir final.mp4 --marca <marca>`. Só entregue com "confere".
3. **Efeito só com motivo na fala**, entrando na palavra exata (`na`) e saindo quando a ideia termina (`ate`).
4. **Música só da biblioteca** (ou com licença livre e crédito no EDL), respeitando a política da marca. Nunca sintetize
   música. Mande o crédito de `creditos.txt` junto com a legenda do post.
5. **Não invente fala** nem mude o sentido do que foi dito. Não publique nada: a publicação é do Leonardo.
6. **Identidade é da marca.** Logo, vinheta, mascote e objetos próprios ficam em `marcas/<id>/`, nunca em `biblioteca/`.
7. **Nada de segredo no repositório**: sem tokens, senhas ou vídeos brutos do Leonardo.

## Comandos

```bash
.venv/bin/python editor.py analisar VIDEO [VIDEO2 …] --marca <marca> [--pasta P] [--sem-fala] [--estabilizar]
.venv/bin/python editor.py renderizar P/edl.json [--rapido] [--so-audio]
.venv/bin/python editor.py conferir P/final.mp4 --marca <marca>
.venv/bin/python editor.py marcas
.venv/bin/python editor.py biblioteca listar 3d|musicas|efeitos [termo] [--marca X] [--clima …] [--json]
.venv/bin/python editor.py testar [--marca X] [--atualizar] [--so-visual]
make lint testes verificar regressao
```

## Mexer no código

- Leia [docs/arquitetura.md](docs/arquitetura.md) e o doc da peça: [edl](docs/edl.md), [marcas](docs/marcas.md),
  [bibliotecas](docs/bibliotecas.md), [testes](docs/testes.md).
- Código em português (nomes, comentários, mensagens), no estilo do arquivo. Linhas até 160 colunas. Sem dependência
  nova sem necessidade; scripts de rede usam só `urllib`.
- Toda leitura de arquivo de marca passa por `arquivo_marca()`; todo arquivo de biblioteca aberto no render passa por
  `registrar()`. Cor de efeito é papel da paleta, nunca hex. Efeitos usam `self.rng_quadro(dt)`, nunca `random`.
- Antes do PR: `make tudo` (ruff, pytest, `biblioteca verificar`, `editor.py testar` terminando em `TUDO OK`).
- Mudança visual intencional: `editor.py testar --marca <marca> --atualizar` só na marca que mudou, e a folha nova no PR.
- Mudou algo visível? Regere as imagens do README: `python ferramentas/gerar_imagens_readme.py`.
- Efeito novo: `editor.py biblioteca catalogo` para atualizar `biblioteca/efeitos/catalogo.json`.
- Atualize o [CHANGELOG.md](CHANGELOG.md) e, se mudou o EDL ou um comando, as três skills.

## Git

Branch a partir da `main`, commits pequenos e descritivos em português, PR com o template. Nada de force-push na `main`.
A `main` é o que o Leonardo usa no Mac (`~/Documents/Dev/edicao-video`).
