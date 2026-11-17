"""Linha de comando (`python editor.py …`)."""
import argparse
import sys

from . import __doc__ as AJUDA
from .marca import ErroDeMarca


def main(argv=None):
    ap = argparse.ArgumentParser(prog="editor.py", description=AJUDA, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("analisar", help="normaliza, transcreve e escreve o rascunho do EDL")
    p.add_argument("video", nargs="+", help="um vídeo, ou vários clipes em sequência")
    p.add_argument("--marca", required=True, help="marca do vídeo (pasta marcas/<marca>/); obrigatória, não há padrão")
    p.add_argument("--pasta")
    p.add_argument("--sem-fala", action="store_true", help="vídeo sem fala: pula o Whisper e desliga as legendas")
    p.add_argument("--estabilizar", action="store_true", help="estabiliza vídeo feito na mão (deshake)")
    p.add_argument("--sem-diretor", action="store_true", help="rascunho cru: sem cortar vícios e tomadas repetidas, sem ênfases, zooms e elementos sugeridos")
    p.add_argument("--sem-cena", action="store_true", help="não lê gestos, cabeça e câmera (sem efeitos que acompanham o movimento)")
    p.add_argument("--sem-aparar", action="store_true", help="usa os tempos crus do Whisper (não acerta pausas pelo áudio)")
    p.add_argument("--modelo", default="small", help="tiny|base|small|medium|large-v3")
    p.add_argument("--estilo", choices=["tutorial_passos", "tela_perspectiva", "vitrine"],
                   help="estilo de edição (docs/estilos-de-referencia.md): ajusta o corte de pausas e o rascunho")

    p = sub.add_parser("renderizar", help="aplica o edl.json e gera final.mp4 + previa.jpg")
    p.add_argument("edl")
    p.add_argument("--rapido", action="store_true", help="codificação rápida para conferir")
    p.add_argument("--so-audio", action="store_true", help="refaz só o áudio sobre o vídeo já renderizado")
    p.add_argument("--formato", choices=["vertical", "feed", "horizontal"], help="renderiza o mesmo EDL em outro formato (sai em final_<formato>.mp4)")
    p.add_argument("--previa", action="store_true", help="prévia rápida (10 quadros/s, só a janela de --de a --ate) em previa.mp4")
    p.add_argument("--de", type=float, help="início da prévia, em segundos do vídeo final")
    p.add_argument("--ate", type=float, help="fim da prévia, em segundos do vídeo final")
    p.add_argument("--sem-conferencia", action="store_true", help="pula a conferência visual automática do final.mp4")
    p.add_argument("--processos", type=int, help="processos de render em paralelo (padrão: um por núcleo, até 8; 1 desliga)")

    p = sub.add_parser("testar", help="regressão de todas as marcas (rode antes de entregar mudanças no editor)")
    p.add_argument("--marca", help="testa só esta marca")
    p.add_argument("--atualizar", action="store_true", help="grava a folha atual como nova referência visual")
    p.add_argument("--so-visual", action="store_true", help="pula o render ponta a ponta")

    p = sub.add_parser("linha-do-tempo", help="página HTML com o vídeo e a linha do tempo do EDL, para revisar")
    p.add_argument("edl")
    p.add_argument("--video", help="vídeo da página (padrão: final.mp4 ou previa.mp4 da pasta)")

    p = sub.add_parser("broll", help="busca b-roll vertical no Pexels (precisa de PEXELS_API_KEY) e baixa para a pasta do vídeo")
    p.add_argument("termo")
    p.add_argument("edl")
    p.add_argument("--n", type=int, default=6)
    p.add_argument("--baixar", type=int, help="baixa a opção N da lista")

    p = sub.add_parser("exportar", help="entrega completa: SRT, capa, legenda do post, reel para o Instagram e outros formatos")
    p.add_argument("edl")
    p.add_argument("--formatos", default="", help="outros formatos além do vertical, separados por vírgula: feed,horizontal")
    p.add_argument("--quando", help="data e hora do post para a entrada da agenda do insta_report (2026-11-20T19:00:00-03:00)")
    p.add_argument("--insta-report", help="pasta de um clone do insta_report: copia reel e capa e acrescenta o post na agenda (sem commit)")

    sub.add_parser("marcas", help="lista as marcas e o que cada uma usa")
    sub.add_parser("estilos", help="lista os estilos de edição, os planos e os looks de cor")

    p = sub.add_parser("biblioteca", help="bibliotecas compartilhadas: 3D, músicas, efeitos e sons")
    p.add_argument("acao", choices=["listar", "baixar", "verificar", "previa", "catalogo", "criar"])
    p.add_argument("qual", nargs="?", choices=["3d", "musicas", "efeitos", "sons"])
    p.add_argument("termo", nargs="*", help="texto a procurar (listar) ou nomes do Fluent Emoji (baixar 3d)")
    p.add_argument("--marca", help="mostra só o que serve a esta marca (e usa a paleta dela na prévia)")
    p.add_argument("--clima")
    p.add_argument("--categoria")
    p.add_argument("--genero")
    p.add_argument("--saida", help="arquivo de saída da prévia")
    p.add_argument("--json", action="store_true", help="saída em JSON (para agentes)")
    p.add_argument("--fluent", help="(criar 3d) nome da pasta no Fluent Emoji, em inglês (ex.: House)")
    p.add_argument("--emoji", help="(criar 3d) emoji para extrudar quando não houver Fluent (ex.: 🏠)")
    p.add_argument("--texto", help="(criar 3d) placa com este texto nas cores da marca (--marca obrigatório)")

    p = sub.add_parser("conferir", help="confere de que marca é um vídeo renderizado")
    p.add_argument("video")
    p.add_argument("--marca", required=True, help="marca esperada")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "analisar":
            from .analisar import cmd_analisar
            cmd_analisar(a)
        elif a.cmd == "renderizar":
            from .renderizar import cmd_renderizar
            cmd_renderizar(a)
        elif a.cmd == "linha-do-tempo":
            from .linha_tempo import cmd_linha_tempo
            cmd_linha_tempo(a)
        elif a.cmd == "broll":
            from .banco import cmd_broll
            cmd_broll(a)
        elif a.cmd == "exportar":
            from .exportar import cmd_exportar
            cmd_exportar(a)
        elif a.cmd == "testar":
            from .testar import cmd_testar
            cmd_testar(a)
        else:
            from . import comandos
            {"marcas": comandos.cmd_marcas, "estilos": comandos.cmd_estilos, "biblioteca": comandos.cmd_biblioteca, "conferir": comandos.cmd_conferir}[a.cmd](a)
    except ErroDeMarca as e:
        sys.exit(f"Erro de marca: {e}")
