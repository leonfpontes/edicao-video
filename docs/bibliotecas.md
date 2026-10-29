# Bibliotecas

Três bibliotecas servem a todas as marcas: **3D**, **músicas** e **efeitos**. Os catálogos ficam no Git
(`biblioteca/<qual>/catalogo.json`); o motor desenha tudo com a paleta da marca ativa.

```bash
editor.py biblioteca listar 3d|musicas|efeitos [termo] [--marca X] [--clima …] [--categoria …] [--genero …] [--json]
editor.py biblioteca baixar musicas [id …]       # baixa as faixas (fora do Git), conferindo o sha256
editor.py biblioteca baixar 3d "<Nome no Fluent>" # acrescenta um emoji 3D do Fluent ao catálogo
editor.py biblioteca verificar                    # ids únicos, licenças, arquivos e marcas
editor.py biblioteca previa efeitos|3d --marca X  # grade de prévia na paleta da marca
editor.py biblioteca catalogo                     # regrava biblioteca/efeitos/catalogo.json a partir do código
```

`--json` devolve a lista em JSON, para o agente filtrar sem ler tabela.

## Regras de uso

- **Uma biblioteca, todas as marcas.** Um item só fica restrito se tiver `"marcas": [...]` no catálogo.
- **Identidade não entra na biblioteca.** Logo, vinheta, mascote e objetos 3D próprios de uma marca ficam em
  `marcas/<id>/` e só aparecem para ela (veja [marcas.md](marcas.md)).
- **Só licença livre**: `CC0 1.0`, `CC BY 4.0`, `MIT`, `Domínio público` ou `Própria`. `biblioteca verificar` e os testes
  recusam qualquer outra.
- **Efeito sem motivo na fala não entra.** Cada efeito, objeto ou trilha precisa de uma razão no que foi dito.

## 3D

167 objetos em `biblioteca/3d/`, de dois tipos:

| Tipo | Origem | Licença | Como é animado |
|---|---|---|---|
| `render` (119) | [Microsoft Fluent Emoji 3D](https://github.com/microsoft/fluentui-emoji) | MIT | Entra com mola e leve giro, flutua e sai girando (`Sprite3D`) |
| `extrusao` (48) | [Simple Icons](https://simpleicons.org) 16.30, na cor da marca dona do logo | CC0 1.0 | O motor extruda o PNG plano: espessura, luz e reflexo (`Objeto3D`) |

No EDL:

```jsonc
{"tipo": "objeto3d", "nome": "foguete", "na": "lançamento", "ate": "mercado", "x": 0.8, "y": 0.3}
```

Nomes em português; o nome original em inglês também funciona (`rocket` encontra `foguete`). Busque por nome, tag ou categoria:
`editor.py biblioteca listar 3d prazo`.

| Categoria | Qtde. | Ids |
|---|---|---|
| analise | 2 | `lupa`, `laboratorio` |
| comunicacao | 8 | `balao-fala`, `balao-pensamento`, `megafone`, `sino`, `envelope`, `claquete`, `microfone`, `camera` |
| comunidade | 6 | `ticket`, `vela`, `erva`, `onda`, `pessoas`, `grupo` |
| conquista | 6 | `trofeu`, `medalha`, `diamante`, `confete`, `presente`, `balao` |
| crescimento | 3 | `foguete`, `escada`, `bandeira-chegada` |
| dados | 4 | `grafico-subindo`, `grafico-descendo`, `grafico-barras`, `abaco` |
| dinheiro | 6 | `saco-dinheiro`, `dinheiro`, `dinheiro-voando`, `moeda`, `cartao-credito`, `recibo` |
| estrategia | 7 | `alvo`, `bussola`, `mapa`, `quebra-cabeca`, `xadrez`, `chave`, `bandeira` |
| gestos | 9 | `joinha`, `palmas`, `maos-pra-cima`, `musculo`, `aceno`, `maos-unidas`, `apontando-cima`, `apontando-direita`, `apontando-baixo` |
| ideias | 3 | `lampada`, `cerebro`, `bola-cristal` |
| logos | 48 | `claude`, `chatgpt`, `gemini`, `perplexity`, `deepseek`, `mistral`, `copilot`, `cursor`, `notion`, `figma`, `jira`, `trello`, `miro`, `asana`, `clickup`, `airtable`, `github`, `vercel`, `supabase`, `n8n`, `zapier`, `make`, `obsidian`, `loom`, `hubspot`, `stripe`, `shopify`, `google`, `gmail`, `google-drive`, `google-sheets`, `google-calendar`, `google-meet`, `zoom`, `discord`, `telegram`, `whatsapp`, `instagram`, `youtube`, `tiktok`, `x`, `meta`, `spotify`, `apple`, `python`, `pix`, `nubank`, `mercado-pago` |
| processo | 4 | `engrenagem`, `ferramentas`, `caixa-ferramentas`, `obras` |
| reacoes | 9 | `pensativo`, `cabeca-explodindo`, `susto`, `estrelas-olhos`, `oculos-escuros`, `monoculo`, `festa`, `mao-na-boca`, `olhos` |
| sinais | 11 | `coracao`, `fogo`, `brilho`, `estrela`, `cem`, `check`, `xis`, `alerta`, `proibido`, `interrogacao`, `exclamacao` |
| tecnologia | 8 | `celular`, `notebook`, `robo`, `link`, `cadeado`, `escudo`, `inseto`, `bateria-fraca` |
| tempo | 3 | `despertador`, `ampulheta`, `cronometro` |
| trabalho | 11 | `maleta`, `calendario`, `prancheta`, `anotacao`, `alfinete`, `pasta`, `caixa`, `aperto-maos`, `predio`, `livros`, `formatura` |
| vida | 19 | `casa`, `sol`, `lua`, `arco-iris`, `cafe`, `bolo`, `aviao`, `praia`, `carro`, `bicicleta`, `cachorro`, `broto`, `girassol`, `rosa`, `flor-cerejeira`, `buque`, `notas-musicais`, `violao`, `bola` |

**Objetos próprios de marca**: `marcas/pontes_brain/3d/lp.png` (Monograma LP) e `marcas/girahub/3d/ticket.png`. Um PNG em
`marcas/<id>/3d/<nome>.png` vira objeto extrudado só daquela marca e tem prioridade sobre a biblioteca.

**Acrescentar**: `editor.py biblioteca baixar 3d "Party popper"` (nome da pasta no Fluent Emoji) baixa a versão 3D e
cadastra no catálogo com as palavras-chave originais; depois ajuste `id`, `categoria` e `tags` em português. Para regerar o
catálogo inteiro (novos logos, por exemplo), edite `ferramentas/montar_3d.py` e rode-o (precisa de `cairosvg`).

> Logos de terceiros (Claude, ChatGPT, Notion…) são marcas registradas dos donos. Use só em contexto editorial, quando a
> fala citar a ferramenta, nunca como se fosse parceria.

## Músicas

35 gravações reais com licença **CC BY 4.0** (uso comercial permitido com crédito):

- 31 faixas de **Kevin MacLeod** ([incompetech.com](https://incompetech.com)), com título, BPM, instrumentos e descrição
  tirados dos metadados oficiais do site;
- 4 faixas de **Alex Morgan** ([Free Music Archive](https://freemusicarchive.org)), em português e com pegada brasileira.

Cada faixa tem:

| Campo | Exemplo | Para quê |
|---|---|---|
| `clima` | `["esperança", "recomeço", "superação"]` | Escolher pela emoção da fala (filtro `--clima`) |
| `energia` | 1 a 5 | 1 = fundo de reflexão, 5 = festa |
| `bpm` / `bpm_fonte` | `100` / `oficial`, `estimado` ou `livre` | Casar cortes com a batida; `livre` = sem pulso fixo |
| `genero`, `instrumentos` | `Trilha sonora`, `Piano, Strings` | Filtro `--genero` e busca por texto |
| `sob_fala` | `true` | Faixa discreta o bastante para tocar sob voz |
| `usos` | `"virada, recomeço, história de superação"` | Sugestão de quando usar |
| `duracao` | `143.2` | Faixa curta entra em loop |
| `credito`, `licenca`, `url`, `sha256` | | Crédito pronto; download conferido |

No EDL:

```jsonc
"musica": {"faixa": "lasting-hope", "ini": 12.0, "volume_db": -20, "fade_in": 1.0, "fade_out": 2.0, "ducking": true}
```

O render baixa a faixa se faltar, aplica ducking sob a voz, normaliza o conjunto em −16 LUFS e grava `creditos.txt` com a
linha para colar na legenda do post. A política de cada marca (`"musica": {"politica": …}` no `marca.json`) manda:
`proibida` (@pontes_brain: o Leonardo põe a música no Instagram), `opcional` (GiraHub) ou `obrigatoria` (@leopontesrp).

**Música fora do catálogo** só entra com `"licenca"` (uma das livres) e `"credito"` no EDL. Melhor ainda: cadastre em
`ferramentas/montar_musicas.py` e regere o catálogo.

**Nunca entram**: música comercial, faixa sem licença clara, música sintetizada por código, e atabaque ou ponto cantado
(sagrados, não são trilha de propaganda).

A lista completa, com crédito de cada faixa, está em [biblioteca/musicas/CREDITOS.md](../biblioteca/musicas/CREDITOS.md).

## Efeitos

20 layers procedurais registrados em `motor/efeitos.py`. Todos:

- usam **só papéis da paleta** (`marinho`, `marinho_2`, `champanhe`, `bronze`, `papel`, `papel_2`, `nevoa`), nunca hex;
- são **determinísticos** (mesmo EDL, mesmo vídeo), o que permite a regressão visual;
- rodam na fase `elementos` (junto dos gráficos) ou `pos` (por cima de tudo, como luz e textura);
- aceitam as âncoras de qualquer elemento (`na`, `ate`, `antecipa`, `segura`, `ini`/`fim`);
- os marcados com som (`confete`, `contador`, `check`, `xis`…) ganham o "pop" discreto.

```jsonc
{"tipo": "efeito", "nome": "sublinhado", "na": "diagnóstico", "y": 0.42, "cor": "champanhe"}
```

| Efeito | Categoria | Fase | Quando usar | Parâmetros |
|---|---|---|---|---|
| `bokeh` | luz | elementos | Bolhas de luz desfocadas subindo devagar. Clima de sonho, conquista, fim de vídeo. | `intensidade` 0 a 1; `quantidade` número de luzes (padrão 18) |
| `brilhos` | luz | elementos | Faíscas de quatro pontas piscando ao redor de um ponto. Para algo valioso, novo, 'mágico'. | `x` 0 a 1; `y` 0 a 1; `raio` fração da largura (padrão 0.2); `quantidade` padrão 9 |
| `check` | marcacao | elementos | Selo de 'certo' (disco com mola e check traçado). Para acerto, aprovado, 'faça assim'. | `x` 0 a 1; `y` 0 a 1; `tamanho` diâmetro em fração da largura (padrão 0.12) |
| `chuva_3d` | celebracao | elementos | Objetos da biblioteca 3D caindo pela tela (ex.: dinheiro, corações, foguetes). | `objeto` id da biblioteca 3D (padrão estrela); `quantidade` padrão 12; `tamanho` fração da largura (padrão 0.12) |
| `circulo` | marcacao | elementos | Círculo feito 'à mão' em volta de um ponto (marca-texto de vídeo). | `x` 0 a 1; `y` 0 a 1; `largura` fração da largura (padrão 0.4); `altura` fração da largura (padrão 0.18) |
| `confete` | celebracao | elementos | Explosão de confete nas cores da marca, com gravidade. Para conquista, lançamento, 'deu certo'. | `x` 0 a 1 (origem); `y` 0 a 1 (origem); `quantidade` padrão 90 |
| `contador` | informacao | elementos | Número que conta até o valor falado (ex.: 0 → 87%), num cartão da marca. | `de` número inicial (padrão 0); `ate` número final; `prefixo` ex.: R$ ; `sufixo` ex.: %; `casas` casas decimais (padrão 0); `duracao_contagem` segundos (padrão 1.2); `y` 0 a 1 (padrão 0.3) |
| `flash` | impacto | pos | Clarão rápido na cor clara da marca, no instante de uma palavra forte. | `intensidade` 0 a 1 (padrão 1) |
| `foco` | atencao | pos | Escurece tudo fora de um círculo (íris que fecha sobre o ponto x,y). Para apontar um detalhe. | `x` 0 a 1; `y` 0 a 1; `raio` fração da largura (padrão 0.22); `intensidade` escuridão 0 a 1 |
| `glitch` | impacto | pos | Falha digital rápida (canais de cor separados e fatias deslocadas). Para virada, erro, 'bug' no processo. | `intensidade` 0 a 1 (padrão 1) |
| `grao` | textura | pos | Grão de filme sutil no quadro inteiro. Dá textura de cinema a vídeos muito 'limpos'. | `intensidade` 0 a 1 (padrão 1 = grão leve) |
| `moldura_rec` | informacao | elementos | Moldura de câmera gravando (cantos, ponto pulsando e cronômetro). Para bastidores e vlog. | `rotulo` texto ao lado do ponto (padrão REC) |
| `ondas` | atencao | elementos | Anéis que se expandem a partir de um ponto (pulso de atenção, notificação, 'olha aqui'). | `x` 0 a 1; `y` 0 a 1; `raio` fração da largura (padrão 0.3) |
| `seta` | marcacao | elementos | Seta curva que se desenha e aponta para (x, y). Para indicar um detalhe da tela ou do b-roll. | `x` ponta 0 a 1; `y` ponta 0 a 1; `de` esquerda\|direita\|cima\|baixo (padrão esquerda); `comprimento` fração da largura (padrão 0.3) |
| `sublinhado` | marcacao | elementos | Sublinhado ondulado desenhado da esquerda para a direita, sob uma palavra ou número. | `x` centro 0 a 1; `y` 0 a 1; `largura` fração da largura (padrão 0.5) |
| `tremor` | impacto | pos | Câmera treme e assenta (impacto, susto, revelação). Curto: 0,3 a 0,6 s. | `intensidade` 0 a 1 (padrão 1) |
| `vazamento_luz` | luz | pos | Vazamento de luz quente que atravessa a tela, como em filme. Bom em abertura e virada de assunto. | `intensidade` 0 a 1 (padrão 1); `direcao` esquerda\|direita (padrão direita) |
| `vhs` | textura | pos | Estética VHS: linhas de varredura, cor deslocada e uma faixa de ruído. Para memória, nostalgia, 'antigamente'. | `intensidade` 0 a 1 (padrão 1) |
| `vinheta` | textura | pos | Escurece as bordas e leva o olhar para o centro. Use em fala emotiva ou dramática. | `intensidade` 0 a 1 (padrão 1) |
| `xis` | marcacao | elementos | Selo de 'errado' (disco com mola e X traçado). Para erro comum, mito, 'não faça'. | `x` 0 a 1; `y` 0 a 1; `tamanho` diâmetro em fração da largura (padrão 0.12) |

Parâmetros comuns: `cor` e `cor2` (papéis da paleta), `intensidade` (0 a 1), `x`/`y` (0 a 1).

**Acrescentar um efeito**: crie uma classe em `motor/efeitos.py` com o decorador `@efeito(nome, categoria, descricao,
params, fase, pop)`, herdando de `Efeito` e implementando `desenhar(frame, dt, rest)`. Use `self.cor`, `cor_marca()` e
`self.rng_quadro(dt)` (nunca `random` solto). Rode `editor.py biblioteca catalogo`, `make testes` e
`editor.py biblioteca previa efeitos --marca pontes_brain` para ver o resultado.

## Licenças

| Recurso | Licença | Crédito |
|---|---|---|
| Fluent Emoji 3D | MIT | © Microsoft Corporation |
| Simple Icons | CC0 1.0 | Logos são marcas registradas dos donos |
| Músicas Kevin MacLeod | CC BY 4.0 | "Título" – Kevin MacLeod (incompetech.com) |
| Músicas Alex Morgan | CC BY 4.0 | "Título" – Alex Morgan (Free Music Archive) |
| Roboto, Inter, Fraunces | SIL Open Font License 1.1 | Google Fonts |
| Robust Video Matting | GPL-3.0 (modelo usado como arquivo, sem alteração) | Peter Lin et al. |
| MediaPipe | Apache 2.0 | Google |
| rnnoise-models | BSD | Gregor Richards |
