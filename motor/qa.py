"""Conferência visual automática do vídeo renderizado.

Durante o render, cada quadro amostrado registra onde ficaram a legenda, os elementos e o rosto. Daqui saem os avisos:

- elemento ou legenda fora da área segura do Reels (topo, rodapé com a legenda do post e coluna de botões à direita);
- elemento cobrindo o rosto, legenda em cima do rosto, legenda brigando com um elemento;
- legenda sem contraste (estilo limpa, sem caixa, sobre fundo claro);
- loudness e pico fora do alvo; vídeo longo demais para Reels; gancho fraco (nota do diretor).

O resultado vai para o terminal e para conferencia.json, ao lado do final.mp4.
"""
import json

import cv2
import numpy as np

from .audio import medir_audio
from .diretor import nota_gancho

# Área segura do Reels em 9:16 (fração da tela): o topo tem a barra do app, o rodapé a legenda do post e o nome,
# a coluna da direita os botões de curtir, comentar e compartilhar.
SEGURA = {"x0": 0.05, "x1": 0.95, "y0": 0.09, "y1": 0.80, "botoes_x": 0.86, "botoes_y": 0.55}
AMOSTRA = 5  # um quadro a cada 5 é conferido
SEM_ROSTO = {"hud_rosto", "texto_atras", "efeito"}


def _inter(a, b):
    """Área da interseção de duas caixas (x0, y0, x1, y1)."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)


def _area(a):
    return max(a[2] - a[0], 0) * max(a[3] - a[1], 0)


def caixa_rosto(rosto):
    cx, cy, h = rosto
    return (cx - 0.42 * h, cy - 0.6 * h, cx + 0.42 * h, cy + 0.55 * h)


def conferir_quadro(W, H, t, caixas, legenda, rosto, plano, fundo_legenda=None, vertical=True):
    """Avisos de um quadro. caixas: [(rótulo, tipo, x0, y0, x1, y1)]; legenda: (x0, y0, x1, y1) ou None;
    rosto: (cx, cy, altura) no quadro de saída ou None; fundo_legenda: luminância média sob a legenda (estilo limpa)."""
    av = []
    s = SEGURA
    fora = lambda c: (c[0] < s["x0"] * W or c[2] > s["x1"] * W or c[1] < s["y0"] * H or c[3] > s["y1"] * H
                      or (c[2] > s["botoes_x"] * W and c[3] > s["botoes_y"] * H))
    face = caixa_rosto(rosto) if rosto else None
    for rot, tipo, *c in caixas:
        if vertical and fora(c):
            av.append(("fora da área segura", rot, t))
        if face and plano == "rosto" and tipo not in SEM_ROSTO and _inter(c, face) > 0.25 * _area(face):
            av.append(("cobre o rosto", rot, t))
        if legenda and _inter(c, legenda) > 0.2 * max(_area(legenda), 1):
            av.append(("legenda brigando com elemento", rot, t))
    if legenda:
        if vertical and fora(legenda):
            av.append(("fora da área segura", "legenda", t))
        if face and plano == "rosto" and _inter(legenda, face) > 0.15 * _area(face):
            av.append(("legenda em cima do rosto", "legenda", t))
        if fundo_legenda is not None and fundo_legenda > 170:
            av.append(("legenda sem contraste", "legenda", t))
    return av


def agrupar(avisos, folga=0.6):
    """Junta avisos iguais em trechos de tempo: [{"problema", "onde", "de", "ate"}]."""
    out = {}
    for prob, rot, t in sorted(avisos, key=lambda a: (a[0], a[1], a[2])):
        lst = out.setdefault((prob, rot), [])
        if lst and t - lst[-1][1] <= folga:
            lst[-1][1] = t
        else:
            lst.append([t, t])
    return [{"problema": p, "onde": r, "de": round(a, 2), "ate": round(b, 2)}
            for (p, r), lst in sorted(out.items()) for a, b in lst if b - a >= 0.2 or p in ("fora da área segura", "borda esticada")]


DICAS = {
    "fora da área segura": "mude x/y para dentro de 5–95% na largura e 9–80% na altura (longe dos botões à direita)",
    "cobre o rosto": "suba o elemento (y menor), mande para o lado ou use o plano dividido",
    "legenda em cima do rosto": "desça a legenda (legendas.posicao_y) ou suba o enquadramento",
    "legenda brigando com elemento": "mova o elemento ou a legenda; os dois não podem dividir o mesmo espaço",
    "borda esticada": "a imagem saiu da fonte (estabilização ou enquadramento): refaça o analisar com --estabilizar atualizado "
                      "ou tire o zoom/tremor desse trecho. Nunca entregue com este aviso",
    "legenda sem contraste": "use o estilo marcada, um look mais escuro ou suba a legenda para uma área escura",
}


def nota_abertura(ctx):
    """Nota do gancho na abertura do vídeo editado (depois dos cortes e na ordem dos segmentos), não na do bruto."""
    ws = []
    for sg in ctx.segs:
        for w in ctx.an.get("palavras", []):
            if sg["qa"] <= (w["ini"] + w["fim"]) / 2 < sg["qb"]:
                ws.append(dict(w, ini=sg["o"] + w["ini"] - sg["qa"], fim=sg["o"] + w["fim"] - sg["qa"]))
    if not ws:
        return None
    nota, motivos = nota_gancho(ws)
    return {"nota": round(nota, 1), "motivos": motivos, "abertura": " ".join(w["t"] for w in ws if w["fim"] - ws[0]["ini"] <= 3.2)}


def relatorio(ctx, final, avisos):
    """Imprime e grava conferencia.json. Devolve a lista de problemas (vazia = confere)."""
    probs = agrupar(avisos)
    try:
        lufs, pico = medir_audio(final)
    except (ValueError, IndexError):
        lufs = pico = None
    if lufs is not None and not -17.5 <= lufs <= -14.5:
        probs.append({"problema": "loudness fora do alvo", "onde": f"{lufs:.1f} LUFS (alvo -16)", "de": 0, "ate": round(ctx.total, 2)})
    if pico is not None and pico > -1.0:
        probs.append({"problema": "pico alto", "onde": f"{pico:.1f} dBFS (máximo -1)", "de": 0, "ate": round(ctx.total, 2)})
    if ctx.total > 90:
        probs.append({"problema": "vídeo longo", "onde": f"{ctx.total:.0f}s (Reels rende melhor até 90 s)", "de": 0,
                      "ate": round(ctx.total, 2)})
    gancho = nota_abertura(ctx)
    diretor = ctx.pasta / "diretor.json"
    if diretor.exists() and gancho is not None:
        sug = json.load(open(diretor)).get("gancho", {}).get("sugestao")
        if sug:
            gancho["sugestao"] = sug
    if gancho and gancho["nota"] < 6 and not any(s.get("gancho") for s in ctx.edl["segmentos"]):
        probs.append({"problema": "gancho fraco", "onde": f"nota {gancho['nota']}/10 nos primeiros 3 s", "de": 0, "ate": 3})
    json.dump({"confere": not probs, "loudness": lufs, "pico": pico, "problemas": probs,
               "gancho": gancho}, open(ctx.pasta / "conferencia.json", "w"), ensure_ascii=False, indent=1)
    if not probs:
        print(f"Conferência visual: confere (áudio {lufs:.1f} LUFS, pico {pico:.1f} dBFS)" if lufs is not None
              else "Conferência visual: confere")
        return probs
    print(f"Conferência visual: {len(probs)} ponto(s) para olhar (conferencia.json):")
    for p in probs:
        dica = DICAS.get(p["problema"], "")
        print(f"  - {p['problema']}: {p['onde']} ({p['de']:.1f}s a {p['ate']:.1f}s)" + (f". {dica}" if dica else ""))
    return probs


def borda_ruim(quadro, minimo=6):
    """Faixa preta na borda do quadro-base: área que a estabilização não cobriu (ela preenche com preto, nunca estica a
    borda). Devolve [(lado, largura em px)]. Vazio = bordas limpas."""
    g = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
    achados = []
    for lado, linhas in (("esquerda", g.T), ("direita", g.T[::-1]), ("topo", g), ("base", g[::-1])):
        preta = linhas[:200].max(axis=1) < 14
        n = int(np.argmin(preta)) if not preta.all() else len(preta)
        if n >= minimo:
            achados.append((lado, n))
    return achados
