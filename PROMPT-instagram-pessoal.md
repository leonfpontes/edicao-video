Quero usar neste projeto (Instagram pessoal, @leopontesrp) o editor de vídeo automático que criei no projeto da mentoria. Leia tudo antes de começar.

**O que é**
Um editor de vídeo local e gratuito para vídeos em que eu falo para a câmera. Você (Claude Code no meu Mac) faz a edição inteira sem eu mexer em nada:
- corta silêncios e retakes;
- faz legendas palavra a palavra;
- mantém o enquadramento contínuo entre os cortes;
- aplica zoom, títulos e destaques ancorados na fala, além de transições;
- troca o fundo com recorte por Robust Video Matting;
- trata o áudio (−16 LUFS, sem estourar);
- abre com uma vinheta e fecha com um CTA.

Ele usa ffmpeg, faster-whisper, MediaPipe, OpenCV e onnxruntime. Não precisa de nenhum serviço pago.

**Onde está**
- A pasta `edicao-video` fica no meu Mac em `~/Documents/Dev/edicao-video`. Se não achar, rode `find ~ -maxdepth 4 -name editor.py -path "*edicao-video*"`. Se não existir, me peça para copiá-la do projeto da mentoria.
- Ela é um **repositório Git compartilhado** com outras marcas. Se tiver remoto, rode `git pull` antes de começar e faça commit de tudo o que mudar.
- Arquivos que importam:
  - `editor.py`: motor, com os comandos `analisar`, `renderizar` e `testar`;
  - `SKILL.md`: o processo completo de edição, que é a referência;
  - `marcas/*.json`: a identidade de cada marca;
  - `marcas/modelo.json`: o ponto de partida para uma marca nova;
  - `assets/`, `modelos/`, `setup-mac.sh` e `LEIA-ME.md`.
- As marcas `pontes_brain` (Papel & Marinho, monograma LP, vinheta PDCA, personagem Leo) e `girahub` (paleta terra, ticket) pertencem a outros projetos. **Não altere nem reaproveite** essas marcas nem os elementos delas (Leo, PDCA, LP, ticket) sem o meu ok.

**Instalação (uma vez)**
Rode `bash setup-mac.sh` na pasta. Depois disso, use sempre `.venv/bin/python editor.py …`. Confirme que tudo funciona com `.venv/bin/python editor.py testar`, que precisa terminar em `TUDO OK`. Anote quantos quadros por segundo o render fez no meu Mac.

**O que eu quero que você faça**
1. Leia `LEIA-ME.md`, `SKILL.md` e `marcas/modelo.json`.
2. Antes de criar qualquer coisa, me pergunte em **uma única mensagem**, com uma sugestão sua para cada item:
   - o objetivo da conta e o público;
   - o tom de voz;
   - a paleta (3 a 5 cores);
   - as fontes do título e do texto (Google Fonts);
   - o logo ou a assinatura;
   - o nome e o subtítulo da vinheta;
   - a chamada e o link do CTA;
   - as hashtags.
3. Crie a marca:
   - copie `marcas/modelo.json` para `marcas/leopontesrp.json` e preencha. As cores são papéis: `marinho` é a cor escura, `champanhe` o destaque, `papel` a cor clara. Coloque `"leo": false` e o vocabulário do Whisper;
   - baixe as fontes (TTF) para `assets/fontes/`;
   - coloque o logo em PNG transparente em `assets/leopontesrp/`;
   - use `"intro": {"tipo": "logo"}` e `"fundo_motivo": "anel"` ou `"nenhum"`. Assim a vinheta e o fundo saem prontos **sem programar nada**. Só crie uma vinheta sob medida se eu pedir;
   - grave a referência com `editor.py testar --marca leopontesrp --atualizar`, abra `testes/referencia/leopontesrp.png` e me mostre;
   - renderize a vinheta em `assets/vinheta-leopontesrp.mp4`.
4. Crie a skill `editor-video-leopontesrp` a partir de `SKILL.md`.
   - Mantenha o processo de edição: cortes, enquadramento contínuo, efeitos no tempo da fala, áudio sem estourar, conferência pela `previa.jpg` e a regra de manutenção (rodar `testar` depois de qualquer mudança no `editor.py`).
   - Troque a identidade, o público, o tom, a legenda do post e o CTA pelos desta conta.
   - Ela sempre usa `analisar --marca leopontesrp`.
   - Proponha a skill para eu salvar.
5. Teste num vídeo meu, de preferência o arquivo original do iPhone:
   - rode `analisar`, edite o `edl.json`, rode `renderizar --rapido`, confira a prévia e faça o render final;
   - meça com `ffmpeg -i final.mp4 -af ebur128=peak=true -f null -`, que deve dar entre −17 e −15 LUFS, com pico abaixo de −1,5 dBFS.
6. Rode `editor.py testar` (todas as marcas precisam continuar `OK`) e faça o commit.
7. Guarde na memória deste projeto que a edição de vídeo usa essa skill e a marca `leopontesrp`.

**Regras que valem para todas as marcas**
- Recorte de fundo limpo.
- Os efeitos entram na palavra certa e saem quando a ideia acaba.
- Elementos só aparecem com contexto na fala.
- Enquadramento contínuo entre os cortes.
- Áudio sem estourar.
- Vinheta em todo vídeo.
- Nada é publicado sem o meu ok.
- Mande arquivos originais, não do WhatsApp, que chegam em 480p.
