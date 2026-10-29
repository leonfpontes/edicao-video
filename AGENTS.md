# AGENTS.md

Regras para qualquer agente de IA (Claude Code, Codex, Cursor…) que trabalhe neste repositório. O Claude Code lê também
o [CLAUDE.md](CLAUDE.md).

## Papéis

Um trabalho de edição passa por quatro papéis. Um único agente pode fazer todos, mas precisa cumprir cada um.

### 1. Editor (por marca)

Transforma o vídeo bruto num Reel pronto. Segue a skill da marca, à risca:

| Marca | Skill | Pontos da marca |
|---|---|---|
| `pontes_brain` | `skills/editor-video-pontes-brain/SKILL.md` | Vinheta PDCA/LP de 2,2 s sempre; CTA para leopontes.com.br/mentoria-produto; Leo só com contexto; logos 3D do Claude e do ChatGPT quando falar de IA; sem música |
| `girahub` | `skills/editor-video-girahub/SKILL.md` | Vinheta do ticket; CTA para girahub.com.br; sem Leo; respeito à religiosidade (nada de atabaque ou ponto cantado como trilha) |
| `leopontesrp` | `skills/editor-video-leopontesrp/SKILL.md` | Instagram pessoal; sem logo, vinheta, CTA ou marca d'água; música real obrigatória; vários clipes do dia a dia |

Regras comuns a todas as marcas: recorte de fundo limpo; efeito na palavra certa; enquadramento contínuo entre cortes;
áudio em −16 LUFS com limitador, sem estourar; legendas revisadas.

### 2. Curador de bibliotecas

Escolhe objetos 3D, efeitos e música **pelo que foi dito**, usando `editor.py biblioteca listar … --marca <marca> --json`.
Só usa o que a busca devolve para a marca. Acrescentar item à biblioteca: só com licença livre (CC0, CC BY 4.0, MIT,
domínio público ou própria), crédito no catálogo e `editor.py biblioteca verificar` passando.

### 3. Revisor de marca

Antes da entrega, confere com olhos de cliente:

- [ ] `editor.py conferir final.mp4 --marca <marca>` diz "confere";
- [ ] `previa.jpg` só tem cores, fontes, logo e vinheta da marca;
- [ ] nenhum texto cita outra marca (@, site, nome, bordão);
- [ ] o CTA aponta para o site da marca (ou não existe, se a marca não tem CTA);
- [ ] `manifesto.json` lista só arquivos de `biblioteca/` e de `marcas/<marca>/`;
- [ ] com música, `creditos.txt` existe e o crédito vai na legenda do post.

Se algo falhar, volta para o editor. Nunca entregue com dúvida.

### 4. Mantenedor do motor

Mexe em `motor/`, `marcas/`, `biblioteca/`, `ferramentas/`, `tests/`. Regras:

- Não enfraqueça a guarda (`motor/guarda.py`) nem o sandbox (`arquivo_marca`) para fazer algo passar. Se uma regra
  atrapalha um caso legítimo, mude a regra com teste novo e explique no PR.
- Toda regra nova de isolamento ganha teste em `tests/test_guarda.py` ou `tests/test_marcas.py`.
- `make tudo` antes do PR. Mudança visual só com `testar --atualizar` na marca afetada, com a folha no PR.
- Atualize docs, CHANGELOG e as skills quando o EDL ou um comando mudar.

## O que nunca fazer

- Renderizar sem `--marca` decidida, ou reaproveitar a pasta de trabalho de um vídeo de outra marca.
- Copiar logo, vinheta, mascote ou objeto de uma marca para outra, ou para `biblioteca/`.
- Usar música comercial, sem licença clara, ou gerada por código.
- Inventar fala, publicar o vídeo, ou commitar vídeo bruto, token ou senha.
