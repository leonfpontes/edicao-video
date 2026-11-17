"""Leitura da cena: o que acontece na imagem, além da fala. Gestos da mão, movimento da cabeça e da câmera.

O `analisar` lê o vídeo a 10 quadros por segundo e grava `cena.json`:

- gestos: dedo para cima, apontar para a câmera, mão aberta, joinha, joinha para baixo, "V" e punho fechado, cada um com
  a trilha da ponta do dedo (ou do centro da mão), em coordenadas da fonte (0 a 1);
- cabeça: aceno de "sim" (cima e baixo) e de "não" (lado a lado), com a trilha do rosto;
- câmera: panorâmica ou giro pelo ambiente (com a trilha de um ponto do ambiente, para um texto "grudar" na parede) e
  afastar ou aproximar a câmera (o rosto encolhe ou cresce: "ampliar a perspectiva").

O diretor transforma cada leitura num elemento que acompanha o movimento (campo "seguir" do EDL). O render projeta a
trilha da fonte no quadro de saída, depois do enquadramento, então o efeito fica colado na mão, no rosto ou na parede.

Sem o modelo de gestos (`modelos/gesture_recognizer.task`, baixado pelo setup), a leitura de mão é pulada e o resto
continua.
"""
import math

import cv2
import numpy as np

from .config import FPS, MODELOS

PASSO = 3  # lê 1 quadro a cada 3 (10 por segundo a 30 fps)
GESTOS = {"Pointing_Up": "dedo_cima", "Open_Palm": "mao_aberta", "Thumb_Up": "joinha", "Thumb_Down": "joinha_baixo",
          "Victory": "vitoria", "Closed_Fist": "punho", "ILoveYou": "rock"}
NOMES = {"dedo_cima": "dedo para cima", "aponta_camera": "aponta para a câmera", "mao_aberta": "mão aberta",
         "joinha": "joinha", "joinha_baixo": "joinha para baixo", "vitoria": "V de vitória", "punho": "punho fechado",
         "rock": "mão de rock", "aceno_sim": "cabeça: sim", "aceno_nao": "cabeça: não", "panoramica": "câmera passeando",
         "giro": "giro pelo ambiente", "afasta": "câmera se afasta", "aproxima": "câmera se aproxima"}


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def aponta_camera(lm):
    """Indicador esticado na direção da lente: a ponta fica bem mais perto da câmera que o punho (z), o dedo parece
    curto na imagem (escorço) e o médio e o anelar estão dobrados."""
    pulso, mcp, ponta = lm[0], lm[5], lm[8]
    dobrado = lambda tip, pip: _dist(lm[tip], pulso) < _dist(lm[pip], pulso) * 1.12
    perto = ponta.z - pulso.z < -0.07
    curto = _dist(ponta, mcp) < 0.75 * max(_dist(mcp, pulso), 1e-3)
    return perto and curto and dobrado(12, 10) and dobrado(16, 14)


def alvo_do_dedo(lm):
    """Indicador esticado (médio e anelar dobrados) apontando para algo do ambiente: devolve o ponto (0 a 1) um pouco
    além da ponta do dedo, na direção do dedo; None se a mão não aponta."""
    pulso, mcp, pip, ponta = lm[0], lm[5], lm[6], lm[8]
    dobrado = lambda tip, p_: _dist(lm[tip], pulso) < _dist(lm[p_], pulso) * 1.12
    if _dist(ponta, pulso) < _dist(pip, pulso) * 1.15 or not (dobrado(12, 10) and dobrado(16, 14)) or aponta_camera(lm):
        return None
    dx, dy = ponta.x - mcp.x, ponta.y - mcp.y
    return min(max(ponta.x + 1.2 * dx, 0.03), 0.97), min(max(ponta.y + 1.2 * dy, 0.03), 0.97)


def _juntar(amostras, chave, gap=0.35, minimo=0.3):
    """[(t, rotulo, x, y)] → eventos contínuos {tipo, ini, fim, trilha} (buracos curtos não quebram o gesto)."""
    eventos, cur = [], None
    for t, rot, x, y in amostras:
        if cur and rot == cur[chave] and t - cur["fim"] <= gap:
            cur["fim"] = t
            cur["trilha"].append([round(t, 2), round(x, 4), round(y, 4)])
            continue
        if cur and cur["fim"] - cur["ini"] >= minimo:
            eventos.append(cur)
        cur = {chave: rot, "ini": t, "fim": t, "trilha": [[round(t, 2), round(x, 4), round(y, 4)]]}
    if cur and cur["fim"] - cur["ini"] >= minimo:
        eventos.append(cur)
    for e in eventos:
        e["ini"], e["fim"] = round(e["ini"], 2), round(e["fim"] + PASSO / FPS, 2)
    return eventos


def _oscila(v, amp):
    """Quantas vezes a série muda de direção com amplitude >= amp (aceno)."""
    ext, sentido, ref = 0, 0, v[0]
    for x in v[1:]:
        d = x - ref
        if abs(d) >= amp:
            s = 1 if d > 0 else -1
            if s != sentido:
                ext += 1 if sentido else 0
                sentido = s
            ref = x
        elif (x - ref) * sentido > 0:
            ref = x
    return ext


def cabeca(rostos):
    """Acenos em janelas de 3,5 s pela pose do rosto (nariz em relação aos olhos): "sim" quando a cabeça sobe e desce
    2+ vezes, "não" quando vira de um lado para o outro 2+ vezes. O "sim" é procurado primeiro: ao inclinar a cabeça o
    rosto também gira um pouco, e o contrário é raro."""
    a = np.array([r for r in rostos if len(r) >= 6])
    if len(a) < 8:
        return []

    def procurar(tipo, col, amp, minimo, livre):
        achados, i = [], 0
        while i < len(a):
            j = np.searchsorted(a[:, 0], a[i, 0] + 3.5)
            w = a[i:j]
            if (len(w) >= 8 and w[-1, 0] - w[0, 0] > 1.0 and livre(w[0, 0], w[-1, 0])
                    and _oscila(w[:, col], amp) >= 2 and np.ptp(w[:, col]) >= minimo):
                ev = {"tipo": tipo, "ini": round(float(w[0, 0]), 2), "fim": round(float(w[-1, 0]), 2),
                      "trilha": [[round(float(r[0]), 2), round(float(r[1]), 4), round(float(r[2]), 4)] for r in w]}
                if achados and ev["ini"] - achados[-1]["fim"] < 0.5:
                    achados[-1]["fim"], achados[-1]["trilha"] = ev["fim"], achados[-1]["trilha"] + ev["trilha"]
                else:
                    achados.append(ev)
                i = j
                continue
            i += 1
        return achados

    sim = procurar("aceno_sim", 4, 0.06, 0.15, lambda a0, b0: True)
    nao = procurar("aceno_nao", 5, 0.25, 0.5, lambda a0, b0: not any(e["ini"] < b0 and a0 < e["fim"] for e in sim))
    return sorted(sim + nao, key=lambda e: e["ini"])


def camera(passos, rostos, dur):
    """Panorâmica/giro: a imagem do ambiente corre de lado (>= 22% da largura por segundo) por 0,5 s ou mais; giro quando
    ela anda mais de uma tela inteira. Afastar/aproximar: o rosto encolhe ou cresce 30% ou mais em até 3 s."""
    out = []
    if passos:
        p = np.array(passos)  # t, dx, dy (fração da largura/altura por passo)
        vel = np.abs(p[:, 1]) * FPS / PASSO
        mov = vel > 0.22
        k = 0
        while k < len(p):
            if not mov[k]:
                k += 1
                continue
            m = k
            while m + 1 < len(p) and (mov[m + 1] or (m + 2 < len(p) and mov[m + 2])):
                m += 1
            if p[m, 0] - p[k, 0] >= 0.5:
                total = float(np.sum(p[k:m + 1, 1]))
                # um ponto do ambiente (começa no centro alto da tela) andando com a imagem
                x, y, trilha = 0.5, 0.32, []
                for t, dx, dy in p[k:m + 1]:
                    x, y = x + dx, y + dy
                    trilha.append([round(float(t), 2), round(x, 4), round(y, 4)])
                out.append({"tipo": "giro" if abs(total) > 1.0 else "panoramica", "ini": round(float(p[k, 0]), 2),
                            "fim": round(float(p[m, 0]), 2), "lado": "esquerda" if total < 0 else "direita",
                            "deslocamento": round(total, 2), "trilha": trilha})
            k = m + 1
    if len(rostos) >= 4:
        a = np.array([r[:4] for r in rostos])
        i = 0
        while i < len(a):
            j = np.searchsorted(a[:, 0], a[i, 0] + 3.0)
            w = a[i:j]
            if len(w) >= 4:
                h0 = float(np.median(a[i:i + 3, 3]))
                k_min, k_max = int(np.argmin(w[:, 3])), int(np.argmax(w[:, 3]))
                tipo, k = None, None
                if w[k_min, 3] < 0.7 * h0 and k_min > 0:
                    tipo, k = "afasta", k_min
                elif w[k_max, 3] > 1.3 * h0 and k_max > 0:
                    tipo, k = "aproxima", k_max
                if tipo:
                    out.append({"tipo": tipo, "ini": round(float(w[0, 0]), 2), "fim": round(float(w[k, 0]), 2),
                                "fator": round(float(w[k, 3] / h0), 2),
                                "trilha": [[round(float(t), 2), round(float(x), 4), round(float(y), 4)] for t, x, y, _ in w[:k + 1]]})
                    i = i + k + 1
                    continue
            i += 1
    return sorted(out, key=lambda e: e["ini"])


def _mascara_fundo(shape, face):
    """Pontos do ambiente: tira a pessoa (rosto e corpo abaixo dele) da conta do movimento da câmera."""
    h, w = shape
    m = np.full((h, w), 255, np.uint8)
    if face:
        fx, fy, fh = face
        fw = fh * h / w
        x0, x1 = int((fx - 1.3 * fw) * w), int((fx + 1.3 * fw) * w)
        cv2.rectangle(m, (max(x0, 0), max(int((fy - 0.8 * fh) * h), 0)), (min(x1, w), h), 0, -1)
    return m


def ler_cena(video):
    """Lê o vídeo a 10 qps: gestos, rosto fino e movimento da câmera. Devolve o conteúdo de cena.json."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(MODELOS / "blaze_face_short_range.tflite")), min_detection_confidence=0.5))
    rec = None
    modelo_mao = MODELOS / "gesture_recognizer.task"
    if modelo_mao.exists():
        rec = vision.GestureRecognizer.create_from_options(vision.GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=str(modelo_mao)), running_mode=vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.55, min_tracking_confidence=0.5))
    cap = cv2.VideoCapture(str(video))
    n, maos, rostos, passos, alvos, assin = 0, [], [], [], [], []
    ant, face = None, None
    while True:
        ok = cap.grab()
        if not ok:
            break
        if n % PASSO:
            n += 1
            continue
        _, f = cap.retrieve()
        t = n / FPS
        h0, w0 = f.shape[:2]
        pq = cv2.resize(f, (320, int(320 * h0 / w0)))
        rgb = cv2.cvtColor(pq, cv2.COLOR_BGR2RGB)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        r = det.detect(img).detections
        if r:
            b = max(r, key=lambda d: d.bounding_box.width).bounding_box
            ph, pw = pq.shape[:2]
            face = ((b.origin_x + b.width / 2) / pw, (b.origin_y + b.height / 2) / ph, b.height / ph)
            kp = max(r, key=lambda d: d.bounding_box.width).keypoints  # olhos, nariz, boca, orelhas
            olho_x, olho_y = (kp[0].x + kp[1].x) / 2, (kp[0].y + kp[1].y) / 2
            esc = max(abs(kp[1].x - kp[0].x), 1e-3)
            # inclinação (cabeça para cima/baixo) e giro (para os lados), sem depender de onde a câmera está
            incl, giro = (kp[2].y - olho_y) * ph / max(b.height, 1), (kp[2].x - olho_x) / esc
            rostos.append([round(t, 2), *(round(v, 4) for v in face), round(incl, 4), round(giro, 4)])
        if rec is not None:
            res = rec.recognize_for_video(img, int(t * 1000))
            for k, lm in enumerate(res.hand_landmarks):
                g = res.gestures[k][0] if k < len(res.gestures) and res.gestures[k] else None
                rot = GESTOS.get(g.category_name) if g is not None and g.score >= 0.6 else None
                if rot is None and aponta_camera(lm):
                    rot = "aponta_camera"
                if rot:
                    ponto = lm[8] if rot in ("dedo_cima", "aponta_camera") else (lm[4] if rot.startswith("joinha") else lm[9])
                    maos.append((t, rot, ponto.x, ponto.y))
                alvo = alvo_do_dedo(lm)
                if alvo:
                    alvos.append((t, "aponta_objeto", *alvo))
        if n % (PASSO * 10) == 0:  # 1 vez por segundo: assinatura de cor do ambiente (grade 4x4 em Lab), para achar troca de cômodo
            lab = cv2.cvtColor(cv2.resize(pq, (4, 4), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB)
            assin.append([round(t, 2), *(int(v) for v in lab.reshape(-1))])
        cinza = cv2.cvtColor(pq, cv2.COLOR_BGR2GRAY)
        if ant is not None:
            pts = cv2.goodFeaturesToTrack(ant, 150, 0.01, 8, mask=_mascara_fundo(ant.shape, face))
            if pts is not None and len(pts) >= 12:
                nov, st, _ = cv2.calcOpticalFlowPyrLK(ant, cinza, pts, None)
                bons = st.ravel() == 1
                if bons.sum() >= 10:
                    M, _ = cv2.estimateAffinePartial2D(pts[bons], nov[bons], method=cv2.RANSAC, ransacReprojThreshold=2.0)
                    if M is not None:
                        ph, pw = cinza.shape
                        passos.append([round(t, 2), round(float(M[0, 2]) / pw, 4), round(float(M[1, 2]) / ph, 4)])
        ant = cinza
        n += 1
    cap.release()
    det.close()
    if rec is not None:
        rec.close()
    dur = n / FPS
    gestos = []
    for e in _juntar(sorted(maos), "tipo"):
        gestos.append(e)
    return {"gestos": gestos, "cabeca": cabeca(rostos), "camera": camera(passos, rostos, dur), "maos_lidas": rec is not None,
            "com_rosto": [r[0] for r in rostos], "apontar": _juntar(sorted(alvos), "tipo", gap=0.5, minimo=0.2),
            "assinaturas": assin}


def resumo_cena(cena):
    linhas = []
    for grupo in ("gestos", "cabeca", "camera"):
        for e in cena.get(grupo, []):
            linhas.append(f"#   {e['ini']:6.2f}–{e['fim']:6.2f}  {NOMES.get(e['tipo'], e['tipo'])}")
    if not cena.get("maos_lidas"):
        linhas.append("#   (sem o modelo de gestos em modelos/gesture_recognizer.task: rode o setup para ler as mãos)")
    return "# Cena (o que acontece na imagem):\n" + ("\n".join(linhas) if linhas else "#   nada marcante")


# ───────────────────────────── direção: da leitura ao EDL ─────────────────────────────
def _trilha(ev, a, b):
    tr = [p for p in ev["trilha"] if a - 0.2 <= p[0] <= b + 0.2]
    return tr or ev["trilha"][:1]


def _palavra_forte(palavras, a, b):
    from .diretor import STOP, norm
    ws = [w for w in palavras if a <= (w["ini"] + w["fim"]) / 2 < b and len(norm(w["t"])) >= 8 and norm(w["t"]) not in STOP]
    return max(ws, key=lambda w: len(norm(w["t"])), default=None)


def dirigir_cena(cena, palavras, segs, calmo=False):
    """Cada gesto, aceno e movimento de câmera dentro do que ficou no vídeo vira um elemento que acompanha o movimento
    ("seguir"), um zoom ou uma transição. Devolve {"elementos", "zooms", "transicoes": {id do segmento: tipo}}.
    calmo=True (marca de ritmo calmo) troca o tranco do zoom por aproximação suave."""
    def trecho(ev):  # o segmento que mais cobre o evento (gesto que começa numa pausa cortada ainda conta)
        sob = [(min(ev["fim"], s["fim"]) - max(ev["ini"], s["ini"]), s) for s in segs]
        sob = [x for x in sob if x[0] > 0.25]
        return max(sob, key=lambda x: x[0])[1] if sob else None
    els, zooms, trans, ultimo, ultima_luz = [], [], {}, -9.0, -99.0
    tr = np.array(cena.get("com_rosto", []) or [-1.0])
    camera_anda = [(c["ini"], c["fim"]) for c in cena.get("camera", []) if c["tipo"] in ("giro", "panoramica")]

    def rosto(a, b):  # fração do evento com o rosto na tela (gesto para a câmera, não mão mostrando um objeto)
        n = int(round((b - a) * FPS / PASSO)) or 1
        return float(np.sum((tr >= a) & (tr <= b))) / n
    eventos = sorted(cena.get("gestos", []) + cena.get("cabeca", []) + cena.get("camera", []), key=lambda e: e["ini"])
    for ev in eventos:
        s = trecho(ev)
        if s is None:
            continue
        a, b = max(ev["ini"], s["ini"]), min(ev["fim"], s["fim"] - 0.05)
        b = min(max(b, a + 0.8), s["fim"] - 0.05, a + 2.5)
        if b - a < 0.4:
            continue
        tp, novo = ev["tipo"], []
        if tp in GESTOS.values() or tp == "aponta_camera":
            if rosto(ev["ini"], ev["fim"]) < 0.5 and (calmo or tp not in ("mao_aberta", "dedo_cima")):
                continue  # mão mostrando algo do ambiente: só o círculo/brilho de "olha aqui", e nunca em marca calma
        if tp.startswith("aceno") and any(c0 < ev["fim"] and ev["ini"] < c1 for c0, c1 in camera_anda):
            continue  # a cabeça "virou" porque a câmera andou, não foi um aceno
        base = {"ini": round(a, 2), "fim": round(b, 2), "seguir": _trilha(ev, a, b), "_motivo": f"imagem: {NOMES.get(tp, tp)}"}
        if tp in ("dedo_cima", "vitoria", "rock"):
            novo.append(dict(base, tipo="efeito", nome="brilhos", raio=0.1, quantidade=8, dy=-0.02))
        elif tp == "aponta_camera":
            novo.append(dict(base, tipo="efeito", nome="ondas", raio=0.22))
            zooms.append({"ini": round(a, 2), "fim": round(min(a + 0.6, b), 2), "fator": 1.1 if calmo else 1.14,
                          "modo": "suave" if calmo else "punch"})
        elif tp == "mao_aberta":
            novo.append(dict(base, tipo="efeito", nome="circulo", largura=0.3, altura=0.3))
        elif tp in ("joinha", "aceno_sim"):
            novo.append(dict(base, tipo="efeito", nome="check", tamanho=0.13,
                             **({"dx": 0.22, "dy": -0.06} if tp == "aceno_sim" else {"dy": -0.09})))
        elif tp in ("joinha_baixo", "aceno_nao"):
            novo.append(dict(base, tipo="efeito", nome="xis", tamanho=0.13,
                             **({"dx": 0.22, "dy": -0.06} if tp == "aceno_nao" else {"dy": -0.09})))
        elif tp in ("giro", "panoramica"):
            prox = next((x for x in segs if ev["ini"] - 0.3 <= x["ini"] <= ev["fim"] + 0.3 and x is not segs[0]), None)
            if prox is not None and not prox.get("transicao") and tp == "giro":
                trans[prox["id"]] = "whip"
            if (tp == "giro" or ev["fim"] - ev["ini"] >= 1.0) and a - ultima_luz >= 10:  # luz no máximo a cada 10 s
                ultima_luz = a
                novo.append({"tipo": "efeito", "nome": "vazamento_luz", "ini": round(a, 2), "fim": round(b, 2),
                             "intensidade": 0.6, "direcao": ev.get("lado", "direita"), "_motivo": base["_motivo"]})
            w = _palavra_forte(palavras, a - 0.3, b + 0.3)
            if w is not None and tp == "giro":  # a palavra dita no giro fica "grudada" na parede e anda com a câmera
                novo.append(dict(base, tipo="destaque", texto=w["t"].strip(".,!?;:").capitalize(), tam=46, som=False))
        elif tp == "afasta":
            zooms.append({"ini": round(a, 2), "fim": round(b, 2), "fator": round(min(1.18, 1 + (1 - ev.get("fator", 0.7))), 2),
                          "modo": "abre"})
        for e in novo:
            if e["ini"] - ultimo < 0.8 and e["nome" if "nome" in e else "tipo"] != "vazamento_luz":
                continue
            els.append(e)
            ultimo = e["fim"]
    return {"elementos": els, "zooms": zooms, "transicoes": trans}


def _janela(e, palavras):
    """Início e fim (fonte) de um elemento, com tempos ou ancorado na fala ("na"/"ate")."""
    if "ini" in e:
        return e["ini"], e.get("fim", e["ini"] + 2)
    if "na" not in e or not palavras:
        return -1, -1
    from .diretor import _tempo_na
    a = _tempo_na(e, palavras)
    b = _tempo_na({"na": e["ate"]}, [w for w in palavras if w["ini"] >= a]) if e.get("ate") else -1
    return a, (b + 0.5 if b >= 0 else a + 2.5)


def aplicar_cena(edl, plano, palavras=None):
    """Junta a direção da cena ao rascunho sem apagar nem cobrir o que já está lá (o que o diretor da fala ou o editor
    puseram ganha: texto da cena não entra por cima de outro texto)."""
    for s in edl["segmentos"]:
        if s["id"] in plano["transicoes"] and not s.get("transicao"):
            s["transicao"] = plano["transicoes"][s["id"]]
    edl["zooms"] = sorted(edl.get("zooms", []) + plano["zooms"], key=lambda z: z["ini"])
    texto = lambda e: e.get("tipo") in ("titulo", "destaque") or e.get("tipo") not in ("efeito", "leo", "objeto3d", "som")
    luz = lambda e: e.get("tipo") == "efeito" and e.get("nome") in ("vazamento_luz", "flash", "grao", "vinheta", "reflexo")
    # texto não cobre texto; marcação (brilho, círculo, check) não cobre outra marcação nem o Leo; luz passa por baixo de tudo
    classe = lambda e: "luz" if luz(e) else ("texto" if texto(e) else "marca")
    ocupado = [(classe(e), *_janela(e, palavras)) for e in edl.get("elementos", []) if e.get("tipo") != "som"]
    novos = [{k: v for k, v in e.items() if not k.startswith("_")} for e in plano["elementos"]
             if classe(e) == "luz" or not any(c == classe(e) and a < e["fim"] and e["ini"] < b for c, a, b in ocupado)]
    edl["elementos"] = edl.get("elementos", []) + novos
    return edl


# ───────────────────────────── rastreio de um ponto do ambiente ("fixar") ─────────────────────────────
def rastrear_ponto(video, t0, x, y, a, b, largura=360):
    """Trilha [[t, x, y]] (fonte, 0 a 1) de um ponto do ambiente (um objeto na estante, a porta) entre a e b, partindo
    do instante t0 em (x, y). Fluxo óptico de uma pequena nuvem de pontos ao redor, para frente e para trás de t0; se o
    ponto se perde (sai da tela), fica no último lugar conhecido."""
    cap = cv2.VideoCapture(str(video))
    i_a, i_b, i_0 = (max(int(round(v * FPS)), 0) for v in (a, b, t0))
    i_0 = min(max(i_0, i_a), i_b)
    cap.set(cv2.CAP_PROP_POS_FRAMES, i_a)
    quadros = []
    for _ in range(i_a, i_b + 1):
        ok, f = cap.read()
        if not ok:
            break
        h0, w0 = f.shape[:2]
        quadros.append(cv2.cvtColor(cv2.resize(f, (largura, int(largura * h0 / w0))), cv2.COLOR_BGR2GRAY))
    cap.release()
    if not quadros:
        return [[round(t0, 3), x, y]]
    ph, pw = quadros[0].shape
    k0 = min(i_0 - i_a, len(quadros) - 1)
    r = 6
    nuvem = np.float32([[x * pw + dx, y * ph + dy] for dx in (-r, 0, r) for dy in (-r, 0, r)]).reshape(-1, 1, 2)
    pos = {k0: (x, y)}
    lk = {"winSize": (31, 31), "maxLevel": 3, "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)}
    for passo in (1, -1):
        pts, k = nuvem.copy(), k0
        while 0 <= k + passo < len(quadros):
            nov, st, _ = cv2.calcOpticalFlowPyrLK(quadros[k], quadros[k + passo], pts, None, **lk)
            bons = st.ravel() == 1
            if bons.sum() < 3:
                break
            centro = np.median(nov[bons].reshape(-1, 2), axis=0)
            if not (0 <= centro[0] < pw and 0 <= centro[1] < ph):
                break
            pts = nov[bons].reshape(-1, 1, 2)
            k += passo
            pos[k] = (float(centro[0] / pw), float(centro[1] / ph))
    return [[round((i_a + k) / FPS, 3), round(px, 4), round(py, 4)] for k, (px, py) in sorted(pos.items())]


DICA_TOUR = ("# Tour: a câmera anda pelo ambiente em {p}% do vídeo. Roteiro de documentário: gancho na frase mais forte, "
             "capítulos por cômodo e rótulo editorial preso a cada coisa que ele nomeia (já sugeridos abaixo: confira o título "
             "de cada capítulo e o ponto de cada rótulo na prévia), corte as caminhadas mudas e mire 45 a 60 s. "
             "A luz entre cômodos já sai igualada (cor.igualar_luz).")


def tour_pela_casa(cena, dur):
    """Fração do vídeo com a câmera andando pelo ambiente (giro, panorâmica, passeio). Devolve a fração se passar de 25%."""
    mov = sum(c["fim"] - c["ini"] for c in cena.get("camera", []) if c.get("tipo") in ("giro", "panoramica", "passeio", "afasta"))
    frac = mov / max(dur, 1e-6)
    return frac if frac >= 0.25 else 0.0
