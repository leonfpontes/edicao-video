"""Editor de vídeo automático multimarca (@pontes_brain, GiraHub, @leopontesrp…). Local e gratuito.

  editor.py analisar   VIDEO [VIDEO2 …] --marca <marca> [--pasta trabalho/] [--modelo small] [--sem-fala] [--estabilizar]
  editor.py renderizar trabalho/edl.json [--rapido] [--so-audio]
  editor.py testar     [--marca <marca>] [--atualizar] [--so-visual]
  editor.py marcas
  editor.py biblioteca listar 3d|musicas|efeitos|sons [termo] [--clima …] [--categoria …]
  editor.py biblioteca baixar [musicas [id …]|3d <nome-fluent>]
  editor.py biblioteca verificar
  editor.py biblioteca previa efeitos|3d|musicas --marca <marca>
  editor.py conferir   video.mp4 --marca <marca>

`analisar` normaliza o vídeo (30 fps, SDR), transcreve com Whisper (tempo por palavra), rastreia o rosto e
escreve trabalho/transcricao.txt + trabalho/edl.json (rascunho). O agente edita o edl.json (cortes, zooms,
fundo, elementos, efeitos, música, transições, CTA) e chama `renderizar`, que gera trabalho/final.mp4,
trabalho/previa.jpg (folha de contato), manifesto.json e, com música, creditos.txt.

Todos os tempos do edl.json estão na linha do tempo do vídeo ORIGINAL (a da transcrição). A identidade
visual vem de marcas/<marca>/marca.json; o edl.json guarda a marca em "marca" e o render recusa o EDL que
misture marcas (veja motor/guarda.py). As chaves de cor são papéis: "marinho" = cor escura de fundo/caixa,
"champanhe" = cor de destaque, "papel" = cor clara.
"""
__version__ = "2.1.0"
