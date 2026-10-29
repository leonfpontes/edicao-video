#!/usr/bin/env python3
"""Monta biblioteca/musicas/catalogo.json e CREDITOS.md a partir da curadoria abaixo.

Uso (da raiz do repositório): python ferramentas/montar_musicas.py

Baixa cada faixa da fonte oficial, mede duração e sha256 e cruza com os metadados oficiais do Kevin MacLeod
(incompetech.com/music/royalty-free/pieces.json: BPM, instrumentos, "feel", descrição). As tags em português
(clima, energia, sob_fala, usos) são a curadoria do editor. Para acrescentar uma faixa, inclua uma linha em
CURADORIA e rode de novo. Só entram faixas reais com licença que permite uso comercial.
"""
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "biblioteca" / "musicas"
INCOMPETECH = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
PIECES = "https://incompetech.com/music/royalty-free/pieces.json"
GENEROS = {"4": "Clássica", "5": "Contemporânea", "7": "Eletrônica", "8": "Funk", "11": "Jazz", "12": "Latina",
           "16": "Pop", "20": "Ragtime", "22": "Trilha sonora", "24": "Variada", "25": "Mundo"}
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
TEMPO_LIVRE = {"meditation-impromptu-01", "touching-moments-four"}  # piano solo em rubato: não tem pulso fixo

# id, título na fonte, clima (pt), energia 1-5, boa sob fala?, usos sugeridos, [marcas] (vazio = todas)
CURADORIA = [
    # ── calmas e emocionais (reflexão, homenagem, vida real)
    ("meditation-impromptu-01", "Meditation Impromptu 01", ["reflexivo", "calmo", "contemplativo"], 1, True, "reflexão falada, fim de dia"),
    ("gymnopedie-no-1", "Gymnopedie No 1", ["nostálgico", "delicado", "saudade"], 1, True, "lembrança, saudade, homenagem"),
    ("touching-moments-four", "Touching Moments Four - Melody", ["emocionante", "terno", "homenagem"], 2, False, "homenagem, agradecimento"),
    ("heartwarming", "Heartwarming", ["romântico", "carinho", "família"], 2, True, "casal, família, carinho"),
    ("lasting-hope", "Lasting Hope", ["esperança", "recomeço", "superação"], 2, True, "virada, recomeço, história de superação"),
    ("eternal-hope", "Eternal Hope", ["esperança", "emoção", "crescente"], 2, True, "história que cresce, conquista"),
    ("dreamer", "Dreamer", ["sonhador", "leve", "fim de tarde"], 2, True, "planos, sonho, fim de tarde"),
    ("wholesome", "Wholesome", ["aconchego", "dia a dia", "gratidão"], 2, True, "rotina, gratidão, casa"),
    ("clean-soul", "Clean Soul", ["calmo", "introspectivo", "espaço"], 1, True, "explicação calma, bastidores tranquilos"),
    ("ether-vox", "Ether Vox", ["contemplativo", "etéreo", "sereno"], 1, True, "abertura serena, natureza"),
    # ── leves e otimistas (dia a dia, tutorial, conteúdo de valor)
    ("carefree", "Carefree", ["alegre", "despreocupado", "passeio"], 3, True, "passeio, humor leve"),
    ("somewhere-sunny", "Somewhere Sunny", ["ensolarado", "viagem", "praia"], 3, True, "viagem, verão"),
    ("wallpaper", "Wallpaper", ["leve", "otimista", "simpático"], 2, True, "dica rápida, tutorial"),
    ("easy-lemon", "Easy Lemon", ["tranquilo", "simpático", "tutorial"], 2, True, "passo a passo, explicação"),
    ("life-of-riley", "Life of Riley", ["alegre", "otimista", "vlog"], 3, True, "vlog, bastidores animados"),
    ("daily-beetle", "Daily Beetle", ["feliz", "rotina", "produtivo"], 3, True, "rotina, organização, antes e depois"),
    # ── modernas e de negócio (produto, tecnologia, apresentação)
    ("inspired", "Inspired", ["inspirador", "corporativo", "tecnologia"], 3, True, "apresentação, case, produto"),
    ("cipher", "Cipher", ["tecnológico", "moderno", "energético"], 4, False, "abertura com ritmo, lançamento"),
    ("pamgaea", "Pamgaea", ["groove", "curioso", "moderno"], 3, True, "explicação com ritmo, lista de dicas"),
    ("deliberate-thought", "Deliberate Thought", ["foco", "reflexivo", "análise"], 2, True, "análise, raciocínio, diagnóstico"),
    ("chill-wave", "Chill Wave", ["chill", "relaxado", "lo-fi"], 2, True, "trabalho focado, setup, bastidores"),
    ("funkorama", "Funkorama", ["energético", "groove", "confiante"], 4, False, "montagem rápida, resultado"),
    # ── lounge, jazz e brasileiras
    ("bossa-antigua", "Bossa Antigua", ["bossa", "acolhedor", "brasileiro"], 2, True, "conversa leve, café"),
    ("lobby-time", "Lobby Time", ["lounge", "elegante", "apresentação"], 2, True, "apresentação elegante, institucional"),
    ("backbay-lounge", "Backbay Lounge", ["jazz", "elegante", "noite"], 2, True, "noite, conversa, sofisticado"),
    ("local-forecast", "Local Forecast - Elevator", ["descontraído", "espera", "humor leve"], 2, True, "espera, 'enquanto isso'"),
    # ── humor e tensão (erro comum, problema, curiosidade)
    ("investigations", "Investigations", ["curiosidade", "mistério leve", "pergunta"], 2, True, "pergunta, investigação, 'por que?'"),
    ("sneaky-snitch", "Sneaky Snitch", ["humor", "travessura", "erro comum"], 3, True, "erro comum, mito, pegadinha"),
    ("thinking-music", "Thinking Music", ["dúvida", "tensão leve", "problema"], 3, True, "problema, dilema, antes da solução"),
    ("monkeys-spinning-monkeys", "Monkeys Spinning Monkeys", ["humor", "caos", "bagunça"], 4, False, "bagunça, caos, exagero cômico"),
    ("fluffing-a-duck", "Fluffing a Duck", ["humor", "bobo", "leve"], 4, False, "humor, fail, blooper"),
]

# Alex Morgan no Free Music Archive (CC BY 4.0): id, página, clima, energia, sob fala, usos
FMA = [
    ("samba-jazz-sunny-cafe", "https://freemusicarchive.org/music/alex-morgan/bossa-nova-latin-jazz-vol-2/samba-jazz-sunny-cafe-fast-bright-samba/",
     ["samba", "alegre", "brasileiro"], 4, False, "festa, celebração, verão"),
    ("samba-jazz-light-batucada", "https://freemusicarchive.org/music/alex-morgan/bossa-nova-latin-jazz-vol-2/samba-jazz-restaurant-light-batucada/",
     ["batucada leve", "brasileiro", "animado"], 3, True, "encontro, comunidade, movimento"),
    ("bossa-nova-cafe-bright", "https://freemusicarchive.org/music/alex-morgan/bossa-nova-latin-jazz-vol-1/bossa-nova-cafe-bright-rhythm/",
     ["bossa", "animado", "brasileiro"], 3, True, "dia a dia, café, conversa"),
    ("bossa-nova-sunny-easy", "https://freemusicarchive.org/music/alex-morgan/bossa-nova-latin-jazz-vol-1/bossa-nova-sunny-cafe-easy-major-key/",
     ["bossa", "calmo", "brasileiro"], 2, True, "explicação calma, acolhimento"),
]


def baixar(url, destino):
    if destino.exists():
        return
    req = urllib.request.Request(url, headers={"User-Agent": "edicao-video/2"})
    with urllib.request.urlopen(req, timeout=180) as r:
        destino.write_bytes(r.read())


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def duracao(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return round(float(out), 1)


def estimar_bpm(arq, ini=20, dur=60):
    """BPM por autocorrelação do fluxo espectral (para faixas sem BPM oficial). Dobrado para 80–160: pode errar
    por oitava (metade ou dobro), por isso o catálogo marca "bpm_fonte": "estimado"."""
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(ini), "-t", str(dur), "-i", str(arq), "-ac", "1", "-ar", "11025",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    hop, n = 256, 1024
    quadros = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    S = np.log1p(np.abs(np.fft.rfft(quadros, axis=1)) * 10)
    fluxo = np.maximum(np.diff(S, axis=0), 0).sum(1)
    fluxo = np.maximum(fluxo - np.convolve(fluxo, np.ones(16) / 16, "same"), 0)
    ac = np.correlate(fluxo, fluxo, "full")[len(fluxo) - 1:]
    bpms = np.arange(60, 181)
    lags = 11025 / hop * 60 / bpms
    nota = np.interp(lags, np.arange(len(ac)), ac) + 0.5 * np.interp(lags * 2, np.arange(len(ac)), ac)
    b = float(bpms[np.argmax(nota)])
    while b < 80:
        b *= 2
    while b >= 160:
        b /= 2
    return int(round(b))


def mmss(s):
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def main():
    (DEST / "arquivos").mkdir(parents=True, exist_ok=True)
    pecas = {p["title"]: p for p in json.loads(urllib.request.urlopen(PIECES, timeout=60).read())}
    itens = []
    for iid, titulo, clima, energia, sob_fala, usos in CURADORIA:
        meta = pecas.get(titulo) or pecas.get(titulo.replace("No 1", "No. 1"), {})
        url = INCOMPETECH + urllib.parse.quote(meta.get("filename") or f"{titulo}.mp3")
        arq = DEST / "arquivos" / f"{iid}.mp3"
        print(f"{iid}…", flush=True)
        baixar(url, arq)
        bpm = int(meta["bpm"]) if meta.get("bpm") else None
        fonte_bpm = "oficial" if bpm else ("livre" if iid in TEMPO_LIVRE else "estimado")
        bpm = bpm or (None if iid in TEMPO_LIVRE else estimar_bpm(arq))
        itens.append({
            "id": iid, "titulo": titulo, "artista": "Kevin MacLeod", "arquivo": f"arquivos/{iid}.mp3",
            "arquivo_original": meta.get("filename") or f"{titulo}.mp3", "duracao": duracao(arq), "duracao_txt": mmss(duracao(arq)),
            "bpm": bpm, "bpm_fonte": fonte_bpm, "genero": GENEROS.get(meta.get("genre"), "Clássica" if "Gymno" in titulo else "Variada"),
            "clima": clima, "energia": energia, "sob_fala": sob_fala, "usos": usos,
            "instrumentos": meta.get("instruments") or "Piano",
            "feel_original": meta.get("feel"), "descricao_original": (meta.get("description") or "")[:240] or None,
            "licenca": "CC BY 4.0", "licenca_url": CC_BY,
            "credito": f"Música: \"{titulo}\" – Kevin MacLeod (incompetech.com), CC BY 4.0 (creativecommons.org/licenses/by/4.0)",
            "pagina": "https://incompetech.com/music/royalty-free/music.html", "url": url, "sha256": sha256(arq),
        })
    for iid, pagina, clima, energia, sob_fala, usos in FMA:
        html = urllib.request.urlopen(urllib.request.Request(pagina, headers={"User-Agent": "edicao-video/2"}), timeout=60).read().decode()
        info = json.loads(re.search(r"data-track-info='([^']+)'", html).group(1))
        if "creativecommons.org/licenses/by/4.0" not in html:
            sys.exit(f"{iid}: a página não mostra mais CC BY 4.0, revise antes de incluir")
        arq = DEST / "arquivos" / f"{iid}.mp3"
        print(f"{iid}…", flush=True)
        baixar(info["fileUrl"], arq)
        itens.append({
            "id": iid, "titulo": info["title"], "artista": info["artistName"], "arquivo": f"arquivos/{iid}.mp3",
            "duracao": duracao(arq), "duracao_txt": mmss(duracao(arq)), "bpm": estimar_bpm(arq),
            "bpm_fonte": "estimado", "genero": "Latina",
            "clima": clima, "energia": energia, "sob_fala": sob_fala, "usos": usos, "instrumentos": "Violão, percussão, piano",
            "licenca": "CC BY 4.0", "licenca_url": CC_BY,
            "credito": f"Música: \"{info['title']}\" de {info['artistName']} (Free Music Archive), CC BY 4.0",
            "pagina": pagina, "url": info["fileUrl"], "sha256": sha256(arq),
        })
    cat = {"versao": 1, "observacao": "Gerado por ferramentas/montar_musicas.py. Os arquivos ficam em arquivos/ (fora do Git): "
                                       "`editor.py biblioteca baixar musicas` baixa todos e confere o sha256.", "itens": itens}
    (DEST / "catalogo.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1) + "\n")
    escrever_creditos(itens)
    print(f"{len(itens)} faixas")


def escrever_creditos(itens):
    ln = ["# Músicas: créditos e licenças", "",
          "Todas as faixas são gravações reais com licença que permite uso comercial (CC BY 4.0).",
          "**O crédito é obrigatório**: o render grava a linha certa em `creditos.txt`; cole na legenda do post.", "",
          "| id | Título | Artista | Clima | BPM | Duração | Sob fala | Crédito |", "|---|---|---|---|---|---|---|---|"]
    for it in itens:
        bpm = f"{it['bpm'] or 'livre'}{'*' if it['bpm_fonte'] == 'estimado' else ''}"
        ln.append(f"| `{it['id']}` | {it['titulo']} | {it['artista']} | {', '.join(it['clima'])} | {bpm} | "
                  f"{it['duracao_txt']} | {'sim' if it['sob_fala'] else 'não'} | {it['credito']} |")
    ln += ["", "\\* BPM estimado pelo editor (sem BPM oficial); pode ser metade ou o dobro.", "",
           "Fontes: [incompetech.com](https://incompetech.com) (Kevin MacLeod) e "
           "[Free Music Archive](https://freemusicarchive.org) (Alex Morgan). Antes de publicar algo grande, confira na "
           "página da faixa se a licença continua a mesma.", "",
           "Nunca entram: música comercial, faixa sem licença clara, música sintetizada por código, e atabaque ou "
           "ponto cantado (sagrados, não são trilha de propaganda)."]
    (DEST / "CREDITOS.md").write_text("\n".join(ln) + "\n")


if __name__ == "__main__":
    main()
