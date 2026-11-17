# Referência do `edl.json`

O EDL (edit decision list) é onde o agente decide tudo. `analisar` escreve um rascunho; o agente edita; `renderizar`
aplica. **Todos os tempos estão na linha do tempo do vídeo original** (os mesmos da `transcricao.txt`); o motor recalcula
tudo depois dos cortes. Um exemplo real está em [exemplos/edl-pontes_brain.json](../exemplos/edl-pontes_brain.json).

```jsonc
{
  "marca": "pontes_brain",               // obrigatório; precisa bater com a análise e com a marca ativa
  "fonte": "<pasta>/fonte_cfr.mov",      // escrito pelo analisar
  "formato": "vertical",                 // vertical (1080×1920) | feed (1080×1350) | horizontal (1920×1080)
  "segmentos": [ … ],
  "zooms": [ … ],
  "fundo": { … },
  "cor": { … },
  "audio": { … },
  "musica": { … },
  "legendas": { … },
  "elementos": [ … ],
  "intro": {"ativo": true, "duracao": 2.2, "apos_gancho": true},  // apos_gancho: o gancho abre e a vinheta vem depois
  "marca_dagua": true,
  "barra_progresso": true,
  "cta": { … },
  "estilo": "tutorial_passos",            // opcional: preset de estilo (veja "Estilos, planos e looks")
  "saida": "final.mp4"
}
```

Campos ausentes usam o padrão da marca (`padroes_edl` no `marca.json`) e, depois, o padrão geral.

## `segmentos`

Trechos que **ficam**, na ordem em que aparecem no vídeo. Apague os que saem.

| Campo | Valores |
|---|---|
| `id`, `ini`, `fim` | Identificador e tempos no original |
| `zoom` | Enquadramento base: 1.0 (no máximo 1.08); muda devagar entre cortes |
| `transicao` | Entrada do trecho: `null` (corte seco), `push`, `whip`, `zoom`, `slide`, `flash`, `dissolve`, `giro` (giro 3D), `rasgo` (papel rasgado), `vidro` (vidro líquido), `luz` (queima de luz) |
| `som` | Som da transição (id de `biblioteca listar sons`); `false` deixa muda. Sem o campo, vale o padrão da marca |
| `gancho` | `true` repete o trecho no início do vídeo (a frase mais forte abrindo). O original continua no lugar |
| `salto` | `true` troca o `zoom` no corte, sem deslizar (jump cut com mudança de enquadramento; o diretor marca sozinho) |
| `plano` | `rosto` (padrão) · `dividido` (palco de motion em cima, rosto embaixo) · `motion` (só o palco; a voz continua) |
| `corte_y` | No `dividido`, o centro da faixa de rosto mostrada (fração da altura; padrão 0.36) |
| `look` | Cor do trecho: `pb`, `pb_acento`, `duotom`, `quente`, `frio`, `limpo`, `noite`, `adesivo` |
| `texto` | A fala do trecho (referência para o agente) |

## `zooms`

Ênfases **dentro** de um trecho, terminando pelo menos 0,4 s antes do corte (o motor força isso).

```jsonc
{"ini": 13.6, "fim": 14.4, "fator": 1.2, "modo": "punch"}   // tranco curto numa palavra
{"ini": 27.2, "fim": 32.0, "fator": 1.12, "modo": "suave"}  // aproximação lenta
{"ini": 17.0, "fim": 18.5, "fator": 1.15, "modo": "abre"}   // entra fechado e abre (a câmera se afasta)
```

## Elementos que acompanham o movimento (`seguir`)

Qualquer elemento aceita `"seguir"`: uma trilha `[[t, x, y], …]` com o tempo e a posição (0 a 1) **na fonte**. O
render projeta a trilha no quadro de saída depois do enquadramento (zoom, rosto, punch), então o elemento fica colado
na ponta do dedo, no rosto ou num ponto da parede. `dx`/`dy` (fração da tela) deslocam o elemento em relação ao ponto.
Cartões (`titulo`, `destaque`) ficam presos à área segura e acima da legenda.

```jsonc
{"tipo": "efeito", "nome": "brilhos", "ini": 2.6, "fim": 5.0, "seguir": [[2.6, 0.62, 0.41], [3.0, 0.6, 0.35]], "raio": 0.1}
{"tipo": "efeito", "nome": "check", "ini": 11.8, "fim": 13.4, "seguir": [[11.8, 0.5, 0.33]], "dx": 0.22, "dy": -0.06}
```

O `analisar` escreve essas trilhas sozinho a partir de `cena.json` (veja [diretor-e-entrega.md](diretor-e-entrega.md)).

**Preso a um objeto do ambiente (`fixar`)**: em vez da trilha, diga só onde está o objeto num instante da fonte,
`"fixar": [t, x, y]`. O render rastreia o ponto pelo fluxo óptico (para frente e para trás, enquanto o elemento está na
tela) e grava a trilha em `_cache/fixar.json`. Funciona com `na`/`ate`. É o jeito de rotular o que a câmera mostra:

```jsonc
{"tipo": "anotacao", "texto": "firmeza de Caboclo", "na": "caboclo", "segura": 1.2, "fixar": [36.1, 0.78, 0.47],
 "tam": 0.038, "caixa": true}
```

Na `anotacao` presa a um ponto, a mira cai no objeto e o texto sai para a direita; `caixa: true` põe uma tarja escura
translúcida atrás (legível sobre parede clara).

## `fundo`

| Campo | Valores |
|---|---|
| `tipo` | `original` · `desfoque` · `marca` (fundo da marca com o motivo dela) · `imagem` |
| `variante` | (`marca`) `marinho` ou `papel` |
| `imagem` | (`imagem`) caminho; nunca da pasta de outra marca |
| `parallax`, `sombra` | `true`/`false` |

## `cor` e `audio`

`cor.igualar_luz: true` leva cada trecho para a exposição do meio do vídeo (sala escura e cozinha clara ficam iguais).

```jsonc
"cor":   {"contraste": 1.05, "saturacao": 1.06, "calor": 0.03, "nitidez": 0.25,
          "lut": "filme.cube", "lut_intensidade": 0.6, "proteger_pele": true, "igualar_clipes": true},
"audio": {"denoise": true, "denoise_db": 10, "presenca_db": 1.0, "loudness": -16, "sfx_transicoes": true}
```

Não passe de `saturacao` 1.12, `presenca_db` 2 nem `loudness` −14. A conferência mede: I entre −17 e −15 LUFS, pico abaixo
de −1,5 dBFS.

## `musica`

```jsonc
"musica": {"faixa": "lasting-hope", "ini": 12.0, "volume_db": -20, "fade_in": 0.8, "fade_out": 2.5, "ducking": true}
```

`faixa` é um id de `editor.py biblioteca listar musicas`. Arquivo próprio: `"arquivo"`, com `"licenca"` livre e
`"credito"`. A política da marca decide se música é proibida, opcional ou obrigatória. Veja [bibliotecas.md](bibliotecas.md#músicas).

## `legendas`

```jsonc
"legendas": {"ativo": true, "estilo": "marcada", "palavras_por_bloco": 3, "posicao_y": 0.68, "maiusculas": false,
             "enfase": ["diagnóstico", "PDCA"],          // 3 a 6 palavras na cor de destaque
             "correcoes": {"porque": "por que"}}         // conserta o Whisper
```

`"marcacao": "enfase"` deixa a marcação só nas palavras de ênfase, sem deslizar de palavra em palavra (padrão do
GiraHub). `largura_max` (padrão 0,70 da tela) é a largura máxima da caixa da legenda antes de quebrar em duas linhas, para não
chegar aos botões do Reels. `quebra_sentido` (padrão `true`) não deixa um bloco terminar em artigo, preposição ou conjunção ("de", "o", "que"). `emoji`
(`true` ou um mapa `{"palavra": "objeto-3d"}`) faz um objeto 3D da biblioteca pular acima da legenda quando a palavra é
falada ("dinheiro", "ideia", "foguete"…); `emoji_tam` (0.13) e `emoji_espaco` (4 s entre um e outro).

`estilo`: `marcada` (padrão, marcação na cor de destaque) ou `limpa` (branco, sem caixa nem contorno, sombra macia; use
com 1 ou 2 palavras por bloco). Nos planos `dividido` e `motion` a legenda vai para a linha que divide (0.5) e para 0.72;
troque com `posicao_y_dividido` e `posicao_y_motion`.

## `elementos`

Todo elemento aceita âncoras pela fala:

| Âncora | Efeito |
|---|---|
| `na` | Texto exato da transcrição onde o elemento entra (`ocorrencia` se repetir) |
| `ate` | Texto onde ele sai (no fim dessa fala) |
| `antecipa` | Quanto antes da palavra entra (padrão 0,12 s) |
| `segura` | Quanto fica depois (padrão 1,2 s; 0,25 s com `ate`) |
| `ini` / `fim` | Tempos no original, quando não há fala para ancorar |
| `saida` | `[ini, fim]` em segundos do vídeo **final** (para elementos sobre o gancho) |

E posição: `x`, `y` (0 a 1), `altura` ou `largura` (fração da tela).

| `tipo` | Campos | Notas |
|---|---|---|
| `titulo` | `texto` | Wipe, palavras subindo e giro 3D. Até 6 palavras |
| `destaque` | `texto`, `tam` | Rótulo na cor de destaque com mola. Até 4 palavras; empilhe em listas (`y` 0.08, 0.14, 0.20) |
| `objeto3d` | `nome`, `fase`, `fluent`, `emoji` | Da biblioteca 3D ou da pasta da marca. Se não existir e vier `fluent` (nome em inglês do Fluent Emoji 3D) ou `emoji`, o editor **cria** o objeto (veja [bibliotecas.md](bibliotecas.md#criar-objetos-3d)) |
| `efeito` | `nome`, `cor`, `cor2`, `intensidade`, parâmetros do efeito | 28 efeitos; veja [bibliotecas.md](bibliotecas.md#efeitos) |
| `leo` | `pose`, `lado` | Só @pontes_brain, e só com contexto narrativo |
| `imagem` | `arquivo` | Print, foto, gráfico |
| `broll` | `arquivo` | Cobre a tela inteira; a voz continua |
| `som` | `nome`, `volume_db`, `rotulo` | Só áudio, da biblioteca de sons. O ápice do som cai na âncora (riser chegando na palavra). Com `rotulo` ("WHOOSH"), o som aparece na tela como onda com o nome |

`broll` aceita ainda `perspectiva` (tela num plano 3D com câmera e profundidade de campo) e `bolha` (o rosto numa
bolha circular por cima do b-roll): veja abaixo.

Qualquer elemento aceita `"sem_legenda": true` (a legenda some enquanto ele está na tela) e `"som": "<id>"` (troca o som de entrada) ou `"som": false` (mudo). `"sfx_elementos": false`
(em `audio`) desliga os sons automáticos dos elementos; os do `tipo` `som` continuam. Veja [bibliotecas.md](bibliotecas.md#sons).

## Estilos, planos e looks

Guia com os três estilos estudados e quando usar cada um: [estilos-de-referencia.md](estilos-de-referencia.md).
`editor.py estilos` lista tudo; `editor.py analisar … --estilo <estilo>` já escreve o rascunho no estilo.

**`estilo`** (no topo do EDL) preenche o que o EDL não disse. O EDL sempre vence.

| Estilo | O que o preset muda |
|---|---|
| `tutorial_passos` | Legenda `limpa` de 2 palavras, sem som nas transições, pausas cortadas a partir de 0,4 s, aviso se algo ficar parado mais de 3 s |
| `tela_perspectiva` | Sem legenda, sem som nas transições, pausas a partir de 0,6 s |
| `vitrine` | Sem legenda corrida (a tipografia é cenográfica), sons em tudo, pausas a partir de 0,35 s, aviso acima de 2 s parado |

`parado_max` (segundos) liga o aviso de ritmo em qualquer EDL: o render mede o maior trecho sem mudança visual.

**Motion de estilo** (`elementos`, todos com `na`/`ate`, `x`, `y`; cores só por papel da paleta):

| `tipo` | Campos | Notas |
|---|---|---|
| `passo` | `numero`, `texto`, `rotulo` ("Passo") | Cabeçalho: número em serifa itálica, texto em sans. Fica no topo do palco |
| `digitacao` | `texto`, `vel`, `caixa`, `largura` | Letra a letra, com cursor; `caixa` põe num campo de texto |
| `janela` | `titulo`, `linhas`, `largura`, `vel` | Janela de app; `[[trecho]]` sai com marca-texto |
| `arvore` | `raiz`, `filhos` (até 5) | Linhas que se desenham e filhos com mola |
| `mapa` | `centro`, `itens` (até 6) | Recapitulação; "Passo 1. Monta" vira número em serifa + texto |
| `comentario` | `texto`, `dica` | Barra de comentário digitando a palavra-chave (CTA "comenta X") |
| `icone` | `arquivo` (PNG) ou `nome` (`pasta`, `documento`, `pessoa`), `rotulo`, `tamanho` | O PNG de um app entra com as cores dele |
| `carrossel` | `arquivos` (2 a 6), `altura` | Miniaturas deslizando (gancho com referências) |
| `titulo_caixa` | `texto` (linhas com `/`) | Gancho em caixas justas com colchete no canto |
| `titulo_editorial` | `partes` [{`t`, `fonte`, `cor`}], `numero` | Fontes misturadas (condensada, manuscrita, serifa) e número circulado |
| `bilhete` | `texto` | Letras de bilhete de resgate |
| `anotacao` | `texto`, `estilo`, `caixa` | Rótulo mono pequeno com cruz de mira; `estilo: "editorial"` com `texto` "sobrelinha/Nome" vira sobrelinha em sans e nome em serifa itálica, com ponto e fio |
| `neon` | `texto` (linhas com `/`), `cor`, `caixa` | Manuscrito em neon que acende tremulando |
| `texto_atras` | `texto`, `fonte`, `tam`, `cor` | Texto enorme **atrás da pessoa** (recorte automático); combina com o look `pb_acento` |
| `hud_rosto` | `rotulo` | Mira, malha e anéis que seguem o rosto |

Os de interface (`passo`, `digitacao`, `janela`, `arvore`, `mapa`, `icone`) usam `"area": "palco"`: `x`/`y` são relativos
ao palco e eles só aparecem nos planos `dividido` e `motion` (`"sempre": true` mostra também no `rosto`).

Fontes de estilo: `serifa_italica`, `serifa`, `condensada`, `mono`, `manuscrita` (biblioteca, OFL) e `sans`, `sans_forte`,
`sans_leve` (as da marca). A marca pode trocar qualquer uma em `fontes.estilo` no `marca.json`.

**Tela em perspectiva e bolha** (num `broll`):

```jsonc
{"tipo": "broll", "arquivo": "tela.mp4", "na": "esse aqui", "ate": "embaixo",
 "perspectiva": {"foco": 0.6, "luz": true,
                 "camera": [{"t": 0, "rx": 22, "ry": -18, "zoom": 1.25, "cx": 0.3, "cy": 0.3},
                            {"t": 1, "rx": 10, "ry": 12, "zoom": 1.6, "cx": 0.6, "cy": 0.55}]},
 "bolha": {"x": 0.22, "y": 0.8, "raio": 0.16}}
```

`camera`: pontos-chave de 0 a 1 ao longo do b-roll (graus `rx`/`ry`/`rz`, `zoom`, e o ponto da tela no centro `cx`/`cy`).
Aponte a câmera para o que a fala cita. `foco` 0 a 1 é a profundidade de campo; `luz` é o brilho quente desfocado.

## `cta`

```jsonc
"cta": {"ativo": true, "duracao": 3.5, "chamada": "Quer destravar seu produto?",
        "url": "leopontes.com.br/mentoria-produto", "pose_leo": "apontando"}
```

`url` precisa ser a da marca; `pose_leo` só onde há Leo. `"transicao_cta"` (no topo) escolhe a entrada do CTA.

## O que a guarda recusa

Qualquer coisa de outra marca: veja [marcas.md](marcas.md#4-guarda-do-edl-motorguardapy). A mensagem lista todos os
problemas de uma vez, com o caminho do campo (`elementos[3].texto contém "girahub", que é da marca girahub`).

## Entrega e cache

| Campo | Valores |
|---|---|
| `capa` | `{"texto": "…", "t": 4.2, "y": 0.16}`: título e instante (s do vídeo final) da capa gerada por `exportar` |
| `cache_recorte` | `false` desliga o cache do recorte da pessoa (`_cache/` na pasta do EDL) |

Caminhos de arquivo no EDL (`arquivo`, `imagem`, `fonte`, `lut`) são relativos à pasta do próprio `edl.json`. O diretor,
a prévia, a conferência visual e o `exportar` estão em [diretor-e-entrega.md](diretor-e-entrega.md).
