"""Bibliotecas compartilhadas por todas as marcas: objetos 3D, músicas e efeitos.

Cada biblioteca tem um `catalogo.json` em `biblioteca/<nome>/`. Um item pode ter `"marcas": [...]` para
ficar restrito a algumas marcas; sem isso, serve a todas. Itens que são identidade de uma marca (o
monograma LP em 3D, o ticket do GiraHub) não ficam aqui: ficam em `marcas/<id>/3d/`, e só a própria
marca os encontra.
"""
import hashlib
import json
import shutil
import urllib.request
from functools import lru_cache

from .config import BIBLIOTECA
from .marca import (
    ATIVA,
    CFG,
    ErroDeMarca,
    arquivo_marca,
    marca_ativa,
    normalizar_texto,
    politica_musica,
    registrar,
    tem_arquivo_marca,
)

LICENCAS_LIVRES = {"CC0 1.0", "CC BY 4.0", "MIT", "Domínio público", "Própria"}


@lru_cache(maxsize=None)
def catalogo(nome):
    p = BIBLIOTECA / nome / "catalogo.json"
    return json.loads(p.read_text()) if p.exists() else {"itens": []}


def itens(nome):
    return catalogo(nome)["itens"]


def item(nome, iid):
    """Item pelo id; aceita também os apelidos e o nome original em inglês (ex.: "rocket" acha "foguete")."""
    for it in itens(nome):
        if it["id"] == iid or iid in it.get("apelidos", []):
            return it
    chave = normalizar_texto(iid).replace("-", " ")
    for it in itens(nome):
        if normalizar_texto(it.get("fluent") or it.get("nome") or "").replace("-", " ") == chave:
            return it
    return None


def permitido(it, mid=None):
    """O item serve à marca? (lista "marcas" vazia ou ausente = todas)."""
    mid = mid or marca_ativa()
    return not it.get("marcas") or mid in it["marcas"]


def buscar(nome, termo=None, **filtros):
    """Itens da biblioteca que servem à marca ativa (se houver), filtrados por texto e campos."""
    out = []
    for it in itens(nome):
        if ATIVA["id"] and not permitido(it):
            continue
        if termo:
            alvo = normalizar_texto(" ".join(str(v) for v in it.values()))
            if not all(normalizar_texto(t) in alvo for t in termo.split()):
                continue
        ok = True
        for k, v in filtros.items():
            if v is None:
                continue
            campo = it.get(k)
            if isinstance(campo, list):
                ok &= any(normalizar_texto(v) == normalizar_texto(c) for c in campo)
            else:
                ok &= normalizar_texto(v) == normalizar_texto(campo)
        if ok:
            out.append(it)
    return out


# ───────────────────────────── 3D ─────────────────────────────

def objeto_3d(nome):
    """(caminho, item) de um objeto 3D: primeiro os da própria marca (marcas/<id>/3d/<nome>.png, sempre
    extrudados), depois a biblioteca compartilhada."""
    marca_ativa()
    if tem_arquivo_marca(f"3d/{nome}.png"):
        return arquivo_marca(f"3d/{nome}.png"), {"id": nome, "tipo": "extrusao", "origem": "marca"}
    it = item("3d", nome)
    if it is None:
        raise ErroDeMarca(f"objeto 3D desconhecido: {nome} (veja `editor.py biblioteca listar 3d`)")
    if not permitido(it):
        raise ErroDeMarca(f"o objeto 3D {nome} não serve à marca {ATIVA['id']}")
    p = BIBLIOTECA / "3d" / it["arquivo"]
    if not p.exists():
        raise ErroDeMarca(f"arquivo do objeto 3D {nome} não encontrado: {p}")
    return registrar(p), it


# ───────────────────────────── músicas ─────────────────────────────

def _sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar_faixa(it, forcar=False):
    """Garante o arquivo da faixa em biblioteca/musicas/arquivos/ (baixa da fonte oficial e confere o sha256)."""
    p = BIBLIOTECA / "musicas" / it["arquivo"]
    if p.exists() and not forcar:
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part")
    req = urllib.request.Request(it["url"], headers={"User-Agent": "edicao-video/2 (+biblioteca de musicas)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if it.get("sha256") and _sha256(tmp) != it["sha256"]:
        tmp.unlink()
        raise ErroDeMarca(f"a faixa {it['id']} baixada não confere com o catálogo (sha256): a fonte mudou o arquivo")
    tmp.rename(p)
    return p


def musica_do_edl(mus):
    """(caminho, item ou None) da trilha pedida no EDL.

    "faixa": id do catálogo (preferido). "arquivo": caminho antigo (assets/musicas/<Título>.mp3) ou um
    arquivo próprio; um arquivo fora do catálogo precisa de "credito" e "licenca" no EDL."""
    mus = mus or {}
    pol = politica_musica()
    if not (mus.get("faixa") or mus.get("arquivo")):
        if pol == "obrigatoria":
            raise ErroDeMarca(f"a marca {CFG['id']} exige música real: preencha \"musica\": {{\"faixa\": …}} "
                              "com uma faixa de `editor.py biblioteca listar musicas`")
        return None, None
    if pol == "proibida":
        raise ErroDeMarca(f"a marca {CFG['id']} não usa música no vídeo")
    it = None
    if mus.get("faixa"):
        it = item("musicas", mus["faixa"])
        if it is None:
            raise ErroDeMarca(f"faixa desconhecida: {mus['faixa']} (veja `editor.py biblioteca listar musicas`)")
    else:
        nome = mus["arquivo"].replace("\\", "/").rsplit("/", 1)[-1]
        it = next((x for x in itens("musicas") if x.get("arquivo_original") == nome
                   or x["arquivo"].rsplit("/", 1)[-1] == nome), None)
    if it is not None:
        if not permitido(it):
            raise ErroDeMarca(f"a faixa {it['id']} não serve à marca {ATIVA['id']}")
        return registrar(baixar_faixa(it)), it
    from pathlib import Path
    p = Path(mus["arquivo"]).expanduser()
    if not p.exists():
        raise ErroDeMarca(f"música não encontrada: {mus['arquivo']}")
    if not (mus.get("credito") and mus.get("licenca") in LICENCAS_LIVRES):
        raise ErroDeMarca("música fora do catálogo: informe \"licenca\" (" + ", ".join(sorted(LICENCAS_LIVRES))
                          + ") e \"credito\" no EDL, ou cadastre a faixa em biblioteca/musicas/catalogo.json")
    return registrar(p), {"id": p.stem, "titulo": p.stem, "licenca": mus["licenca"], "credito": mus["credito"]}
