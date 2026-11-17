"""Tour pela casa: capítulos por cômodo e rótulos presos ao que a mão aponta, escritos pelo `analisar`.

Num vídeo em que a câmera anda pelo ambiente (detectado em `cena.tour_pela_casa`), o editor faz sozinho o que antes era
marcado à mão no EDL:

- **Capítulos.** Cada troca de cômodo vira um `passo` com `rotulo: "Parte"` e a transição `luz` com o sopro. A troca é
  achada pela fala ("vamos seguir", "aqui na sala"), pela mudança de cor do ambiente (assinatura de 1 s em `cena.json`)
  e pela caminhada cortada entre dois trechos. O título vem do lugar ou do objeto citado no começo do capítulo
  ("esse cantinho" → "O cantinho", "aqui na sala" → "A sala").
- **Rótulos.** Cada coisa que a pessoa nomeia ("firmeza de Caboclo", "quartinha de Oxum") vira uma `anotacao` editorial
  presa ao ponto para onde o dedo aponta naquela hora (`cena.json`, "apontar"). Sem mão na imagem, o rótulo de "X de Y"
  fica no centro do quadro, para onde a câmera está virada. Um rótulo por vez, no máximo 8, sem legenda por baixo.

Tudo sai marcado em `_motivo` no relatório: o agente confere na prévia e ajusta o ponto (`fixar`) se precisar.
"""
import numpy as np

from .diretor import TRANSICOES, ancora, norm

DET_M = {"o", "os", "um", "uns", "meu", "meus", "esse", "esses", "este", "estes", "seu", "no", "nos", "do", "dos", "nesse", "neste"}
DET_F = {"a", "as", "uma", "umas", "minha", "minhas", "essa", "essas", "esta", "estas", "na", "nas", "da", "das", "nessa", "nesta"}
PREP = {"de", "do", "da", "dos", "das", "para", "pra"}
VAZIAS = {"coisa", "coisas", "vídeo", "pouco", "pouquinho", "lado", "vez", "jeito", "gente", "tempo", "dia", "você", "isso",
          "isto", "aquilo", "tudo", "todas", "todos", "algumas", "alguns", "mais", "parte", "forma", "hora", "agora", "aqui",
          "cá", "lá", "eu", "ele", "ela", "que", "qual", "quem", "frente", "bastante", "muito", "muita", "outro", "outra",
          "mesmo", "mesma", "espiritualidade", "vida"}
TITULOS = {"seu", "dona", "são", "santa", "pai", "mãe", "preto", "preta", "vó", "vovó", "vô", "vovô", "nossa"}
LUGARES = {"sala", "cozinha", "quarto", "escritório", "varanda", "quintal", "jardim", "banheiro", "garagem", "corredor",
           "entrada", "cantinho", "congá", "altar", "terreiro", "loja", "oficina", "sacada",
           "área", "casa", "praia", "rua", "parque", "igreja", "cantina", "barracão", "roça"}
LUGAR_FALADO = ("aqui na", "aqui no", "agora na", "agora no", "chegando na", "chegando no", "entrando na", "entrando no")


def _palavra(w):
    return norm(w["t"])


def nomes_citados(palavras, correcoes=None):
    """Coisas nomeadas na fala. [{i (índice da palavra que dá nome), ini, sobre, nome, genero, forma}]:
    forma "de" = "firmeza de Caboclo" (sobrelinha + nome); forma "simples" = "um congá" (só o nome)."""
    cor = {k.lower(): v for k, v in (correcoes or {}).items()}
    t = [_palavra(w) for w in palavras]
    corrige = lambda k: cor.get(t[k], palavras[k]["t"].strip(".,!?;:\"'()…"))
    cap = lambda s: s if s[:1].isupper() else s[:1].upper() + s[1:]
    out, k = [], 0
    while k < len(t) - 1:
        lista = palavras[k]["t"].rstrip()[-1:] == "," and k + 2 < len(t) and t[k + 2] in PREP  # "…, firmeza de baiano"
        if (t[k] not in DET_M | DET_F and not lista) or t[k + 1] in VAZIAS | PREP | DET_M | DET_F or len(t[k + 1]) < 3:
            k += 1
            continue
        n, genero = k + 1, "f" if t[k] in DET_F or (lista and t[k + 1].endswith("a")) else "m"
        fim_frase = palavras[n]["t"].rstrip()[-1:] in ",.!?;"
        j = n + 1
        while j < len(t) and t[j] in ("aqui", "lá"):  # "uma firmeza aqui para a prosperidade"
            j += 1
        if not fim_frase and j < len(t) - 1 and t[j] in PREP:
            m = j + 1
            if m < len(t) and t[m] in ("a", "o"):  # "para a prosperidade", "para o Oxalá"
                m += 1
            if m < len(t) and t[m] not in (VAZIAS | DET_M | DET_F) - TITULOS and len(t[m]) >= 2:
                i_nome = m
                nome = [corrige(m)]
                if (t[m] in TITULOS and m + 1 < len(t) and palavras[m]["t"][-1:] not in ",.!?;"
                        and (t[m] not in ("preto", "preta") or t[m + 1] in ("velho", "velha"))):
                    nome.append(corrige(m + 1))
                    m += 1
                if t[m] == "anjo" and t[m + 1:m + 3] == ["de", "guarda"]:
                    nome += ["de", "guarda"]
                    m += 2
                # "firmeza de Caboclo" (de quem é: nome próprio, com maiúscula); "firmeza para a prosperidade" (para quê)
                proprio = t[j] in ("de", "do", "da", "dos", "das")
                minusc = {"de", "do", "da", "seu", "dona", "vó", "vovó", "vô", "vovô", "anjo", "guarda"}
                nome = " ".join(x if (x.lower() in minusc and (k_ > 0 or x.lower() in ("seu", "dona"))) or not proprio else cap(x) for k_, x in enumerate(nome))
                out.append({"i": i_nome, "ini": palavras[n]["ini"], "genero": genero, "forma": "de", "nome": nome,
                            "sobre": " ".join(palavras[q]["t"].strip(".,!?;:") for q in range(n, i_nome) if t[q] not in ("aqui", "lá"))})
                k = m  # o nome pode fechar uma lista: "…de baiano, quartinha de anjo de guarda"
                continue
        out.append({"i": n, "ini": palavras[n]["ini"], "sobre": "", "nome": corrige(n), "genero": genero, "forma": "simples"})
        k = n + 1
    return out


def _assinatura(cena, a, b):
    s = [x[1:] for x in cena.get("assinaturas", []) if a <= x[0] < b]
    return np.mean(np.array(s, float), axis=0) if s else None


def capitulos(cena, palavras, segs, max_caps=3, espaco=12.0, correcoes=None):
    """Onde começa cada capítulo (segmentos do EDL) e o título. Devolve [{seg, titulo, motivo}] (o 1º é a abertura)."""
    corpo = [s for s in segs if not s.get("gancho")]
    if len(corpo) < 3:
        return []
    t = [_palavra(w) for w in palavras]
    nomes = nomes_citados(palavras, correcoes)

    def falas(a, b):
        return " ".join(t[k] for k, w in enumerate(palavras) if a <= w["ini"] < b)
    dist = []
    for k in range(1, len(corpo)):
        x, y = _assinatura(cena, corpo[k - 1]["fim"] - 4, corpo[k - 1]["fim"]), _assinatura(cena, corpo[k]["ini"], corpo[k]["ini"] + 4)
        dist.append(float(np.linalg.norm(x - y)) if x is not None and y is not None else 0.0)
    ref = float(np.median([d for d in dist if d > 0])) if any(dist) else 1.0
    cands = []
    for k in range(1, len(corpo)):
        s, ant = corpo[k], corpo[k - 1]
        inicio = falas(s["ini"], s["ini"] + 3.0)
        motivos, nota = [], dist[k - 1] / max(ref, 1e-6)
        if nota >= 1.6:
            motivos.append("o ambiente muda")
        if any(f in inicio for f in TRANSICOES + LUGAR_FALADO) or any(f in falas(ant["fim"] - 2.5, ant["fim"]) for f in TRANSICOES):
            nota += 2.0
            motivos.append("fala de passagem")
        if s["ini"] - ant["fim"] >= 1.0:
            nota += 0.5
            motivos.append("caminhada cortada")
        if any(norm(x["nome"]) in LUGARES for x in nomes if s["ini"] - 0.3 <= x["ini"] < s["ini"] + 8):
            nota += 1.0
            motivos.append("nomeia um lugar")
        if nota >= 2.0 and motivos:
            cands.append((nota, k, ", ".join(motivos)))
    ini0, fim0 = corpo[0]["ini"], corpo[-1]["fim"]
    escolhidos = []
    # capítulo que nomeia o lugar vem primeiro (o título sai certo); depois, a nota
    for nota, k, motivo in sorted(cands, key=lambda c: ("nomeia um lugar" in c[2], c[0]), reverse=True):
        a = corpo[k]["ini"]
        if a - ini0 < 8 or fim0 - a < 8 or any(abs(a - corpo[j]["ini"]) < espaco for j, _ in escolhidos):
            continue
        escolhidos.append((k, motivo))
        if len(escolhidos) >= max_caps - 1:
            break
    if not escolhidos:
        return []
    out = []
    for n, (k, motivo) in enumerate([(0, "abertura")] + sorted(escolhidos)):
        a = corpo[k]["ini"]
        perto = [x for x in nomes if a - 0.3 <= x["ini"] < a + 8]
        lugar = next((x for x in perto if norm(x["nome"]) in LUGARES), None) or next((x for x in perto if x["forma"] == "simples"), None)
        titulo = (("A " if lugar["genero"] == "f" else "O ") + lugar["nome"].lower()) if lugar else f"Parte {n + 1}"
        out.append({"seg": corpo[k]["id"], "titulo": titulo, "motivo": motivo, "ini": a})
    return out


def _alvo(cena, t0):
    """Ponto (t, x, y) para onde o dedo aponta perto de t0 (de 0,8 s antes a 1,5 s depois), ou None."""
    melhor = None
    for e in cena.get("apontar", []):
        if e["ini"] - 1.5 <= t0 <= e["fim"] + 0.8:
            p = min(e["trilha"], key=lambda q: abs(q[0] - t0))
            if melhor is None or abs(p[0] - t0) < abs(melhor[0] - t0):
                melhor = p
    return melhor


def rotulos(cena, palavras, segs, max_rotulos=8, espaco=2.2, correcoes=None):
    """Anotações editoriais para as coisas nomeadas: presas ao alvo do dedo, ou ao centro do quadro ("X de Y" sem mão)."""
    dentro = lambda tt: any(s["ini"] - 0.1 <= tt < s["fim"] - 0.1 for s in segs if not s.get("gancho"))
    cands = []
    for x in nomes_citados(palavras, correcoes):
        w = palavras[x["i"]]
        if not dentro(w["ini"]) or norm(x["nome"]) in LUGARES:
            continue
        p = _alvo(cena, w["ini"])
        if p is None and x["forma"] != "de":
            continue  # nome solto sem dedo apontando: não dá para saber onde está
        origem = "dedo apontando" if p else "centro do quadro (sem mão)"
        p = p or [round(w["ini"], 2), 0.5, 0.5]
        na, oc = ancora(palavras, x["i"])
        el = {"tipo": "anotacao", "estilo": "editorial", "texto": f"{x['sobre']}/{x['nome']}" if x["sobre"] else x["nome"],
              "na": na, "segura": 1.4, "fixar": [round(p[0], 2), round(p[1], 3), round(p[2], 3)], "caixa": True, "tam": 0.066,
              "sem_legenda": True, "som": False, "_motivo": f"tour: rótulo de \"{x['nome']}\" ({origem})", "_t": w["ini"],
              "_prio": 0 if p and origem.startswith("dedo") else 1}
        if oc > 1:
            el["ocorrencia"] = oc
        cands.append(el)
    escolhidos = []
    for e in sorted(cands, key=lambda e: (e["_prio"], e["_t"])):  # primeiro o que o dedo mostra, depois o resto
        if len(escolhidos) < max_rotulos and all(abs(e["_t"] - o["_t"]) >= espaco for o in escolhidos):
            escolhidos.append(e)
    return sorted(escolhidos, key=lambda e: e["_t"])


def dirigir_tour(cena, palavras, edl):
    """Capítulos e rótulos de um tour, aplicados ao EDL sem cobrir o que já está lá. Devolve (edl, linhas do relatório)."""
    from .cena import _janela
    segs = edl["segmentos"]
    correcoes = edl.get("legendas", {}).get("correcoes", {})
    linhas, novos = [], []
    caps = capitulos(cena, palavras, segs, correcoes=correcoes)
    por_id = {s["id"]: s for s in segs}
    for n, c in enumerate(caps, 1):
        s = por_id[c["seg"]]
        w = next((k for k, x in enumerate(palavras) if x["ini"] >= s["ini"] - 0.05), None)
        if w is None:
            continue
        na, oc = ancora(palavras, w, 2)
        el = {"tipo": "passo", "rotulo": "Parte", "numero": n, "texto": c["titulo"], "na": na, "segura": 1.8, "sempre": True,
              "x": 0.45, "y": 0.2, "tam": 0.062, "som": "pagina", "_motivo": f"tour: capítulo ({c['motivo']})"}
        if oc > 1:
            el["ocorrencia"] = oc
        novos.append(el)
        if n > 1 and not s.get("transicao"):
            s["transicao"], s["som"] = "luz", "whoosh-sopro"
        linhas.append(f"#   capítulo {n} em {c['ini']:.1f}s: \"{c['titulo']}\" ({c['motivo']})")
    novos += rotulos(cena, palavras, segs, correcoes=correcoes)
    for e in novos:
        if e["tipo"] == "anotacao":
            linhas.append(f"#   rótulo em {e['_t']:.1f}s: {e['texto'].replace('/', ' ')} ({e['_motivo'].split('(')[-1].rstrip(')')})")
    # texto não cobre texto: o que já estava no EDL (título do gancho, destaques) ganha
    ocupado = [_janela(e, palavras) for e in edl.get("elementos", []) if e.get("tipo") not in ("efeito", "som", "objeto3d", "leo")]
    aceitos = []
    for e in novos:
        a, b = _janela(e, palavras)
        b = max(b, a + e.get("segura", 1.4))
        if a >= 0 and not any(x < b and a < y for x, y in ocupado):
            aceitos.append({k: v for k, v in e.items() if not k.startswith("_")})
            ocupado.append((a, b))
    edl["elementos"] = edl.get("elementos", []) + aceitos
    return edl, linhas
