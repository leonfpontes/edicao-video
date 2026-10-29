# Marcas e isolamento

## Uma marca é uma pasta

```
marcas/pontes_brain/
├── marca.json      # identidade
├── logo.png        # logo claro (marca d'água, CTA, vinheta)
├── vinheta.mp4     # prévia da vinheta (referência para humanos)
├── leo/            # mascote (só esta marca)
└── 3d/lp.png       # objetos 3D próprios
```

### `marca.json`

| Campo | Obrigatório | O que é |
|---|---|---|
| `id` | sim | Igual ao nome da pasta |
| `nome` | sim | Nome de exibição (vai nos metadados do vídeo) |
| `cores` | sim | Os 7 papéis: `marinho`, `marinho_2`, `champanhe`, `bronze`, `papel`, `papel_2`, `nevoa` (hex). Extras são permitidos |
| `fontes` | sim | `titulo` e `texto`, cada um com `Black`, `Bold`, `Regular` (arquivos em `biblioteca/fontes/`) |
| `intro` | sim | `tipo` (`pdca_lp`, `ticket` ou `logo`), `nome`, `sub` |
| `fundo_motivo` | sim | `pdca`, `ticket`, `anel` ou `nenhum` |
| `exclusivo.termos` | sim | Palavras que só esta marca pode usar (nome, @, site, bordão) |
| `logo` | não | PNG transparente, relativo à pasta. Sem logo: sem marca d'água e sem logo no CTA |
| `leo` | não | `true` se a marca tem o mascote em `leo/` |
| `cta` | não | `chamada`, `url`, `pose_leo` |
| `musica.politica` | não | `proibida`, `opcional` (padrão) ou `obrigatoria` |
| `vocabulario` | não | Prompt inicial do Whisper (nomes e termos da marca) |
| `padroes_edl` | não | Valores padrão do rascunho do EDL (ex.: `{"intro": {"ativo": false}}`) |
| `marca_dagua_alt`, `marca_dagua_y`, `cta_logo_alt` | não | Ajustes finos de posição e tamanho |

### Criar uma marca

1. `cp -r marcas/modelo marcas/<id>` e troque `id`, `nome`, `cores`, `fontes`, `logo.png`, `cta`, `vocabulario`.
2. Preencha `exclusivo.termos` com o que **não pode** aparecer em outra marca: @, site, nome do produto, bordão.
3. Use `"intro": {"tipo": "logo"}` e `"fundo_motivo": "anel"` (ou `"nenhum"`): vinheta e fundo saem prontos.
4. `editor.py marcas` para conferir; `editor.py testar --marca <id> --atualizar` grava a folha de referência;
   `editor.py testar` precisa terminar em `TUDO OK`.
5. Crie a skill em `skills/editor-video-<id>/SKILL.md` a partir de uma existente.

Uma vinheta sob medida (como a do PDCA ou a do ticket) é código em `motor/vinhetas.py` e precisa ser registrada em
`VINHETAS` com a marca dona; o mesmo vale para um motivo de fundo novo em `MOTIVOS`.

## Isolamento

A regra: **um vídeo de uma marca nunca pode carregar nada da identidade de outra.** Cada camada abaixo é testada.

### 1. Uma marca por processo, sem padrão

`analisar` exige `--marca`. `renderizar` lê a marca do `edl.json`. Antes de `ativar()`, qualquer leitura de marca levanta
`ErroDeMarca`. `ativar()` zera cores, fontes, configuração e auditoria, então nada sobra da marca anterior.

### 2. Pastas trancadas

`arquivo_marca(rel)` só devolve caminhos **dentro** de `marcas/<ativa>/`. `../outra/logo.png`, caminho absoluto para outra
marca ou o Leo numa marca sem Leo são recusados.

### 3. Identidade com dono

| Recurso | Dono |
|---|---|
| Vinheta `pdca_lp`, fundo `pdca`, Leo | `pontes_brain` |
| Vinheta `ticket`, fundo `ticket` | `girahub` |
| Vinheta `logo`, fundos `anel` e `nenhum` | qualquer marca |
| `marcas/<id>/3d/*.png` | só a marca `<id>` |

`validar_marca` recusa um `marca.json` que use recurso de outro dono.

### 4. Guarda do EDL (`motor/guarda.py`)

Antes do render, `conferir_edl` junta **todos** os problemas e recusa o EDL se houver qualquer um:

- `"marca"` ausente ou diferente da ativa; `analise.json` de outra marca;
- termo exclusivo de outra marca em título, destaque, rótulo de efeito, ênfase ou correção de legenda e CTA (sem acento, sem caixa,
  por palavra inteira);
- `cta.url` que não é o da marca;
- Leo (elemento ou `pose_leo`) em marca sem Leo;
- arquivo dentro da pasta de outra marca (imagem, b-roll, fundo, música);
- objeto 3D ou faixa que não serve à marca, ou desconhecido;
- efeito desconhecido ou com cor que não é papel da paleta.

### 5. Auditoria

Todo arquivo aberto durante o render passa por `registrar()`. No fim, `conferir_auditoria()` recusa se algum veio da
pasta de outra marca. A lista vai para `manifesto.json`.

### 6. Selo no vídeo

O render grava nos metadados `comment=marca=<id>; editor=edicao-video <versão>` e `artist=<nome da marca>`. Antes de
entregar:

```bash
editor.py conferir final.mp4 --marca girahub
# final.mp4: marca girahub confere.
```

### 7. Testes

`editor.py testar` roda, para cada marca, `isolamento_ok`: tenta renderizar com o termo exclusivo de cada outra marca e
falha se a guarda deixar passar. `tests/test_guarda.py` e `tests/test_marcas.py` cobrem cada regra acima.
