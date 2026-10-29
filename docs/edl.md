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
  "intro": {"ativo": true, "duracao": 2.2},
  "marca_dagua": true,
  "barra_progresso": true,
  "cta": { … },
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
| `texto` | A fala do trecho (referência para o agente) |

## `zooms`

Ênfases **dentro** de um trecho, terminando pelo menos 0,4 s antes do corte (o motor força isso).

```jsonc
{"ini": 13.6, "fim": 14.4, "fator": 1.2, "modo": "punch"}   // tranco curto numa palavra
{"ini": 27.2, "fim": 32.0, "fator": 1.12, "modo": "suave"}  // aproximação lenta
```

## `fundo`

| Campo | Valores |
|---|---|
| `tipo` | `original` · `desfoque` · `marca` (fundo da marca com o motivo dela) · `imagem` |
| `variante` | (`marca`) `marinho` ou `papel` |
| `imagem` | (`imagem`) caminho; nunca da pasta de outra marca |
| `parallax`, `sombra` | `true`/`false` |

## `cor` e `audio`

```jsonc
"cor":   {"contraste": 1.05, "saturacao": 1.06, "calor": 0.03, "nitidez": 0.25},
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
"legendas": {"ativo": true, "palavras_por_bloco": 3, "posicao_y": 0.68, "maiusculas": false,
             "enfase": ["diagnóstico", "PDCA"],          // 3 a 6 palavras na cor de destaque
             "correcoes": {"porque": "por que"}}         // conserta o Whisper
```

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
| `objeto3d` | `nome`, `fase` | Da biblioteca 3D ou da pasta da marca. Dois objetos: um de cada lado da cabeça |
| `efeito` | `nome`, `cor`, `cor2`, `intensidade`, parâmetros do efeito | 28 efeitos; veja [bibliotecas.md](bibliotecas.md#efeitos) |
| `leo` | `pose`, `lado` | Só @pontes_brain, e só com contexto narrativo |
| `imagem` | `arquivo` | Print, foto, gráfico |
| `broll` | `arquivo` | Cobre a tela inteira; a voz continua |
| `som` | `nome`, `volume_db` | Só áudio, da biblioteca de sons. O ápice do som cai na âncora (riser chegando na palavra) |

Qualquer elemento aceita `"som": "<id>"` (troca o som de entrada) ou `"som": false` (mudo). `"sfx_elementos": false`
(em `audio`) desliga os sons automáticos dos elementos; os do `tipo` `som` continuam. Veja [bibliotecas.md](bibliotecas.md#sons).

## `cta`

```jsonc
"cta": {"ativo": true, "duracao": 3.5, "chamada": "Quer destravar seu produto?",
        "url": "leopontes.com.br/mentoria-produto", "pose_leo": "apontando"}
```

`url` precisa ser a da marca; `pose_leo` só onde há Leo. `"transicao_cta"` (no topo) escolhe a entrada do CTA.

## O que a guarda recusa

Qualquer coisa de outra marca: veja [marcas.md](marcas.md#4-guarda-do-edl-motorguardapy). A mensagem lista todos os
problemas de uma vez, com o caminho do campo (`elementos[3].texto contém "girahub", que é da marca girahub`).
