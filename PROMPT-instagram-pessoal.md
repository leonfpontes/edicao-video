Quero usar neste projeto (Instagram pessoal, @leopontesrp) o editor de vídeo automático que criei no projeto da mentoria. Leia tudo antes de começar.

**O que é**
Um editor de vídeo local e gratuito para vídeos em que eu falo para a câmera. Um agente (você, rodando no Claude Code no meu Mac) faz a edição inteira sem eu mexer em nada: corta silêncios e retakes, gera legendas palavra a palavra, enquadra o rosto sem saltos entre os cortes e aplica zoom, títulos e destaques ancorados na fala. Também faz transições, troca o fundo (recorte com Robust Video Matting), trata o áudio (-16 LUFS, sem estourar), abre com uma vinheta e fecha com um CTA. Ele usa ffmpeg, faster-whisper, MediaPipe, OpenCV e onnxruntime. Não precisa de nenhum serviço pago.

**Onde está**
- A pasta `edicao-video` fica no meu Mac em `~/Documents/Dev/edicao-video`. Se não achar, procure com `find ~ -maxdepth 4 -name editor.py -path "*edicao-video*"`. Se ainda assim não existir, me peça para copiá-la do projeto da mentoria.
- Arquivos principais:
  - `editor.py`: o motor, com os comandos `analisar` e `renderizar`;
  - `SKILL.md`: o processo completo de edição, que é a referência;
  - `marcas/*.json`: a identidade de cada marca;
  - `assets/`: fontes, logos, objetos 3D e vinhetas;
  - `modelos/`: os modelos de IA;
  - `setup-mac.sh`: a instalação;
  - `LEIA-ME.md`: as instruções de uso.
- O motor já suporta várias marcas. Hoje existem `pontes_brain` (mentoria: Papel & Marinho, Roboto, monograma LP, vinheta PDCA, personagem Leo) e `girahub` (paleta terra, Fraunces, ticket). As duas pertencem a outros projetos e **não devem ser alteradas nem reaproveitadas aqui** sem o meu ok. Isso vale para o Leo, o PDCA, o monograma LP e o ticket.

**Instalação (uma vez)**
Na pasta, rode `bash setup-mac.sh`. Ele instala o ffmpeg e o Python 3.12 via brew, cria o `.venv` e baixa os modelos. Depois disso, use sempre `.venv/bin/python editor.py …`.

**O que eu quero que você faça**
1. Leia `SKILL.md`, `LEIA-ME.md`, `marcas/pontes_brain.json` e as funções `carregar_marca`, `quadro_intro`, `FundoMarca` e `cartao_cta` do `editor.py`, para entender como funciona uma marca.
2. Antes de criar qualquer coisa, me pergunte sobre a identidade da conta pessoal:
   - qual é o objetivo da conta e quem é o público;
   - o tom de voz;
   - a paleta (ou se uso alguma existente);
   - a fonte;
   - se tem logo ou assinatura;
   - qual é o CTA e o link;
   - se uso música e hashtags.
   Faça poucas perguntas, com uma sugestão sua para cada uma.
3. Com as minhas respostas:
   - crie `marcas/leopontesrp.json` (cores como papéis: "marinho" é a cor escura, "champanhe" o destaque e "papel" a cor clara; fontes de título e de texto em `assets/fontes/`, logo, CTA, vocabulário do Whisper, `"leo": false`);
   - crie uma vinheta própria de cerca de 2,2 s e um motivo de fundo próprio, estendendo `editor.py` no mesmo estilo de `_intro_ticket` e do motivo `ticket`, sem quebrar as marcas existentes;
   - renderize uma prévia da vinheta em `assets/vinheta-leopontesrp.mp4` e me mostre.
4. Escreva uma skill `editor-video-leopontesrp` a partir de `SKILL.md`. Mantenha o processo de edição (cortes, enquadramento contínuo, timing dos efeitos pela fala, áudio sem estourar, conferência pela `previa.jpg`) e troque a identidade, o público, o tom, a legenda do post e o CTA pelos desta conta. Ela sempre usa `analisar --marca leopontesrp`. Proponha a skill para eu salvar.
5. Teste num vídeo meu: rode `analisar`, edite o `edl.json`, rode `renderizar --rapido`, confira a prévia e faça o render final. Meça o áudio com `ffmpeg -i final.mp4 -af ebur128=peak=true -f null -`: o resultado deve ficar entre −17 e −15 LUFS, com pico abaixo de −1,5 dBFS.
6. Guarde na memória deste projeto que a edição de vídeo usa essa skill e essa marca.

**Regras que valem para todas as marcas**
- Recorte de fundo limpo.
- Efeitos entram na palavra certa e saem quando a ideia acaba.
- Elementos só com contexto na fala.
- Enquadramento contínuo entre os cortes.
- Áudio sem estourar.
- Vinheta em todo vídeo.
- Nada é publicado sem o meu ok.
- Mande arquivos originais, não do WhatsApp, que chegam em 480p.
