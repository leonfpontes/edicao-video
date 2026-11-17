"""Diretor automático: lê a transcrição e o áudio e propõe a edição no rascunho do EDL.

- tira vícios de fala ("ãh", "hum", "né" no fim da frase, "tipo," de muleta, palavra gaguejada);
- percebe tomada repetida (a pessoa recomeça a frase) e fica só com a última;
- escolhe as palavras de ênfase da legenda (energia da voz, números, palavras fortes);
- alterna o zoom nos cortes secos e dá um tranco (punch) nas ênfases mais fortes;
- dá nota ao gancho dos primeiros 3 s e aponta a frase mais forte do vídeo para abrir;
- sugere elementos ancorados na fala (contador, passo, check, xis), respeitando o estilo.

Tudo é proposta: o agente revisa o rascunho e o relatório (diretor.json) antes de renderizar. Nada aqui inventa fala:
só corta o que foi dito a mais e marca o que já está no vídeo.
"""
import re
import subprocess
import unicodedata

import numpy as np

VICIOS = {"ãh", "ã", "ahn", "hã", "hum", "hmm", "hm", "uh", "éé", "ééé", "eh", "ehh", "mmm", "mm", "ééh", "aaa"}
STOP = set("""a o e é as os um uma uns umas de da do das dos em na no nas nos por pra pro para com sem que se ou mas
mais menos muito muita muitos muitas pouco já não sim isso isto esse essa esses essas este esta aquele aquela aqui ali lá
eu tu ele ela nós vós eles elas você vocês me te se lhe nos vos meu minha seu sua nosso nossa teu tua dele dela
ser estar ter ir vai vou foi era tem tá to tô está estou são somos fui faz fazer ainda também então aí né tipo assim
quando como onde porque porquê qual quais quem cada todo toda todos todas outro outra outros outras mesmo mesma bem
algum alguma alguns algumas alguém nenhum nenhuma tão tanto tanta qualquer pode posso podemos vamos vai dá dar
estiver estava estavam esteve esteja seria sido sendo tinha tenho tiver teria faria feito fez fazendo vou indo
gente coisa coisas hoje agora depois antes até ao aos à às pelo pela pelos pelas num numa dum duma lo la vez vezes
""".split())
FORTES = set("""nunca ninguém erro errado errada segredo pare para proibido cuidado perigo grátis dinheiro rápido rápida
simples fácil difícil melhor pior primeiro único única verdade mentira problema solução resultado resultados
crescimento metade dobro triplo zero tudo nada sempre jamais urgente agora""".split())
NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
           "nove": 9, "dez": 10, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "cem": 100, "mil": 1000}
ORDINAIS = {"primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2, "terceiro": 3, "terceira": 3, "quarto": 4,
            "quarta": 4, "quinto": 5, "quinta": 5}
SAUDACOES = ("oi", "olá", "ola", "e aí", "eai", "fala galera", "fala pessoal", "bom dia", "boa tarde", "boa noite",
             "tudo bem", "hoje eu vou", "hoje eu quero", "agora eu vou", "pois bem", "deixa eu", "nesse vídeo", "neste vídeo", "no vídeo de hoje")
TRANSICOES = ("vamos seguir", "seguindo", "voltando", "agora vamos", "vamos lá", "continuando", "para cá", "pra cá",
              "um pouquinho mais", "mais para frente")  # frase de passagem não abre vídeo
GANCHO_FORTE = ("você", "vocês", "pare", "nunca", "ninguém", "erro", "segredo", "por que", "porque", "como", "se você",
                "o maior", "a maior", "o pior", "a pior", "não")


def norm(t):
    return t.lower().strip(".,!?;:\"'()…-–—")


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def numero(t, artigo=False):
    """Valor numérico de uma palavra ('87%', '3', 'três'), ou None. "um"/"uma" quase sempre são artigo ("um vídeo"),
    então só contam como número com artigo=True (depois de "passo", por exemplo)."""
    n = norm(t).replace("%", "")
    if n in ("um", "uma") and not artigo:
        return None
    m = re.fullmatch(r"\d+(?:[.,]\d+)?", n)
    if m:
        return float(n.replace(".", "").replace(",", ".")) if "," in n else float(n.replace(".", ""))
    return NUMEROS.get(n)


# ───────────────────────────── vícios e tomadas repetidas ─────────────────────────────
def vicios(ws):
    """Índices de palavras que são vício de fala."""
    fora = set()
    for i, w in enumerate(ws):
        n = norm(w["t"])
        prox = ws[i + 1] if i + 1 < len(ws) else None
        pausa_dep = (prox["ini"] - w["fim"]) if prox else 9
        if n in VICIOS or re.fullmatch(r"(é|e|a|ã|u|hu?m)\1{1,}h?", n or "x"):
            fora.add(i)
        elif n == "né" and (pausa_dep > 0.25 or w["t"].rstrip()[-1:] in ",.?!" or prox is None):
            fora.add(i)
        elif n == "tipo" and w["t"].rstrip().endswith(","):  # "tipo," de muleta (com vírgula do Whisper)
            fora.add(i)
        elif prox and n == norm(prox["t"]) and len(n) <= 5 and n not in ("é",) and pausa_dep < 0.35 and n.isalpha():
            fora.add(i)  # gaguejada: "eu eu", "que que" (fica a segunda)
    return fora


def frases(ws, pausa=0.6):
    """Divide em frases por pausa longa ou pontuação final: [(i0, i1)] (i1 exclusivo)."""
    out, ini = [], 0
    for i, w in enumerate(ws):
        fim_frase = w["t"].rstrip()[-1:] in ".?!"
        longa = i + 1 < len(ws) and ws[i + 1]["ini"] - w["fim"] >= pausa
        if fim_frase or longa or i == len(ws) - 1:
            out.append((ini, i + 1))
            ini = i + 1
    return out


def tomadas_repetidas(ws, fr):
    """Frases que a pessoa recomeçou logo depois: [(i0, i1)] para tirar (fica a última tomada).
    Recomeço = a frase seguinte (ou a próxima depois de até 2 frases curtas, como "não, peraí") começa igual,
    ou a frase é curta, foi interrompida e reaparece inteira."""
    chave = lambda a, b: [norm(w["t"]) for w in ws[a:b] if norm(w["t"]) not in VICIOS]
    tirar, k = [], 0
    while k < len(fr):
        a0, a1 = fr[k]
        ca = chave(a0, a1)
        achou = None
        for j in range(k + 1, min(k + 4, len(fr))):
            b0, b1 = fr[j]
            if ws[b0]["ini"] - ws[a1 - 1]["fim"] > 20:
                break
            cb = chave(b0, b1)
            n = min(3, len(ca), len(cb))
            if (n >= 2 and ca[:n] == cb[:n]) or (1 <= len(ca) <= 6 and len(cb) > len(ca) and cb[:len(ca)] == ca):
                achou = j
                break
            if len(cb) > 4:  # no meio só cabem frases curtas de correção
                break
        if achou is not None:
            tirar.append((a0, fr[achou][0]))  # da tomada velha até o começo da nova (inclui o "peraí")
            k = achou
        else:
            k += 1
    return tirar


# ───────────────────────────── energia e ênfase ─────────────────────────────
def energia(video, ws):
    """Volume (dB RMS) de cada palavra, pelo áudio do vídeo."""
    try:
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [0.0] * len(ws)
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    out = []
    for w in ws:
        a, b = int(w["ini"] * 16000), max(int(w["fim"] * 16000), int(w["ini"] * 16000) + 160)
        seg = x[a:b]
        out.append(float(10 * np.log10(np.mean(seg ** 2) + 1e-9)) if len(seg) else -90.0)
    return out


def enfases(ws, db, n_max=8, espaco=2.5):
    """Palavras de ênfase da legenda: voz mais alta que a vizinhança, números e palavras fortes. [(i, nota)]"""
    notas = []
    for i, w in enumerate(ws):
        n = norm(w["t"])
        if not n or n in STOP or n in VICIOS:
            continue
        viz = [db[k] for k in range(max(0, i - 8), min(len(ws), i + 9)) if k != i]
        z = (db[i] - np.mean(viz)) / (np.std(viz) + 1.5) if viz else 0
        nota = z
        nota += 1.6 if numero(w["t"]) is not None or "%" in w["t"] else 0
        nota += 1.0 if sem_acento(n) in {sem_acento(f) for f in FORTES} else 0
        nota += 0.4 if len(n) >= 8 else (0.15 if len(n) >= 6 else -0.5)
        prox = ws[i + 1] if i + 1 < len(ws) else None
        nota += 0.4 if (prox is None or prox["ini"] - w["fim"] > 0.25) else 0  # palavra que fecha a ideia
        nota -= 0.8 if w.get("p", 1) < 0.5 else 0
        notas.append((nota, i))
    escolhidas = []
    for nota, i in sorted(notas, reverse=True):
        if nota < 0.9 or len(escolhidas) >= n_max:
            break
        if all(abs(ws[i]["ini"] - ws[j]["ini"]) >= espaco for j, _ in escolhidas) and \
                norm(ws[i]["t"]) not in {norm(ws[j]["t"]) for j, _ in escolhidas}:
            escolhidas.append((i, round(float(nota), 2)))
    return sorted(escolhidas)


# ───────────────────────────── gancho ─────────────────────────────
def nota_gancho(ws):
    """Nota de 0 a 10 para uma abertura (as palavras dos primeiros ~3 s), com os motivos."""
    if not ws:
        return 0.0, ["sem fala na abertura"]
    t0 = ws[0]["ini"]
    ab = [w for w in ws if w["fim"] - t0 <= 3.2] or ws[:1]
    txt = " ".join(norm(w["t"]) for w in ab)
    nota, motivos = 5.0, []
    if any(txt.startswith(s) or f" {s} " in f" {txt[:30]} " for s in SAUDACOES):
        nota -= 3
        motivos.append("abre com saudação ou anúncio (\"oi\", \"hoje eu vou\"): vá direto ao ponto")
    if any(f" {x} " in f" {txt} " for x in TRANSICOES):
        nota -= 3
        motivos.append("frase de passagem (\"vamos seguir\", \"voltando pra cá\")")
    if any(w["t"].rstrip().endswith("?") for w in ab):
        nota += 2
        motivos.append("pergunta na abertura")
    if any(f" {g} " in f" {txt} " for g in GANCHO_FORTE):
        nota += 1.5
        motivos.append("fala com o público ou promete algo forte")
    if any(numero(w["t"]) is not None for w in ab):
        nota += 1.5
        motivos.append("número concreto")
    dur = max(ab[-1]["fim"] - t0, 0.5)
    ritmo = len(ab) / dur
    if ritmo >= 2.6:
        nota += 1
        motivos.append(f"ritmo bom ({ritmo:.1f} palavras/s)")
    elif ritmo < 1.8:
        nota -= 1.5
        motivos.append(f"ritmo lento ({ritmo:.1f} palavras/s)")
    buracos = [b["ini"] - a["fim"] for a, b in zip(ab, ab[1:]) if b["ini"] - a["fim"] > 0.5]
    if buracos:
        nota -= 1.5
        motivos.append("pausa longa nos primeiros segundos")
    return float(np.clip(nota, 0, 10)), motivos


# ───────────────────────────── elementos sugeridos ─────────────────────────────
def ancora(ws, i, n=1):
    """Texto de âncora ("na") das palavras i..i+n-1 e a ocorrência dele na transcrição inteira."""
    alvo = [norm(w["t"]) for w in ws[i:i + n]]
    oc = sum(1 for k in range(i + 1) if [norm(w["t"]) for w in ws[k:k + n]] == alvo)
    return " ".join(w["t"].strip(".,!?;:") for w in ws[i:i + n]), oc


def elementos_sugeridos(ws, mantidas, estilo, espaco=3.0):
    """Elementos ancorados na fala. Só usa o que está dito: contador para porcentagem, passo/destaque para
    'primeiro/segundo passo', check e xis para certo/errado."""
    out, ultimo = [], -99.0
    for i in mantidas:
        w = ws[i]
        if w["ini"] - ultimo < espaco:
            continue
        n, t = norm(w["t"]), w["t"]
        prox = [norm(x["t"]) for x in ws[i + 1:i + 3]]
        e = None
        v = numero(t)
        if v is not None and ("%" in t or (prox[:2] == ["por", "cento"])):
            na, oc = ancora(ws, i, 1 if "%" in t else 3)
            e = {"tipo": "efeito", "nome": "contador", "na": na, "ate": v, "sufixo": "%", "y": 0.3}
        elif n in ORDINAIS and prox[:1] in (["passo"], ["ponto"], ["erro"], ["dica"], ["regra"]):
            num = ORDINAIS[n]
            resto = [x["t"].strip(".,!?;:") for x in ws[i + 2:i + 7] if x["t"]]
            na, oc = ancora(ws, i, 2)
            if estilo == "tutorial_passos":
                e = {"tipo": "passo", "numero": num, "texto": " ".join(resto[:5]).capitalize(), "na": na}
            else:
                e = {"tipo": "destaque", "texto": f"{prox[0].capitalize()} {num}", "na": na}
        elif n == "passo" and i + 1 < len(ws) and (numero(ws[i + 1]["t"], True) or 0) >= 1:
            num = int(numero(ws[i + 1]["t"], True))
            resto = [x["t"].strip(".,!?;:") for x in ws[i + 2:i + 7]]
            na, oc = ancora(ws, i, 2)
            e = ({"tipo": "passo", "numero": num, "texto": " ".join(resto[:5]).capitalize(), "na": na}
                 if estilo == "tutorial_passos" else {"tipo": "destaque", "texto": f"Passo {num}", "na": na})
        elif n in ("errado", "errada", "erro") or (n == "não" and prox[:1] in (["faça"], ["faz"])):
            na, oc = ancora(ws, i, 1)
            e = {"tipo": "efeito", "nome": "xis", "na": na}
        elif n in ("certo", "certa", "correto", "funciona", "funcionou"):
            na, oc = ancora(ws, i, 1)
            e = {"tipo": "efeito", "nome": "check", "na": na}
        if e:
            if oc > 1:
                e["ocorrencia"] = oc
            e["_motivo"] = "diretor"
            out.append(e)
            ultimo = w["ini"]
    return out


# ───────────────────────────── tudo junto ─────────────────────────────
def dirigir(palavras, video=None, estilo=None, db=None):
    """Analisa a fala e devolve o plano do diretor:
    {"cortes": [(ini, fim, motivo)], "enfase": [...], "punch": [...], "gancho": {...}, "elementos": [...]}."""
    ws = palavras
    if not ws:
        return {"cortes": [], "enfase": [], "punch": [], "gancho": {"nota": 0, "motivos": ["sem fala"]}, "elementos": []}
    fora = {i: "vício" for i in vicios(ws)}
    fr = frases(ws)
    retakes = tomadas_repetidas(ws, fr)
    for a, b in retakes:
        for i in range(a, b):
            fora.setdefault(i, "tomada repetida")
    cortes = []
    for i in sorted(fora):
        a = ws[i - 1]["fim"] if i else ws[i]["ini"]
        if cortes and cortes[-1][2] == fora[i] and cortes[-1][3] == i - 1:
            cortes[-1] = (cortes[-1][0], ws[i]["fim"], fora[i], i)
        else:
            cortes.append((max(a, ws[i]["ini"] - 0.06), ws[i]["fim"], fora[i], i))
    cortes = [(round(a, 3), round(b, 3), m) for a, b, m, _ in cortes]
    mantidas = [i for i in range(len(ws)) if i not in fora]
    if db is None:
        db = energia(video, ws) if video else [0.0] * len(ws)
    wm = [ws[i] for i in mantidas]
    enf = [(mantidas[k], nota) for k, nota in enfases(wm, [db[i] for i in mantidas])]
    punch = [ws[i] for i, nota in sorted(enf, key=lambda x: -x[1])[:3] if nota >= 1.6]
    g_nota, g_motivos = nota_gancho(wm)
    melhor = None
    for a, b in frases(wm):
        if wm[a]["ini"] - wm[0]["ini"] < 3:
            continue
        n, mot = nota_gancho(wm[a:b])
        if b - a >= 3 and (melhor is None or n > melhor["nota"]):
            melhor = {"ini": wm[a]["ini"], "fim": wm[b - 1]["fim"], "texto": " ".join(w["t"] for w in wm[a:b]),
                      "nota": round(n, 1), "motivos": mot}
    gancho = {"nota": round(g_nota, 1), "motivos": g_motivos,
              "abertura": " ".join(w["t"] for w in wm if w["fim"] - wm[0]["ini"] <= 3.2)}
    if melhor and melhor["nota"] >= g_nota + 2:
        gancho["sugestao"] = melhor
    conta = {}
    for w in wm:
        n = norm(w["t"])
        if len(n) >= 5 and n not in STOP and numero(n) is None:
            conta[n] = conta.get(n, 0) + 1
    termos = [t for t, _ in sorted(conta.items(), key=lambda x: (-x[1], -len(x[0])))[:5]]
    return {"termos_broll": termos, "cortes": cortes, "enfase": [ws[i]["t"].strip(".,!?;:") for i, _ in enf],
            "punch": [{"ini": w["ini"], "fim": round(w["fim"] + 0.35, 3), "fator": 1.14, "modo": "punch", "palavra": w["t"].strip(".,!?;:")}
                      for w in punch],
            "gancho": gancho, "elementos": elementos_sugeridos(ws, mantidas, estilo),
            "retakes": [{"ini": ws[a]["ini"], "fim": ws[b - 1]["fim"], "texto": " ".join(w["t"] for w in ws[a:b])}
                        for a, b in retakes]}


def aplicar_cortes(segs, cortes, respiro=0.04):
    """Corta os trechos do diretor dos segmentos (um segmento pode virar dois). Devolve a nova lista, renumerada."""
    out = []
    for s in segs:
        pedacos = [(s["ini"], s["fim"])]
        for a, b, _ in cortes:
            novo = []
            for x, y in pedacos:
                if b <= x or a >= y:
                    novo.append((x, y))
                    continue
                if a - x > 0.12:
                    novo.append((x, a + respiro))
                if y - b > 0.12:
                    novo.append((b, y))
            pedacos = novo
        for x, y in pedacos:
            if y - x >= 0.2:
                out.append(dict(s, ini=round(x, 3), fim=round(y, 3)))
    for i, s in enumerate(out):
        s["id"] = i
    return out


def alternar_zoom(segs, clipes_ini=(0.0,), zoom=1.08):
    """Corte seco no mesmo plano (jump cut): alterna o enquadramento (1.0 ↔ zoom) e marca "salto" para a câmera
    trocar no corte em vez de deslizar. Trechos curtos (< 1 s) ficam como o anterior."""
    clipe = lambda t: sum(1 for c in clipes_ini[1:] if t >= c)
    atual = 1.0
    for i, s in enumerate(segs):
        if i == 0 or clipe(s["ini"]) != clipe(segs[i - 1]["ini"]) or s.get("transicao"):
            atual = 1.0
            s["zoom"] = atual
            continue
        if s["ini"] - segs[i - 1]["fim"] > 0.12 and s["fim"] - s["ini"] >= 1.0:
            atual = zoom if atual == 1.0 else 1.0
            s["salto"] = True
        s["zoom"] = atual
    return segs


def texto_segmento(s, palavras):
    return " ".join(w["t"] for w in palavras if s["ini"] <= (w["ini"] + w["fim"]) / 2 < s["fim"])


def aplicar(edl, plano, palavras, clipes_ini=(0.0,), alternar=True):
    """Põe o plano do diretor no rascunho do EDL (cortes, zoom alternado, ênfases, punches e elementos).
    alternar=False (marca com enquadramento contínuo, `"diretor": {"alternar_zoom": false}`) deixa o zoom 1.0 nos cortes."""
    segs = aplicar_cortes(edl["segmentos"], plano["cortes"])
    for s in segs:
        if s.get("texto") != "(sem fala)":
            s["texto"] = texto_segmento(s, palavras)
    edl["segmentos"] = alternar_zoom(segs, clipes_ini) if alternar else segs
    leg = edl.setdefault("legendas", {})
    if leg.get("ativo", True) and not leg.get("enfase"):
        leg["enfase"] = plano["enfase"]
    dentro = lambda t: any(s["ini"] <= t < s["fim"] - 0.5 for s in segs)
    edl["zooms"] = edl.get("zooms") or [{k: z[k] for k in ("ini", "fim", "fator", "modo")} for z in plano["punch"] if dentro(z["ini"])]
    if not edl.get("elementos"):
        edl["elementos"] = [{k: v for k, v in e.items() if not k.startswith("_")} for e in plano["elementos"]
                            if any(s["ini"] <= _tempo_na(e, palavras) < s["fim"] for s in segs)]
    return edl


def montar_gancho(edl, plano, palavras, max_dur=6.5):
    """Abre o vídeo pela frase mais forte, sem repetir: tira o anúncio do começo ("agora eu vou fazer um vídeo…"),
    move o trecho do gancho para a abertura ("gancho": true) e põe a vinheta logo depois dele (intro.apos_gancho).
    A fala não muda: só a ordem. Devolve o EDL; o plano ganha "gancho.aplicado"."""
    g = plano.get("gancho", {})
    sug = g.get("sugestao")
    if not sug or not edl.get("segmentos"):
        return edl
    ws = [w for w in palavras if sug["ini"] - 0.01 <= w["ini"] and w["fim"] <= sug["fim"] + 0.01]
    fim = sug["fim"]
    for w in ws:  # gancho curto: termina na última palavra que cabe em max_dur
        if w["fim"] - sug["ini"] <= max_dur:
            fim = w["fim"]
    ini, fim = round(max(sug["ini"] - 0.08, 0), 3), round(fim + 0.08, 3)
    cortes = [(ini, fim, "gancho movido para a abertura")]
    if any("anúncio" in m for m in g.get("motivos", [])):  # o anúncio do começo sai: o gancho já diz do que é o vídeo
        fr = frases(palavras)
        if fr:
            a, b = fr[0]
            cortes.append((round(palavras[a]["ini"] - 0.05, 3), round(palavras[b - 1]["fim"] + 0.05, 3), "anúncio na abertura"))
    resto = [dict(sg, fim=min(sg["fim"], ini) if sg["ini"] < ini else sg["fim"]) for sg in aplicar_cortes(edl["segmentos"], cortes)]
    resto = [sg for sg in resto if sg["fim"] - sg["ini"] >= 0.2]
    abre = {"id": 0, "ini": ini, "fim": fim, "zoom": 1.0, "transicao": None, "gancho": True,
            "texto": " ".join(w["t"] for w in palavras if ini <= (w["ini"] + w["fim"]) / 2 < fim)}
    edl["segmentos"] = [abre] + resto
    for i, sg in enumerate(edl["segmentos"]):
        sg["id"] = i
    intro = edl.setdefault("intro", {"ativo": True})
    if intro.get("ativo", True):
        intro["apos_gancho"] = True
    g["aplicado"] = {"ini": ini, "fim": fim, "anuncio_cortado": len(cortes) > 1}
    return edl


def _tempo_na(e, palavras):
    alvo = [norm(x) for x in e["na"].split()]
    n = 0
    for i in range(len(palavras)):
        if [norm(w["t"]) for w in palavras[i:i + len(alvo)]] == alvo:
            n += 1
            if n == e.get("ocorrencia", 1):
                return palavras[i]["ini"]
    return -1


def resumo_diretor(plano):
    """Relatório curto do diretor (vai para o terminal e para a transcricao.txt)."""
    g = plano["gancho"]
    linhas = [f"# Diretor: gancho {g['nota']:.1f}/10 ({'; '.join(g['motivos']) or 'sem observações'})"]
    if g.get("sugestao"):
        sg = g["sugestao"]
        linhas.append(f"#   Abertura mais forte ({sg['nota']:.1f}/10), em {sg['ini']:.2f}–{sg['fim']:.2f}: \"{sg['texto']}\". "
                      "Para abrir com ela, copie o trecho para o início com \"gancho\": true.")
    if g.get("aplicado"):
        ap = g["aplicado"]
        linhas.append(f"#   Aplicado: o trecho {ap['ini']:.2f}–{ap['fim']:.2f} abre o vídeo (gancho), a vinheta vem logo depois"
                      + (" e o anúncio do começo saiu." if ap["anuncio_cortado"] else ". Confira se a história continua sem ele."))
    vic = [c for c in plano["cortes"] if c[2] == "vício"]
    if vic:
        linhas.append(f"#   {len(vic)} vícios cortados")
    for r in plano.get("retakes", []):
        linhas.append(f"#   Tomada repetida cortada ({r['ini']:.2f}–{r['fim']:.2f}): \"{r['texto']}\"")
    if plano["enfase"]:
        linhas.append("#   Ênfases: " + ", ".join(plano["enfase"]))
    if plano["punch"]:
        linhas.append("#   Punch de zoom em: " + ", ".join(z["palavra"] for z in plano["punch"]))
    if plano.get("termos_broll"):
        linhas.append("#   Termos para b-roll (editor.py broll \"termo\" edl.json): " + ", ".join(plano["termos_broll"]))
    if plano["elementos"]:
        linhas.append("#   Elementos sugeridos: " + ", ".join(f"{e.get('nome', e['tipo'])} em \"{e['na']}\"" for e in plano["elementos"]))
    if plano.get("cena"):
        linhas.append(plano["cena"])
    return "\n".join(linhas)
