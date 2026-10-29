"""Guarda de marca: confere o EDL e o render contra a marca ativa antes e depois de renderizar.

É a segunda camada do isolamento (a primeira é `marca.py`, que só enxerga a pasta da marca ativa).
Aqui ficam as checagens que dependem do conteúdo do vídeo:

- o EDL declara a marca, e ela é a mesma da análise (`analise.json`);
- nenhum texto do vídeo (títulos, destaques, CTA, correções de legenda) traz termo exclusivo de outra marca;
- a URL do CTA é a da marca; Leo só na marca que tem Leo;
- nenhum arquivo citado no EDL fica na pasta de outra marca;
- objetos 3D, músicas e efeitos existem e servem à marca;
- no fim, nenhum arquivo aberto durante o render veio da pasta de outra marca.
"""
import re
from pathlib import Path

from .config import MARCAS
from .marca import ATIVA, AUDITORIA, CFG, ErroDeMarca, ler_marca, listar_marcas, normalizar_texto, tem_leo

CAMPOS_ARQUIVO = ("arquivo", "imagem")


def termos_de_outras(mid):
    """{termo normalizado: marca dona} dos termos exclusivos das outras marcas (menos os que mid também tem)."""
    meus = {normalizar_texto(t) for t in ler_marca(mid)["exclusivo"]["termos"]}
    out = {}
    for outra in listar_marcas():
        if outra == mid:
            continue
        for t in ler_marca(outra)["exclusivo"]["termos"]:
            n = normalizar_texto(t)
            if n not in meus:
                out[n] = outra
    return out


def achar_termos(texto, termos):
    """Termos (de outras marcas) presentes no texto, comparando sem acento e sem caixa."""
    alvo = normalizar_texto(texto)
    achados = []
    for termo, dono in termos.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(termo) + r"(?![a-z0-9])", alvo):
            achados.append((termo, dono))
    return achados


def textos_do_edl(edl):
    """[(onde, texto)] de tudo que vira texto na tela ou no áudio."""
    out = []
    for i, e in enumerate(edl.get("elementos", [])):
        for k in ("texto", "rotulo", "prefixo", "sufixo"):
            if isinstance(e.get(k), str):
                out.append((f"elementos[{i}].{k}", e[k]))
    cta = edl.get("cta") or {}
    for k in ("chamada", "url", "apoio"):
        if isinstance(cta.get(k), str):
            out.append((f"cta.{k}", cta[k]))
    leg = edl.get("legendas") or {}
    for k, v in (leg.get("correcoes") or {}).items():
        out.append((f"legendas.correcoes[{k}]", str(v)))
    for v in leg.get("enfase") or []:
        out.append(("legendas.enfase", str(v)))
    for k in ("titulo", "saida"):
        if isinstance(edl.get(k), str):
            out.append((k, edl[k]))
    return out


def arquivos_do_edl(edl):
    out = []
    for i, e in enumerate(edl.get("elementos", [])):
        for k in CAMPOS_ARQUIVO:
            if e.get(k):
                out.append((f"elementos[{i}].{k}", e[k]))
    for sec in ("fundo", "musica"):
        for k in CAMPOS_ARQUIVO:
            v = (edl.get(sec) or {}).get(k)
            if v:
                out.append((f"{sec}.{k}", v))
    return out


def dono_do_caminho(caminho, base=None):
    """Marca dona do caminho (se ele estiver dentro de marcas/<id>/), senão None."""
    p = Path(caminho).expanduser()
    if not p.is_absolute() and base is not None:
        p = Path(base) / p
    try:
        rel = p.resolve().relative_to(MARCAS.resolve())
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def conferir_edl(edl, analise=None, pasta=None):
    """Levanta ErroDeMarca com todos os problemas encontrados (nada é renderizado se houver um)."""
    from .bibliotecas import item, objeto_3d, permitido
    from .efeitos import REGISTRO
    mid = ATIVA["id"]
    pr = []
    if not edl.get("marca"):
        pr.append("o edl.json não diz a marca (\"marca\"): rode `analisar --marca <marca>` de novo")
    elif edl["marca"] != mid:
        pr.append(f"o edl.json é da marca {edl['marca']}, mas a marca ativa é {mid}")
    if analise is not None and analise.get("marca") and analise["marca"] != edl.get("marca"):
        pr.append(f"a análise desta pasta foi feita para a marca {analise['marca']} e o edl.json diz {edl.get('marca')}: "
                  "rode `analisar` com a marca certa numa pasta própria (--pasta)")
    termos = termos_de_outras(mid)
    for onde, txt in textos_do_edl(edl):
        for termo, dono in achar_termos(txt, termos):
            pr.append(f"{onde} contém \"{termo}\", que é da marca {dono}")
    cta = edl.get("cta") or {}
    url_marca = (CFG.get("cta") or {}).get("url")
    if cta.get("url") and cta["url"] != url_marca:
        pr.append(f"cta.url ({cta['url']}) não é a da marca ({url_marca or 'a marca não tem CTA'})")
    if cta.get("pose_leo") and not tem_leo():
        pr.append(f"cta.pose_leo: a marca {mid} não tem o Leo")
    for onde, caminho in arquivos_do_edl(edl):
        dono = dono_do_caminho(caminho, pasta)
        if dono and dono != mid:
            pr.append(f"{onde} aponta para a pasta da marca {dono}: {caminho}")
    for i, e in enumerate(edl.get("elementos", [])):
        tp = e.get("tipo")
        if tp == "leo" and not tem_leo():
            pr.append(f"elementos[{i}]: o Leo é personagem do @pontes_brain; a marca {mid} não o usa")
        elif tp == "objeto3d":
            try:
                objeto_3d(e.get("nome", ""))
            except ErroDeMarca as err:
                pr.append(f"elementos[{i}]: {err}")
        elif tp == "efeito":
            if e.get("nome") not in REGISTRO:
                pr.append(f"elementos[{i}]: efeito desconhecido: {e.get('nome')}")
            for k in ("cor", "cor2"):
                if k in e and e[k] not in ("marinho", "marinho_2", "champanhe", "bronze", "papel", "papel_2", "nevoa"):
                    pr.append(f"elementos[{i}].{k}: use um papel da paleta da marca, não {e[k]!r}")
            if e.get("nome") == "chuva_3d":
                try:
                    objeto_3d(e.get("objeto", "estrela"))
                except ErroDeMarca as err:
                    pr.append(f"elementos[{i}]: {err}")
    mus = edl.get("musica") or {}
    if mus.get("faixa"):
        it = item("musicas", mus["faixa"])
        if it is None:
            pr.append(f"musica.faixa desconhecida: {mus['faixa']}")
        elif not permitido(it):
            pr.append(f"musica.faixa {it['id']} não serve à marca {mid}")
    if pr:
        raise ErroDeMarca(f"o EDL não passou na guarda da marca {mid}:\n- " + "\n- ".join(pr))


def conferir_auditoria():
    """Depois do render: nenhum arquivo aberto pode estar na pasta de outra marca."""
    mid = ATIVA["id"]
    intrusos = [str(p) for p in AUDITORIA if (dono_do_caminho(p) or mid) != mid]
    if intrusos:
        raise ErroDeMarca(f"o render da marca {mid} abriu arquivos de outra marca:\n- " + "\n- ".join(intrusos))
    return list(AUDITORIA)
