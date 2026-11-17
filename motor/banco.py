"""B-roll de banco: busca e baixa vídeos verticais do Pexels (licença Pexels: uso livre, comercial inclusive, sem
crédito obrigatório) para cobrir a fala com imagem.

Precisa da chave da API na variável de ambiente PEXELS_API_KEY (grátis em pexels.com/api). A chave nunca vai para o
repositório nem para o EDL. Só `urllib`, sem dependência nova.

    editor.py broll "reunião de equipe" P/edl.json            # lista opções
    editor.py broll "reunião de equipe" P/edl.json --baixar 2 # baixa a 2ª para P/broll/ e mostra o elemento do EDL
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.pexels.com/videos/search"
LICENCA = "Pexels License (uso livre, sem crédito obrigatório)"


def _get(url, chave, timeout=30):
    req = urllib.request.Request(url, headers={"Authorization": chave, "User-Agent": "editor-video/2"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def chave_api():
    chave = os.environ.get("PEXELS_API_KEY", "").strip()
    if not chave:
        raise SystemExit("Falta a chave do Pexels: exporte PEXELS_API_KEY (grátis em pexels.com/api). Ela não vai para o repositório.")
    return chave


def melhor_arquivo(video, largura_max=1080):
    """O arquivo vertical de maior resolução que não passa de largura_max."""
    arqs = [f for f in video.get("video_files", []) if f.get("width") and f.get("height") and f.get("link")]
    vert = [f for f in arqs if f["height"] >= f["width"]] or arqs
    ok = [f for f in vert if f["width"] <= largura_max] or vert
    return max(ok, key=lambda f: f["width"] * f["height"]) if ok else None


def buscar(termo, n=6, chave=None, idioma="pt-BR"):
    """Opções de b-roll vertical para o termo: [{id, pagina, duracao, autor, link, largura, altura}]."""
    chave = chave or chave_api()
    q = urllib.parse.urlencode({"query": termo, "orientation": "portrait", "per_page": n, "locale": idioma, "size": "medium"})
    dados = json.loads(_get(f"{API}?{q}", chave))
    out = []
    for v in dados.get("videos", []):
        f = melhor_arquivo(v)
        if f:
            out.append({"id": v["id"], "pagina": v.get("url"), "duracao": v.get("duration"),
                        "autor": (v.get("user") or {}).get("name"), "link": f["link"], "largura": f["width"], "altura": f["height"]})
    return out


def baixar(opcao, pasta, chave=None):
    """Baixa a opção para pasta/broll/pexels-<id>.mp4 e grava a origem ao lado (para o manifesto e a licença)."""
    destino = Path(pasta) / "broll"
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / f"pexels-{opcao['id']}.mp4"
    if not arq.exists():
        arq.write_bytes(_get(opcao["link"], chave or chave_api(), timeout=120))
    json.dump(dict(opcao, licenca=LICENCA), open(arq.with_suffix(".json"), "w"), ensure_ascii=False, indent=1)
    return arq


def cmd_broll(a):
    pasta = Path(a.edl).resolve().parent
    ops = buscar(a.termo, a.n)
    if not ops:
        sys.exit(f"Nada no Pexels para \"{a.termo}\". Tente outro termo (em inglês costuma ter mais).")
    if not a.baixar:
        for k, o in enumerate(ops, 1):
            print(f"{k}. {o['duracao']}s {o['largura']}x{o['altura']} · {o['autor']} · {o['pagina']}")
        print("Baixe com --baixar N.")
        return
    o = ops[a.baixar - 1]
    arq = baixar(o, pasta)
    el = {"tipo": "broll", "arquivo": f"broll/{arq.name}", "na": "<palavra>", "ate": "<palavra>"}
    print(f"Baixado: {arq} ({LICENCA}).\nNo EDL:\n{json.dumps(el, ensure_ascii=False)}")
