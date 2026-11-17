# Estilos de referência

Três estilos de edição estudados em Reels de outros criadores (gravações de tela do Instagram, novembro de 2026). Cada
estilo vira uma receita: o que se vê, os números medidos e como montar no EDL. O motor faz os três: `"estilo"` no EDL
(ou `analisar --estilo`), planos e looks por segmento e os elementos de motion descritos em [edl.md](edl.md#estilos-planos-e-looks).
As receitas não carregam a identidade de ninguém: cores, fontes e CTA vêm sempre da marca do vídeo (`marcas/<id>/`).

Como foi medido: cortes por detecção de cena do ffmpeg (`select='gt(scene,0.2)'`), quadros a cada 0,5 s a 2 s,
transcrição com `faster-whisper small` com tempo por palavra, e volume das pausas entre palavras para saber se há trilha.

| | A. Tela em perspectiva | B. Tutorial em passos | C. Vitrine de estilos |
|---|---|---|---|
| Duração | 71 s | 74 s | 44 s (gravação começou no meio) |
| Fala | 241 palavras/min, narração | 267 palavras/min, para a câmera | 221 palavras/min, para a câmera |
| Cortes de plano | 1 (só no fim) | 17 cortes + troca de motion a cada 1 a 3 s | 32 (um a cada 1,4 s) |
| Maior pausa mantida | 0,78 s | 0,44 s | 0,38 s |
| Trilha | Cama baixa (pausas a −35 dB) | Nenhuma (pausas a −40 dB) | Música e efeitos o tempo todo (pausas a −27 dB) |
| Legenda corrida | Não | Sim, 1 ou 2 palavras | Não; a tipografia é cenográfica |
| Serve para | Demonstrar produto, sistema, painel | Ensinar passo a passo | Anúncio, lançamento, mostrar alcance |

## A. Tela em perspectiva

Narração por cima de uma gravação de tela que parece filmada por uma câmera de cinema. O rosto só aparece no fim.

**O que se vê**

- **Gancho (0 a 3 s):** título em duas linhas no canto superior esquerdo, texto preto em sans bold sobre caixas brancas
  justas, uma por linha, com um colchete fino na cor de acento abraçando o canto. Some antes de a tela começar a andar.
- **Tela num plano 3D:** a gravação de tela (interface escura) fica num plano inclinado, com a câmera virtual fazendo
  travelling, inclinação e aproximação. Profundidade de campo rasa: a borda do plano desfoca, o centro fica nítido.
- **Luz quente:** um bokeh laranja grande e fixo à esquerda, como reflexo de luminária no vidro. Dá calor a uma UI fria.
- **Ritmo sem corte:** um único plano por 67 s; o movimento de câmera muda a cada 2 a 4 s (novo enquadramento, novo foco),
  sempre indo para o elemento que a fala cita ("marketing", "vendas", "integrações").
- **Fecho (últimos 3,5 s):** corte seco para o rosto, fala curta com o CTA verbal ("a metodologia está aqui embaixo").
- **Áudio:** voz limpa, cama musical muito baixa. Sem efeitos sonoros perceptíveis.

**Como montar**

```jsonc
"estilo": "tela_perspectiva",
"elementos": [
  {"tipo": "titulo_caixa", "texto": "Uma empresa inteira / com Inteligência Artificial", "ini": 0, "fim": 2.8, "x": 0.42, "y": 0.1},
  {"tipo": "broll", "arquivo": "tela.mp4", "na": "esse aqui", "ate": "metodologia",
   "perspectiva": {"foco": 0.6, "luz": true, "camera": [
     {"t": 0, "rx": 24, "ry": -20, "zoom": 1.2, "cx": 0.3, "cy": 0.3},     // "um cérebro": o grafo
     {"t": 0.4, "rx": 14, "ry": 6, "zoom": 1.5, "cx": 0.5, "cy": 0.55},    // "marketing": os cartões
     {"t": 1, "rx": 10, "ry": 16, "zoom": 1.6, "cx": 0.62, "cy": 0.7}]}}  // "integrações"
]
```

O último segmento (o rosto falando o CTA) fica sem b-roll. Música baixa (`volume_db` −26) onde a marca permite.

## B. Tutorial em passos

Tutorial falado em quatro passos, com uma folha de estilo explícita (aparece no próprio vídeo). É o estilo mais fácil
de copiar e o mais útil para vender como produto, porque é uma regra simples aplicada com disciplina.

**Três planos, troca em corte seco**

| Plano | Quando | Composição |
|---|---|---|
| Rosto | Opinião, gancho, conversa | Câmera ocupa a tela inteira |
| Dividido | Explicando algo que dá para mostrar | Metade de cima: fundo escuro com motion. Metade de baixo: o rosto |
| Só motion | Quando a imagem explica sozinha | Tela inteira de motion; a voz continua |

A troca entre planos é sempre corte seco, sem transição. Regra do vídeo: **nada parado por mais de três segundos**; dentro
de um plano, o motion muda de estado (ícone entra, pasta abre, linha se desenha) a cada 1 a 2 s.

**Legenda**

- 1 ou 2 palavras por vez, sem caixa e sem contorno pesado, branco quase puro, sans semibold, em caixa normal.
- Posição: na linha que divide os planos (no dividido) ou em torno de 62% da altura (rosto cheio).
- Sem palavra em destaque: o motion faz a ênfase.

**Cabeçalho de passo**

- No topo do motion, sempre visível enquanto o passo dura: `Passo 1.` em serifa itálica + `Monta o ambiente` em sans bold.
- Regra tipográfica: sans no texto do passo, serifa só no número.

**Motion**

- Fundo quase preto e liso, superfície um tom acima. Paleta medida: fundo `#0B0B0C`, superfície `#151517`, texto
  `#F5F5F3`, cinza `#A3A3A8` e um único acento (no vídeo, vermelho).
- **Objeto externo leva a identidade dele:** pasta azul do sistema, ícone colorido do app, janela do app como ela é,
  com sombra e profundidade. O que é da marca fica na cor da marca; o resto, na cor dele.
- Recursos usados: ícone que entra com mola, nome de pasta digitado letra a letra, árvore de pastas que se desenha,
  janela de app (com os três pontos do macOS) mostrando o prompt com trechos marcados em amarelo, cartões de lista,
  storyboard rolando.
- **Recapitulação:** no fim, os quatro passos voltam ao redor do objeto central, ligados por linhas pontilhadas.

**Gancho e CTA**

- Gancho (0 a 10 s): título de duas linhas no topo, sobre o rosto, e três miniaturas de Reels de referência passando como
  carrossel na altura do peito. Promessa forte: "todo mundo faz, ninguém conta como".
- CTA de comentário: o rosto volta e aparece uma barra de comentário com a palavra-chave sendo digitada ("Comenta MOTION").

**Áudio:** só voz, limpa e alta (−17 dB RMS), sem música. Pausas cortadas até sobrar no máximo 0,4 s.

**Como montar**

```jsonc
"estilo": "tutorial_passos",
"segmentos": [
  {"id": 0, "ini": 0.0, "fim": 10.6, "plano": "rosto"},
  {"id": 1, "ini": 10.8, "fim": 14.8, "plano": "dividido"},
  {"id": 2, "ini": 15.2, "fim": 23.3, "plano": "motion"}
],
"elementos": [
  {"tipo": "titulo_caixa", "texto": "Tudo que você precisa / pra editar vídeo com IA", "ini": 0, "fim": 10.5, "y": 0.08},
  {"tipo": "carrossel", "arquivos": ["ref1.jpg", "ref2.jpg", "ref3.jpg"], "ini": 0, "fim": 10.5, "y": 0.28},
  {"tipo": "passo", "numero": 1, "texto": "Monta o ambiente", "na": "Primeiro", "ate": "acabou de criar"},
  {"tipo": "icone", "arquivo": "icones/app.png", "rotulo": "Claude Code", "na": "Claude Code", "segura": 1.5},
  {"tipo": "digitacao", "texto": "Editor de vídeo com IA", "caixa": true, "na": "chama de"},
  {"tipo": "arvore", "raiz": "Editor de vídeo com IA", "filhos": ["Vídeo bruto", "Referências", "Vídeos prontos"], "na": "três subpastas"},
  {"tipo": "janela", "titulo": "Como posso ajudar?", "linhas": ["Corta toda pausa maior que [[0,15 s]]."], "na": "esse prompt"},
  {"tipo": "mapa", "centro": "Editor de vídeo com IA", "itens": ["Passo 1. Monta o ambiente", "Passo 2. Instala as ferramentas",
   "Passo 3. Trava o seu estilo", "Passo 4. Grava e edita"], "na": "fluxo inteiro"},
  {"tipo": "comentario", "texto": "MOTION", "na": "Comenta"}
]
```

O que ainda é manual: os ícones de app são PNGs que você traz (o motor desenha pasta, documento e pessoa na paleta da
marca), e o storyboard rolando entra como `broll` de uma gravação de tela.

## C. Vitrine de estilos

Anúncio de alta produção: cada frase ganha um visual diferente para provar que "dá para fazer de tudo". Funciona como
peça de lançamento; para conteúdo do dia a dia é cansativo.

**O que se vê (um look a cada 1,5 a 3 s)**

- **Palavra atrás da pessoa:** palavras enormes em sans condensada laranja, entrando por partes, com o corpo da pessoa
  recortado por cima. Imagem em preto e branco; só a tipografia tem cor.
- **Anotações de interface:** rótulos pequenos em fonte mono ("+ E NÃO SÃO", "pa·la·vra s.f. unidade de sentido",
  "ELEMENTOS +41"), riscos, cruzes de mira, contador subindo.
- **Chuva de objetos 3D** e cartões de interface (curtidas, gráfico, chat) em volta da cabeça.
- **Título editorial:** "O ESTILO ① *das* PALAVRAS", misturando sans bold amarela e manuscrito itálico, com número circulado.
- **Recorte com contorno:** pessoa recortada em preto e branco, contorno vermelho rabiscado, coroa desenhada à mão,
  bloco mostarda chapado e letras de bilhete de resgate ("COMPLETAMENTE").
- **Look esportivo:** faixa diagonal magenta e texto condensado girado 90°. **Look calmo:** fundo branco com halo
  circular, legenda em serifa itálica fina, tudo dessaturado.
- **Rastreamento facial e corporal como efeito:** malha de pontos no rosto, anéis sobre os óculos, esqueleto laranja
  ligando as articulações, objeto em pixel art preso na ponta do dedo, rótulos mono ("RASTREAMENTO FACIAL", "CORPO 13
  ARTICULAÇÕES").
- **Som visível:** cada efeito sonoro aparece como uma onda laranja com o nome ("WHOOSH", "SWISH", "CATRACA",
  "OBTURADOR", "RISE", "IMPACTO", "PLOP") no exato instante em que toca.
- **Tela do produto** com o rosto numa bolha circular de borda laranja no canto inferior esquerdo.
- **CTA em neon:** "CLICA EM SAIBA MAIS" escrito à mão em neon laranja que acende com tremulação e troca de cor no fim.
- Cenas geradas por IA (escritório com vista, estúdio de mixagem, corrida na orla) intercaladas com a câmera real.

**Áudio:** música o tempo todo, efeito sonoro em quase todo corte e elemento.

**Como montar**

```jsonc
"estilo": "vitrine",
"segmentos": [
  {"id": 0, "ini": 0.0, "fim": 3.2, "look": "pb_acento"},
  {"id": 1, "ini": 3.2, "fim": 5.0, "look": "adesivo", "transicao": "whip"},
  {"id": 2, "ini": 5.0, "fim": 7.6, "look": "noite", "transicao": "flash"},
  {"id": 3, "ini": 7.6, "fim": 10.8, "look": "limpo"}
],
"elementos": [
  {"tipo": "texto_atras", "texto": "SÓ / PALAVRAS", "na": "só palavras", "segura": 1.0},
  {"tipo": "anotacao", "texto": "+ E NÃO SÃO", "na": "não são", "x": 0.3, "y": 0.08},
  {"tipo": "titulo_editorial", "partes": [{"t": "O ESTILO"}, {"t": "das"}, {"t": "PALAVRAS"}], "numero": 1, "na": "o estilo"},
  {"tipo": "bilhete", "texto": "COMPLETAMENTE", "na": "completamente"},
  {"tipo": "hud_rosto", "rotulo": "RASTREAMENTO FACIAL", "na": "rastreamento", "ate": "efeito aqui"},
  {"tipo": "som", "nome": "whoosh-rapido", "rotulo": "WHOOSH", "na": "efeitos sonoros", "x": 0.7, "y": 0.3},
  {"tipo": "broll", "arquivo": "plataforma.mp4", "na": "aulas", "ate": "fácil", "bolha": {"x": 0.22, "y": 0.8}},
  {"tipo": "neon", "texto": "CLICA EM / SAIBA MAIS", "na": "Clica aqui", "y": 0.75}
]
```

O que ainda não faz: esqueleto do corpo com objeto preso no dedo (precisa de um modelo de pose) e as cenas geradas por IA
(entram como `broll` prontos).

## Próximos passos para o produto

1. Ícones de apps conhecidos prontos numa biblioteca (com licença de uso de marca checada), para o estilo B não depender de PNG.
2. Modelo de pose (MediaPipe Pose) para o esqueleto do corpo e objetos presos às mãos no estilo C.
3. Câmera da tela em perspectiva ancorada na fala (`"na"` em cada ponto-chave) em vez de `t` de 0 a 1.

## Regras que valem para os três

- O gancho mostra o assunto em texto nos primeiros 2 s e promete algo concreto.
- Corte de pausa agressivo: nenhuma pausa acima de 0,4 s, exceto antes do CTA.
- Cada elemento entra na palavra exata da fala que o justifica e sai quando a ideia termina.
- Uma só cor de acento por vídeo; o resto em tons neutros ou na cor própria do objeto mostrado.
- O CTA é falado e escrito ao mesmo tempo.
