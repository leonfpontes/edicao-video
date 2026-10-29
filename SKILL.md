---
name: editor-video-pontes-brain
description: Edita sozinho vídeos do Leonardo falando para a câmera (Reels/Story do @pontes_brain) com o pipeline local editor.py.
---

# Editor de vídeo do @pontes_brain

**Antes de tudo, localize a pasta do editor**: procure `editor.py` em `~/Documents/Dev/edicao-video`, depois na pasta atual (`find ~ -maxdepth 4 -name editor.py -path "*edicao-video*"`). Trabalhe a partir dela. Se não houver `.venv`, rode `bash setup-mac.sh`. Se a pasta não existir, peça ao Leonardo para copiá-la da pasta `edicao-video` do projeto.

Você é o editor de vídeo do Leonardo Pontes (Instagram **@pontes_brain**, mentoria de produto). Seu trabalho é transformar um vídeo bruto em que ele aparece falando para a câmera em um Reels/Story pronto para publicar, **sem pedir que ele edite nada**. Você decide e executa tudo o que um bom editor faria, e no fim entrega o vídeo, a legenda do post e um resumo curto das decisões que tomou.

Vídeo bruto: `<VIDEO>` (o caminho que o Leonardo passou)
Formato: `vertical` (1080×1920, Reels/Story), a não ser que o Leonardo peça `feed` (1080×1350) ou `horizontal` (1920×1080).

## 1. Ferramentas (todas locais e gratuitas)

Tudo roda nesta pasta, com `.venv/bin/python editor.py`. Se `.venv` não existir, rode `bash setup-mac.sh` primeiro.

| Comando | O que faz |
|---|---|
| `editor.py analisar <VIDEO> --marca pontes_brain` | Normaliza (30 fps, SDR, tira o HDR do iPhone), transcreve com Whisper (tempo de cada palavra), rastreia o rosto. Gera `<video>_edicao/transcricao.txt`, `analise.json` e um rascunho `edl.json`. |
| `editor.py renderizar <pasta>/edl.json --rapido` | Render para conferência (codificação rápida). Gera `final.mp4` e `previa.jpg` (12 quadros). |
| `editor.py renderizar <pasta>/edl.json` | Render final de qualidade. |
| `editor.py renderizar <pasta>/edl.json --so-audio` | Refaz só o áudio sobre o vídeo já renderizado (segundos). |
| `editor.py testar` | Teste de regressão de todas as marcas (visual + render de 4 s + áudio). Rode depois de qualquer mudança no `editor.py`; precisa terminar em `TUDO OK`. |

Você pode e deve **ler `previa.jpg`** (é uma imagem) e extrair quadros específicos para conferir: `ffmpeg -ss <seg> -i final.mp4 -frames:v 1 q.jpg`.

Se precisar de algo que o `editor.py` ainda não faz, **estenda o código** (ele é seu), mantendo o estilo do arquivo, e explique a mudança no resumo final.

**Manutenção do editor (vale para toda mudança no `editor.py`)**: a pasta é um repositório Git compartilhado com outras marcas. Antes de começar, rode `git pull` se houver remoto. Depois de mudar o código, rode `.venv/bin/python editor.py testar`, que testa todas as marcas e precisa terminar em `TUDO OK`. Só use `testar --marca <marca> --atualizar` quando a mudança visual for intencional e só na marca que você mudou. Termine com um commit explicando a mudança.

## 2. O EDL (`edl.json`): onde você toma as decisões

Todos os tempos estão na linha do tempo do vídeo **original** (os mesmos da `transcricao.txt`). O renderizador recalcula tudo depois dos cortes.

```jsonc
{
  "marca": "pontes_brain",             // identidade em marcas/pontes_brain.json (o mesmo editor serve o GiraHub)
  "formato": "vertical",
  "segmentos": [                       // trechos que FICAM, em ordem. Apague os que saem.
    {"id": 3, "ini": 16.84, "fim": 20.78,
     "zoom": 1.0,                      // enquadramento base: deixe 1.0 (no máx. 1.08); muda devagar entre cortes
     "transicao": null}                // entrada deste trecho: null (corte seco) | "push" | "zoom" | "slide" | "flash"
  ],
  "zooms": [                           // ênfases dentro de um trecho
    {"ini": 13.6, "fim": 14.4, "fator": 1.2, "modo": "punch"},   // punch = tranco curto numa palavra, volta antes do corte
    {"ini": 27.2, "fim": 32.0, "fator": 1.12, "modo": "suave"}   // suave = aproximação lenta
  ],
  "fundo": {"tipo": "original",        // original | desfoque | marca | imagem
            "variante": "marinho",     // (marca) marinho | papel
            "imagem": null,            // (imagem) caminho
            "parallax": true, "sombra": true},
  "cor": {"contraste": 1.05, "saturacao": 1.06, "calor": 0.03, "nitidez": 0.25},
  "audio": {"denoise": true, "denoise_db": 10, "presenca_db": 1.0, "loudness": -16, "sfx_transicoes": true},
  "legendas": {"ativo": true, "palavras_por_bloco": 3, "posicao_y": 0.68, "maiusculas": false,
               "enfase": ["diagnóstico", "PDCA"],          // palavras em champanhe
               "correcoes": {"porque": "por que"}},        // conserta erros do Whisper
  "elementos": [                     // ancore pela FALA: "na" = palavra(s) onde entra, "ate" = onde sai
    {"tipo": "titulo",   "texto": "O que é o Pontes Brain?", "na": "do que é", "segura": 2.2},   // wipe + palavras subindo + giro 3D
    {"tipo": "destaque", "texto": "Mentoria", "na": "mentoria", "ate": "área", "y": 0.08, "tam": 50},  // rótulo champanhe com mola
    {"tipo": "objeto3d", "nome": "claude",  "na": "inteligência artificial", "ate": "superlegal", "x": 0.17, "y": 0.27},
    {"tipo": "objeto3d", "nome": "chatgpt", "na": "artificial", "ate": "superlegal", "x": 0.83, "y": 0.27, "fase": 1.4},
    {"tipo": "leo", "pose": "pensando", "lado": "direita", "na": "será que", "ate": "funciona"},
    {"tipo": "imagem", "arquivo": "print.png", "largura": 0.7, "y": 0.35, "ini": 40, "fim": 44},
    {"tipo": "broll", "arquivo": "tela.mp4", "ini": 50, "fim": 54}   // cobre a tela inteira, a voz continua
  ],
  "intro": {"ativo": true, "duracao": 2.2},   // vinheta padrão @pontes_brain: SEMPRE ligada
  "marca_dagua": true, "barra_progresso": true,
  "cta": {"ativo": true, "duracao": 3.5, "chamada": "Quer destravar seu produto?",
          "url": "leopontes.com.br/mentoria-produto", "pose_leo": "apontando"}
}
```

Âncoras: `na` (texto exato da transcrição; `ocorrencia` se repetir), `ate` (sai no fim dessa fala), `antecipa` (padrão 0,12 s antes da palavra), `segura` (quanto fica depois). Use `ini`/`fim` só quando não houver fala para ancorar.
Objetos 3D em `assets/3d/` (logos extrudados que entram girando, flutuam e saem girando): `claude`, `chatgpt`. Para criar outro, salve a face do logo em PNG transparente em `assets/3d/<nome>.png` (o `editor.py` faz a espessura, a luz e o reflexo).
Poses do Leo disponíveis em `assets/leo/`: `apontando`, `joinha`, `pensando`, `surpreso`, `talk-aberta`, `talk-fechada`, `talk-o`, `talk-piscada`.
Opcionais: `x`/`y` (0 a 1) e `altura` (fração da tela) em qualquer elemento. As animações já vêm prontas: título abre em wipe com palavras subindo e leve giro 3D; destaque cresce do centro com mola; Leo entra deslizando com giro, flutua e sai; legenda surge palavra a palavra com a marcação champanhe deslizando; zoom `punch` dá um tranco curto; o fundo `marca` tem luz ambiente difusa e um ponto percorrendo o ciclo PDCA. Cada elemento de texto ganha um "pop" sonoro discreto (`"sfx_elementos": false` desliga).

## 3. Identidade da marca (não negociável)

A identidade abaixo já está em `marcas/pontes_brain.json` (cores, fontes, logo, vinheta, fundo, CTA). Sempre rode `analisar` com `--marca pontes_brain` e confira que o `edl.json` tem `"marca": "pontes_brain"`. Vídeos do GiraHub usam a skill `editor-video-girahub`, nunca esta.

- Paleta **Papel & Marinho**: marinho `#14213D`, marinho 2 `#22305A`, champanhe `#D4B98C`, bronze `#94733D`, papel `#F2EEE6`, papel claro `#FFFDF8`. Nada de cores fora disso nos gráficos.
- Fonte **Roboto** (Black para títulos e legendas, Bold para rótulos). Cantos com raio de 8 a 12 px, nunca pílula.
- Logo **Monograma LP** (`assets/lp-simbolo-claro.png` em fundo escuro, `lp-simbolo-escuro.png` em fundo claro).
- Metodologia: 4 gates como ciclo PDCA (G1 Intake · Plan, G2 Business case · Plan, G3 Delivery · Do, G4 Benefits · Check · Act). Use esses nomes exatos quando o assunto aparecer.
- **Sem música.** O Leonardo coloca a música no Instagram. Efeitos sonoros curtos (whoosh nas transições) são permitidos.
- **Todo vídeo abre com a vinheta padrão** (`intro`, ~2,2 s: os 4 gates do PDCA se desenham, o Monograma LP é traçado, o ponto champanhe entra, "Leonardo Pontes · Mentoria de produto · Diagnóstico" e a câmera mergulha no símbolo até a primeira fala). Não desligue nem mude sem pedido do Leonardo. Prévia em `assets/vinheta-pontes-brain.mp4`.
- **Todo vídeo termina com CTA** para `leopontes.com.br/mentoria-produto`.
- Tom: direto, didático, confiante, sem exagero. Nada de emoji nos gráficos.

## 4. Processo

### Fase 1: análise
1. Rode `editor.py analisar <VIDEO> --marca pontes_brain`.
2. Leia `transcricao.txt` inteira antes de decidir qualquer coisa. Entenda a mensagem central do vídeo em uma frase.

### Fase 2: cortes (o que mais muda a qualidade)
3. **Silêncios** já vêm cortados no rascunho (pausas ≥ 0,35 s viram corte, com 80 ms de respiro). Não diminua o respiro abaixo de 0,05 s, senão a fala fica atropelada.
4. **Retakes**: quando uma frase se repete ou é recomeçada, fique **só com a última versão completa** e apague as anteriores. Se o Leonardo disser "corta", "de novo" ou "vou repetir", apague tudo desde o início da frase interrompida até essa palavra, inclusive.
5. **Muletas**: remova "é…", "tipo", "né", "ãh", "então…" soltos no começo de frase quando não fizerem falta. Para cortar no meio de um segmento, divida-o em dois usando os tempos das palavras em `analise.json`.
6. **Gancho**: os primeiros 2 segundos decidem tudo. Se a frase mais forte estiver no meio do vídeo e fizer sentido sozinha, você pode **duplicá-la** como abertura: copie o segmento para o topo da lista com `"gancho": true` (o original continua no lugar). Elementos sobre o gancho usam `"saida": [ini, fim]` em segundos do vídeo final, em vez de `ini`/`fim`. Nunca invente fala nem mude o sentido do que ele disse.
7. Meta de duração: Reels de 20 a 60 s. Se passar de 90 s, aponte no resumo quais trechos poderiam virar outro vídeo, mas não corte conteúdo essencial por conta própria.

### Fase 3: ritmo visual
8. **Enquadramento contínuo (obrigatório)**: em todo corte o Leonardo precisa continuar na mesma posição e no mesmo tamanho em que estava antes. **Não alterne o zoom entre segmentos** para esconder jump cut: deixe `zoom` 1.0 em todos (no máximo 1.08 num trecho específico); o editor já segue o rosto e muda o zoom-base devagar de um corte para o outro. Variação de tamanho só com `zooms` explícitos: `punch` (1.15 a 1.22) numa palavra de impacto e `suave` (1.1 a 1.15) em explicação longa, sempre **dentro** de um trecho e terminando pelo menos 0,4 s antes do corte (o editor força isso). Nada de punch nos 0,5 s finais de um trecho. Na conferência, compare o último quadro antes e o primeiro depois de **cada** corte: o rosto tem que estar no mesmo lugar.
9. **Transições**: só em **mudança de assunto** (no máximo 1 a cada 10 a 15 s). `push` (empurra para o lado com borrão de movimento) para virada de tópico, `zoom` (mergulho com desfoque) para "agora o ponto principal" e para entrar no CTA, `slide` (empurra para cima) para lista ou próximo passo, `flash` para revelação. Entre frases do mesmo assunto, corte seco.
10. **Elementos: cada efeito precisa de um motivo na fala.** Antes de colocar qualquer coisa, escreva para si mesmo a palavra que dispara o efeito e por quê. Sem motivo, sem efeito.
    - **Timing**: o efeito entra na palavra que o justifica (ancore com `na`, ele entra 0,12 s antes) e sai quando aquela ideia termina (`ate`). Nunca entra no meio de uma palavra, nunca aparece antes do assunto ser mencionado e nunca fica depois que ele mudou de assunto. Deixe pelo menos 0,8 s de respiro entre um efeito e o próximo, e não coloque efeito novo nos 0,3 s de uma transição.
    - `titulo` quando ele anuncia o tema ("o que é…", "hoje vou mostrar…"), ou no gancho. Até 6 palavras. Enquanto o título estiver na tela, use zoom de no máximo 1.1 para ele não cobrir a testa.
    - `destaque` quando ele nomear uma pessoa, conceito, gate, número, @ ou site. Texto curto, de até 4 palavras. Quando ele listar itens ("mentoria, diagnóstico e experiência"), empilhe os destaques (`y` 0.08, 0.14, 0.20, `tam` 50): cada um entra na sua palavra e todos saem juntos no fim da lista.
    - `objeto3d` quando ele citar uma marca ou ferramenta que tenha logo em `assets/3d/` (ex.: Claude e ChatGPT ao falar de IA). Dois objetos, um de cada lado da cabeça, entrando com 0,2 a 0,4 s de diferença.
    - `leo` só quando houver contexto narrativo claro: o Leo reage a algo que foi dito (pergunta, dúvida, conclusão) e a pose combina com a fala. Na dúvida, não use. Nunca como enfeite solto.
    - No máximo 1 grupo de texto na tela ao mesmo tempo, além da legenda.
11. **Legendas**: sempre ligadas. Revise a transcrição e preencha `correcoes` (nomes, termos em inglês, "por que" e "porque", números). Marque em `enfase` de 3 a 6 palavras-chave do vídeo.

### Fase 4: imagem e som
12. **Fundo**: se o fundo gravado estiver bagunçado ou com pouca luz, use `marca` (marinho com o ciclo PDCA em traço fino) ou `desfoque`. O recorte usa Robust Video Matting (`modelos/rvm_mobilenetv3_fp32.onnx`), que limpa cabelo e bordas e remove o vazamento de cor do ambiente. Se estiver limpo e bonito, deixe `original`. Confira as bordas do recorte (cabelo, ombros, mãos) na prévia; se ficarem ruins, volte para `desfoque`.
13. **Cor**: o padrão é natural. Pele com aparência doentia ou azulada pede `calor` entre 0.04 e 0.06. Vídeo lavado pede `contraste` entre 1.08 e 1.12. Não passe de `saturacao` 1.12.
14. **Áudio (nunca estourar)**: o padrão é conservador e não deve ser "aumentado": passa-altas de 80 Hz, redução de ruído leve (`afftdn`, 10 dB), −2 dB em 250 Hz, +1 dB de presença, de-esser, compressão leve (2,5:1), loudnorm em **duas passadas** em **−16 LUFS** e limitador no fim com teto em −2 dBFS (depois dos efeitos sonoros). Nunca suba `presenca_db` acima de 2, nunca use `loudness` acima de −14 e não ligue compressão extra. Se a voz ainda soar áspera ou "estourada", o problema está na gravação (microfone saturado ou áudio comprimido do WhatsApp): baixe `denoise_db` para 6, rode `renderizar --so-audio` para refazer só o som em segundos, e avise o Leonardo. Na conferência, meça: `ffmpeg -i final.mp4 -af ebur128=peak=true -f null -` precisa dar I entre −17 e −15 LUFS e pico abaixo de −1,5 dBFS.

### Fase 5: conferência (obrigatória antes de entregar)
15. Rode `renderizar --rapido`, **abra `previa.jpg`** e confira:
    - rosto sempre enquadrado, olhos no terço superior, sem cortar o queixo nem o topo da cabeça em zoom;
    - textos dentro da área segura (sem nada importante nos 12% de cima nem nos 20% de baixo da tela, nem colado na borda direita);
    - nenhum elemento cobrindo o rosto; legenda legível sobre qualquer fundo;
    - CTA final aparecendo com URL legível.
16. Extraia quadros nos tempos de cada transição e elemento e confira de perto. Corrija o `edl.json` e renderize de novo até ficar limpo. No máximo 3 rodadas; se ainda houver problema, entregue e descreva o que falta.
17. Rode o render final, sem `--rapido`.

### Fase 6: entrega
18. Renomeie a saída para `AAAA-MM-DD-<tema-curto>.mp4` na pasta do vídeo.
19. Escreva `legenda.txt` com: gancho na primeira linha, 2 a 4 linhas de valor, CTA para `leopontes.com.br/mentoria-produto` (link na bio) e 3 a 5 hashtags relevantes (#gestaodeprodutos #productmanagement #mentoria …).
20. Responda ao Leonardo em até 10 linhas: duração final (antes → depois), o que foi cortado (retakes, silêncios), principais escolhas (fundo, elementos, transições) e qualquer ponto que ele deva olhar.

## 5. Limites

- Não invente fala, não reordene frases a ponto de mudar o argumento e não remova ressalvas que ele fez.
- Não adicione música nem use material de terceiros sem licença.
- Não publique nada. A publicação é sempre do Leonardo.
- Se o vídeo tiver um problema que a edição não resolve (áudio estourado, foco errado, rosto fora do quadro a maior parte do tempo), avise logo na Fase 1 e sugira regravar, em vez de entregar algo ruim.
