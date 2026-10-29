"""Marcas: a identidade de cada conta e o isolamento entre elas.

Cada marca vive na própria pasta, `marcas/<id>/`, com o `marca.json` e os arquivos que só ela usa (logo,
vinheta, personagem). O que é de todas as marcas fica em `biblioteca/`.

Regras que tornam impossível sair um vídeo da marca A com a identidade da marca B:

1. O motor só enxerga UMA marca por vez (a marca ativa). Não existe marca padrão: sem `ativar()`, nada
   que dependa de identidade funciona.
2. Arquivo de marca só é aberto por `arquivo_marca()`, que nunca sai da pasta da marca ativa.
3. Ativar uma marca troca TODAS as cores, fontes e configurações (a validação exige todos os papéis de
   cor, então nada da marca anterior sobra).
4. Vinhetas e motivos de fundo próprios de uma marca (PDCA + LP, ticket) têm dono: outra marca não usa.
5. Cada marca declara os termos exclusivos dela (nome, @, domínio). `guarda.py` recusa o EDL de uma
   marca que contenha termos exclusivos de outra.
"""
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image

from .config import FONTES_DIR, MARCAS


class ErroDeMarca(Exception):
    """Algo tentou misturar marcas, ou a marca está mal configurada."""


PAPEIS_COR = ("marinho", "marinho_2", "champanhe", "bronze", "papel", "papel_2", "nevoa")
CAMPOS = ("id", "nome", "cores", "fontes", "intro", "fundo_motivo", "exclusivo")
# vinhetas e motivos de fundo desenhados sob medida para uma marca (o resto serve a qualquer uma)
VINHETAS = {"pdca_lp": "pontes_brain", "ticket": "girahub", "logo": None}
MOTIVOS = {"pdca": "pontes_brain", "ticket": "girahub", "anel": None, "nenhum": None}
POLITICAS_MUSICA = ("opcional", "obrigatoria", "proibida")

# estado da marca ativa (dicionários mutados no lugar: quem importou enxerga a troca)
CORES = {}  # papel -> (R, G, B)
CFG = {}  # marca.json da marca ativa
FONTES = {}  # papel ("titulo"/"texto") -> peso -> arquivo .ttf
ATIVA = {"id": None, "pasta": None}
AUDITORIA = []  # todo arquivo (de marca ou de biblioteca) aberto desde a ativação


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def normalizar_texto(t):
    """minúsculas, sem acento e com espaços simples (para comparar termos)."""
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def listar_marcas():
    return sorted(p.parent.name for p in MARCAS.glob("*/marca.json"))


def pasta_marca(mid):
    return MARCAS / mid


def ler_marca(mid):
    """Lê e valida marcas/<mid>/marca.json sem ativar a marca."""
    if not re.fullmatch(r"[a-z0-9_]+", str(mid or "")):
        raise ErroDeMarca(f"id de marca inválido: {mid!r} (use letras minúsculas, números e _)")
    p = pasta_marca(mid) / "marca.json"
    if not p.exists():
        raise ErroDeMarca(f"marca desconhecida: {mid} (marcas: {', '.join(listar_marcas())})")
    cfg = json.loads(p.read_text())
    problemas = validar_marca(cfg, mid)
    if problemas:
        raise ErroDeMarca(f"marca {mid} mal configurada:\n- " + "\n- ".join(problemas))
    return cfg


def validar_marca(cfg, mid):
    """Lista de problemas de configuração (vazia = ok)."""
    pr = []
    for c in CAMPOS:
        if c not in cfg:
            pr.append(f"falta o campo \"{c}\"")
    if cfg.get("id") != mid:
        pr.append(f"\"id\" ({cfg.get('id')}) precisa ser igual ao nome da pasta ({mid})")
    cores = cfg.get("cores", {})
    for papel in PAPEIS_COR:
        v = cores.get(papel)
        if not (isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v)):
            pr.append(f"cor \"{papel}\" ausente ou fora do formato #RRGGBB")
    for papel, pesos in cfg.get("fontes", {}).items():
        for peso, arq in pesos.items():
            if not (FONTES_DIR / arq).exists():
                pr.append(f"fonte {papel}/{peso} não existe em biblioteca/fontes: {arq}")
    pasta = pasta_marca(mid)
    for chave in ("logo",):
        if cfg.get(chave):
            pr += _conferir_relativo(pasta, cfg[chave], chave)
    tipo = cfg.get("intro", {}).get("tipo")
    if not cfg.get("intro", {}).get("nome"):
        pr.append("falta \"intro.nome\" (o nome que aparece na vinheta)")
    if tipo not in VINHETAS:
        pr.append(f"vinheta desconhecida: {tipo} (opções: {', '.join(VINHETAS)})")
    elif VINHETAS[tipo] not in (None, mid):
        pr.append(f"a vinheta \"{tipo}\" é exclusiva da marca {VINHETAS[tipo]}")
    if tipo == "pdca_lp" and not cfg.get("logo"):
        pr.append("a vinheta pdca_lp traça o logo da marca: defina \"logo\"")
    motivo = cfg.get("fundo_motivo")
    if motivo not in MOTIVOS:
        pr.append(f"fundo_motivo desconhecido: {motivo} (opções: {', '.join(MOTIVOS)})")
    elif MOTIVOS[motivo] not in (None, mid):
        pr.append(f"o fundo \"{motivo}\" é exclusivo da marca {MOTIVOS[motivo]}")
    if cfg.get("leo") and not (pasta / "leo").is_dir():
        pr.append("\"leo\": true, mas a marca não tem a pasta leo/")
    pol = politica_musica(cfg)
    if pol not in POLITICAS_MUSICA:
        pr.append(f"musica.politica inválida: {pol} (opções: {', '.join(POLITICAS_MUSICA)})")
    exc = cfg.get("exclusivo", {})
    if not exc.get("termos"):
        pr.append("\"exclusivo.termos\" vazio: liste nome, @ e domínio que só esta marca pode usar")
    return pr


def _conferir_relativo(pasta, rel, rotulo):
    p = (pasta / rel).resolve()
    if Path(rel).is_absolute() or pasta.resolve() not in p.parents:
        return [f"{rotulo} precisa estar dentro da pasta da marca: {rel}"]
    if not p.exists():
        return [f"{rotulo} não encontrado: marcas/{pasta.name}/{rel}"]
    return []


def politica_musica(cfg=None):
    cfg = CFG if cfg is None else cfg
    if "musica" in cfg and isinstance(cfg["musica"], dict):
        return cfg["musica"].get("politica", "opcional")
    return "obrigatoria" if cfg.get("musica_obrigatoria") else "opcional"


def ativar(mid):
    """Torna mid a marca ativa: troca cores, fontes e configuração inteiras e zera a auditoria."""
    cfg = ler_marca(mid)
    CFG.clear()
    CFG.update(cfg)
    CORES.clear()
    CORES.update({k: hex2rgb(cfg["cores"][k]) for k in PAPEIS_COR})
    FONTES.clear()
    FONTES.update(cfg.get("fontes", {}))
    ATIVA.update(id=mid, pasta=pasta_marca(mid).resolve())
    AUDITORIA.clear()
    return cfg


def marca_ativa():
    if not ATIVA["id"]:
        raise ErroDeMarca("nenhuma marca ativa: passe --marca ou preencha \"marca\" no edl.json")
    return ATIVA["id"]


def arquivo_marca(rel):
    """Caminho de um arquivo da marca ativa. Nunca sai de marcas/<marca ativa>/."""
    marca_ativa()
    pasta = ATIVA["pasta"]
    p = (pasta / rel).resolve()
    if Path(rel).is_absolute() or pasta not in p.parents:
        raise ErroDeMarca(f"arquivo fora da pasta da marca {ATIVA['id']}: {rel}")
    if not p.exists():
        raise ErroDeMarca(f"a marca {ATIVA['id']} não tem o arquivo {rel}")
    registrar(p)
    return p


def tem_arquivo_marca(rel):
    marca_ativa()
    p = (ATIVA["pasta"] / rel).resolve()
    return ATIVA["pasta"] in p.parents and p.exists()


def registrar(p):
    """Anota um arquivo usado no render (conferido no fim por guarda.conferir_auditoria)."""
    p = Path(p).resolve()
    if p not in AUDITORIA:
        AUDITORIA.append(p)
    return p


def tem_logo():
    return bool(CFG.get("logo"))


def tem_leo():
    return bool(CFG.get("leo")) and tem_arquivo_marca("leo")


def padrao(edl, chave, valor):
    """Valor do EDL; se faltar, o padrão da marca ("padroes_edl"); se faltar, o padrão geral."""
    return edl.get(chave, CFG.get("padroes_edl", {}).get(chave, valor))


def logo_marca(alt):
    """Logo da marca ativa (PNG com transparência) com altura alt, proporção preservada."""
    im = Image.open(arquivo_marca(CFG["logo"])).convert("RGBA")
    return im.resize((max(1, int(im.width * alt / im.height)), alt), Image.LANCZOS)
