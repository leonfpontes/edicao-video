"""Criação de objetos 3D sob demanda: quando o roteiro pede um objeto que a biblioteca não tem, o editor cria.

Três caminhos, nesta ordem:

1. **Fluent 3D** (`fluent`: nome da pasta no Microsoft Fluent Emoji, MIT, ex.: "House", "Seedling"): baixa o render
   3D pronto para `biblioteca/3d/renders/` e põe no catálogo. Sem nome, tenta o próprio `nome` em inglês.
2. **Emoji extrudado** (`emoji`: o caractere, ex.: "🏠"): desenha o emoji colorido (Noto Color Emoji, licença OFL) em
   alta, recorta e grava em `biblioteca/3d/criados/`; o motor extruda (espessura, luz e reflexo), como os logos.
3. **Placa da marca** (`texto`, com a marca ativa): placa com o texto nas cores e na fonte da marca, extrudada, em
   `marcas/<id>/3d/` (identidade: nunca na biblioteca compartilhada).

Tudo que é criado fica: o objeto entra no catálogo (ou na pasta da marca) e serve aos próximos vídeos.
No EDL: {"tipo": "objeto3d", "nome": "casa", "fluent": "House", "emoji": "🏠", "na": "pela casa"}.
"""
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import BIBLIOTECA

FLUENT = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/"
FONTES_EMOJI = ["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", "/System/Library/Fonts/Apple Color Emoji.ttc"]
CATALOGO = BIBLIOTECA / "3d" / "catalogo.json"


def slug(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _catalogar(item):
    cat = json.loads(CATALOGO.read_text())
    if not any(it["id"] == item["id"] for it in cat["itens"]):
        cat["itens"].append(item)
        CATALOGO.write_text(json.dumps(cat, ensure_ascii=False, indent=1) + "\n")


def de_fluent(nome_fluent, iid=None, tags=()):
    """Baixa o render 3D de uma pasta do Fluent Emoji. Devolve o id, ou None se não houver (ou sem rede)."""
    pasta = urllib.parse.quote(nome_fluent)
    try:
        meta = json.loads(urllib.request.urlopen(FLUENT + pasta + "/metadata.json", timeout=30).read())
    except Exception:
        return None
    base = re.sub(r"[^a-z0-9-]+", "_", nome_fluent.lower()).strip("_")
    png = None
    for sub in [f"{d}{s}_3d{x}.png" for s in {base, base.replace("-", "_")} for d, x in (("3D/", ""), ("Default/3D/", "_default"))]:
        try:
            png = urllib.request.urlopen(FLUENT + pasta + "/" + urllib.parse.quote(sub), timeout=60).read()
            break
        except Exception:
            continue
    if not png:
        return None
    iid = iid or slug(nome_fluent)
    destino = BIBLIOTECA / "3d" / "renders" / f"{iid}.png"
    destino.write_bytes(png)
    _catalogar({"id": iid, "nome": nome_fluent, "tipo": "render", "categoria": "criados",
                "tags": list(tags) + meta.get("keywords", [])[:8], "arquivo": f"renders/{iid}.png",
                "fonte": "Microsoft Fluent Emoji 3D", "licenca": "MIT", "fluent": nome_fluent})
    return iid


def de_emoji(emoji, iid, tags=(), lado=512):
    """Desenha o emoji colorido em alta e grava o PNG recortado para extrusão. Devolve o id, ou None sem fonte de emoji."""
    fonte = next((f for f in FONTES_EMOJI if Path(f).exists()), None)
    if fonte is None:
        return None
    f = ImageFont.truetype(fonte, 109)  # a fonte colorida só tem bitmaps nesse tamanho
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), emoji, font=f, embedded_color=True, anchor="mm")
    bb = im.getbbox()
    if not bb:
        return None
    im = im.crop(bb)
    k = lado / max(im.size)
    im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    pasta = BIBLIOTECA / "3d" / "criados"
    pasta.mkdir(parents=True, exist_ok=True)
    im.save(pasta / f"{iid}.png")
    _catalogar({"id": iid, "nome": unicodedata.name(emoji[0], iid).title(), "tipo": "extrusao", "categoria": "criados",
                "tags": list(tags), "arquivo": f"criados/{iid}.png", "fonte": "Noto Color Emoji (extrudado pelo editor)",
                "licenca": "OFL 1.1", "emoji": emoji})
    return iid


def placa_marca(texto, iid, lado=1024):
    """Placa com o texto nas cores e na fonte da marca ativa, gravada em marcas/<id>/3d/<iid>.png (extrudada no render)."""
    from .graficos import fonte
    from .marca import ATIVA, CORES
    rgb = lambda n: tuple(int(v) for v in CORES[n]) + (255,)
    im = Image.new("RGBA", (lado, lado // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = 24
    d.rounded_rectangle([m, m, lado - m, lado // 2 - m], 60, fill=rgb("marinho"), outline=rgb("champanhe"), width=18)
    tam = 170
    f = fonte("Black", tam)
    while f.getlength(texto) > lado * 0.8 and tam > 40:
        tam -= 8
        f = fonte("Black", tam)
    d.text((lado / 2, lado / 4), texto, font=f, fill=rgb("papel_2"), anchor="mm")
    destino = Path(ATIVA["pasta"]) / "3d" / f"{iid}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.save(destino)
    return iid


def criar_3d(nome, fluent=None, emoji=None, texto=None, tags=()):
    """Cria o objeto `nome` pelo primeiro caminho que funcionar. Devolve (id, como) ou (None, motivo)."""
    from .bibliotecas import catalogo
    catalogo.cache_clear()  # o objeto novo aparece na próxima busca
    iid = slug(nome)
    if texto:
        return placa_marca(texto, iid), "placa da marca"
    for nf in [x for x in (fluent, nome.strip().capitalize() if re.fullmatch(r"[A-Za-z][A-Za-z \-]+", nome) else None) if x]:
        r = de_fluent(nf, iid, tags)
        if r:
            catalogo.cache_clear()
            return r, f"Fluent 3D ({nf})"
    if emoji:
        r = de_emoji(emoji, iid, tags)
        if r:
            catalogo.cache_clear()
            return r, "emoji extrudado"
    return None, "sem rede para o Fluent e sem emoji: passe \"fluent\" (nome em inglês) ou \"emoji\""
