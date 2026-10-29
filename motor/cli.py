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
    p.add_argument("--modelo", default="small", help="tiny|base|small|medium|large-v3")

    p = sub.add_parser("renderizar", help="aplica o edl.json e gera final.mp4 + previa.jpg")
    p.add_argument("edl")
    p.add_argument("--rapido", action="store_true", help="codificação rápida para conferir")
    p.add_argument("--so-audio", action="store_true", help="refaz só o áudio sobre o vídeo já renderizado")

    p = sub.add_parser("testar", help="regressão de todas as marcas (rode antes de entregar mudanças no editor)")
    p.add_argument("--marca", help="testa só esta marca")
    p.add_argument("--atualizar", action="store_true", help="grava a folha atual como nova referência visual")
    p.add_argument("--so-visual", action="store_true", help="pula o render ponta a ponta")

    sub.add_parser("marcas", help="lista as marcas e o que cada uma usa")

    p = sub.add_parser("biblioteca", help="bibliotecas compartilhadas: 3D, músicas e efeitos")
    p.add_argument("acao", choices=["listar", "baixar", "verificar", "previa", "catalogo"])
    p.add_argument("qual", nargs="?", choices=["3d", "musicas", "efeitos"])
    p.add_argument("termo", nargs="*", help="texto a procurar (listar) ou nomes do Fluent Emoji (baixar 3d)")
    p.add_argument("--marca", help="mostra só o que serve a esta marca (e usa a paleta dela na prévia)")
    p.add_argument("--clima")
    p.add_argument("--categoria")
    p.add_argument("--genero")
    p.add_argument("--saida", help="arquivo de saída da prévia")
    p.add_argument("--json", action="store_true", help="saída em JSON (para agentes)")

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
        elif a.cmd == "testar":
            from .testar import cmd_testar
            cmd_testar(a)
        else:
            from . import comandos
            {"marcas": comandos.cmd_marcas, "biblioteca": comandos.cmd_biblioteca, "conferir": comandos.cmd_conferir}[a.cmd](a)
    except ErroDeMarca as e:
        sys.exit(f"Erro de marca: {e}")
