# Editor de vídeo do @pontes_brain

Edição automática de vídeos em que você fala para a câmera: corte de silêncios e retakes, legendas animadas, zoom, troca de fundo com parallax, títulos com entrada 3D, Leo 3D, transições com whoosh, correção de cor, limpeza de voz (−14 LUFS) e CTA final. Tudo local e gratuito.

## Instalar (uma vez, ~10 min)

1. Copie esta pasta `edicao-video` para o Mac (ex.: `~/Documents/Dev/edicao-video`).
2. No Terminal: `cd ~/Documents/Dev/edicao-video && bash setup-mac.sh`
   Instala ffmpeg e Python via Homebrew, as bibliotecas e baixa os modelos (~500 MB).

## Usar

Abra o Claude Code nessa pasta e diga:

> Edite ~/Movies/meu-video.mov seguindo PROMPT-MESTRE.md

O agente analisa, decide os cortes e efeitos, confere a prévia e entrega `AAAA-MM-DD-tema.mp4` + `legenda.txt`.

## Dicas de gravação (fazem mais diferença que qualquer efeito)

- Celular na **vertical**, 1080p ou 4K a **30 fps**. Desligue o vídeo HDR (Ajustes › Câmera › Gravar Vídeo › HDR) para as cores ficarem previsíveis; se esquecer, o editor converte.
- Câmera na altura dos olhos, rosto no terço superior, um palmo de espaço acima da cabeça (o zoom precisa de folga).
- Luz de frente (janela ou ring light), nada de janela atrás de você.
- Para trocar o fundo, ajuda ter contraste entre você e a parede. Fundo liso dá recorte mais limpo.
- Microfone de lapela, se tiver. Ambiente sem eco vale mais que filtro.
- Errou? Faça uma pausa e repita a frase inteira. O agente fica com a última versão. Pode dizer "corta" antes de repetir.
- Deixe 1 segundo parado no começo e no fim.

## Arquivos

- `PROMPT-MESTRE.md`: as instruções do agente (o "editor").
- `editor.py`: o motor (`analisar` e `renderizar`). O agente pode estendê-lo.
- `assets/`: logo LP, fontes Roboto e poses do Leo. `modelos/`: recorte de fundo, rosto e redução de ruído.
- `exemplo-*`: teste feito com um vídeo simulado (sua foto + voz sintética), só para mostrar o resultado.

## Marcas (@pontes_brain e GiraHub)

O mesmo `editor.py` edita vídeos das duas marcas. A identidade de cada uma fica em `marcas/<marca>.json` (cores, fontes, logo, vinheta, fundo, CTA, vocabulário do Whisper):

- `--marca pontes_brain` (padrão): Papel & Marinho, Roboto, Monograma LP, vinheta PDCA, Leo. Skill `editor-video-pontes-brain` (`SKILL.md`).
- `--marca girahub`: paleta terra, Fraunces + Inter, ticket em ouro, vinheta do ticket (`assets/vinheta-girahub.mp4`), sem Leo. Skill `editor-video-girahub` (`SKILL-girahub.md`).

Exemplo: `.venv/bin/python editor.py analisar ~/Movies/gira.mov --marca girahub`

## Marca nova e testes

- **Marca nova**: copie `marcas/modelo.json` para `marcas/<id>.json` e troque as cores, as fontes, o logo (PNG transparente em `assets/<id>/`), o nome, o CTA e o vocabulário. Com `"intro": {"tipo": "logo"}` e `"fundo_motivo": "anel"` (ou `"nenhum"`), a vinheta e o fundo saem prontos, sem programar nada. Uma vinheta sob medida, como as do PDCA e do ticket, é opcional.
- **Teste**: `.venv/bin/python editor.py testar` compara a folha visual de cada marca com `testes/referencia/` e roda um render completo de 4 s, medindo o áudio (−17 a −15 LUFS, pico < −1,5 dBFS). Rode sempre depois de mudar o `editor.py`.
- **Velocidade**: no Mac, o recorte usa o CoreML (Neural Engine/GPU) quando disponível e volta para a CPU sozinho se der erro. O progresso mostra quadros por segundo e o tempo restante.
