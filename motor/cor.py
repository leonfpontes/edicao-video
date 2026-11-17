"""Correção de cor por LUT (contraste, calor), saturação e nitidez."""
import cv2
import numpy as np


def lut_cor(c):
    x = np.arange(256, dtype=np.float32)
    y = (x - 128) * c.get("contraste", 1.0) + 128
    q = c.get("calor", 0.0)
    b = np.clip(y * (1 - q), 0, 255)
    r = np.clip(y * (1 + q), 0, 255)
    return np.stack([b.astype(np.uint8), np.clip(y, 0, 255).astype(np.uint8), r.astype(np.uint8)], axis=1)[None]


def aplicar_cor(f, luts, c):
    if not isinstance(luts, np.ndarray):  # as três curvas numa LUT só de 3 canais (uma passada no quadro)
        luts = np.stack(luts, axis=1)[None]
    f = cv2.LUT(f, luts)
    s = c.get("saturacao", 1.0)
    if abs(s - 1) > 0.01:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = cv2.LUT(hsv[..., 1], np.clip(np.arange(256) * s, 0, 255).astype(np.uint8))
        f = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    n = c.get("nitidez", 0)
    if n > 0:
        f = cv2.addWeighted(f, 1 + n, cv2.GaussianBlur(f, (0, 0), 2), -n, 0)
    return f



# ───────────────────────────── LUT 3D (.cube) ─────────────────────────────
def ler_cube(caminho):
    """Lê um .cube (Adobe/Resolve): devolve (N, N, N, 3) em RGB 0..1, indexado [b][g][r] (o r varia mais rápido)."""
    n, dados, dmin, dmax = None, [], np.zeros(3), np.ones(3)
    for linha in open(caminho, encoding="utf-8", errors="ignore"):
        t = linha.strip()
        if not t or t.startswith("#") or t.startswith("TITLE"):
            continue
        p = t.split()
        if p[0] == "LUT_3D_SIZE":
            n = int(p[1])
        elif p[0] == "DOMAIN_MIN":
            dmin = np.array(p[1:4], float)
        elif p[0] == "DOMAIN_MAX":
            dmax = np.array(p[1:4], float)
        elif p[0] == "LUT_1D_SIZE":
            raise ValueError("só LUT 3D (.cube com LUT_3D_SIZE)")
        else:
            try:
                dados.append([float(x) for x in p[:3]])
            except ValueError:
                continue
    if not n or len(dados) != n ** 3:
        raise ValueError(f"{caminho}: .cube incompleto ({len(dados)} de {(n or 0) ** 3} linhas)")
    lut = np.array(dados, np.float32).reshape(n, n, n, 3)
    return (lut - dmin) / np.maximum(dmax - dmin, 1e-6)


def tabela_lut3d(lut, intensidade=1.0, bits=7):
    """Tabela pronta para aplicar: 2^bits níveis por canal (128 por padrão), interpolada (trilinear) do .cube,
    misturada com a imagem original pela intensidade. Saída: (2^bits)^3 × 3 em BGR uint8."""
    n = lut.shape[0]
    q = 2 ** bits
    v = (np.arange(q, dtype=np.float32) + 0.5) / q
    b, g, r = np.meshgrid(v, v, v, indexing="ij")
    coord = np.stack([b, g, r], -1).reshape(-1, 3) * (n - 1)
    i0 = np.floor(coord).astype(np.int32).clip(0, n - 2)
    fr = coord - i0
    out = np.zeros((coord.shape[0], 3), np.float32)
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                w = ((fr[:, 0] if db else 1 - fr[:, 0]) * (fr[:, 1] if dg else 1 - fr[:, 1]) * (fr[:, 2] if dr else 1 - fr[:, 2]))
                out += w[:, None] * lut[i0[:, 0] + db, i0[:, 1] + dg, i0[:, 2] + dr]
    orig = np.stack([r, g, b], -1).reshape(-1, 3)  # RGB da própria entrada
    out = orig + (out - orig) * intensidade
    return (out[:, ::-1] * 255).clip(0, 255).astype(np.uint8)  # RGB -> BGR


def aplicar_lut3d(f, tabela, bits=7):
    s = 8 - bits
    b, g, r = (c.astype(np.uint32) >> s for c in cv2.split(f))
    return tabela[(b << (2 * bits)) | (g << bits) | r]


# ───────────────────────────── pele ─────────────────────────────
def mascara_pele(f):
    """Máscara 0..1 (H×W×1) da pele, por faixa em YCrCb, calculada em 1/4 da resolução e suavizada."""
    h, w = f.shape[:2]
    pq = cv2.resize(f, (max(w // 4, 1), max(h // 4, 1)), interpolation=cv2.INTER_AREA)
    ycc = cv2.cvtColor(pq, cv2.COLOR_BGR2YCrCb)
    m = cv2.inRange(ycc, (40, 135, 85), (250, 178, 135))
    m = cv2.GaussianBlur(m, (0, 0), 3)
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)[..., None] * (1 / 255)


def proteger_pele(original, tratado, forca=0.6):
    """Devolve a pele perto da cor original (o look não deixa o rosto azul, verde ou acinzentado)."""
    m = mascara_pele(original)[..., 0] * forca
    return cv2.blendLinear(original, tratado, m, 1 - m)


# ───────────────────────────── igualar clipes ─────────────────────────────
def estatisticas_cor(video, ini, fim, amostras=8):
    """Média e desvio por canal (BGR) de quadros espalhados em [ini, fim)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    px = []
    for k in range(amostras):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((ini + (fim - ini) * (k + 0.5) / amostras) * fps))
        ok, f = cap.read()
        if ok:
            px.append(cv2.resize(f, (96, 170), interpolation=cv2.INTER_AREA).reshape(-1, 3))
    cap.release()
    if not px:
        return None
    x = np.concatenate(px).astype(np.float32)
    return x.mean(0).tolist(), x.std(0).tolist()


def igualar_clipes(video, clipes):
    """Correção por clipe para todos ficarem com a cor e a exposição do conjunto (vídeos gravados em momentos e
    lugares diferentes). Devolve [{"ganho": [b, g, r], "desloc": [b, g, r]}] por clipe, com ganho limitado."""
    est = [estatisticas_cor(video, c["ini"], c["fim"]) for c in clipes]
    validos = [e for e in est if e]
    if len(validos) < 2:
        return None
    alvo_m = np.median([e[0] for e in validos], 0)
    alvo_s = np.median([e[1] for e in validos], 0)
    out = []
    for e in est:
        if not e:
            out.append({"ganho": [1, 1, 1], "desloc": [0, 0, 0]})
            continue
        m, s = np.array(e[0]), np.array(e[1])
        ganho = np.clip(alvo_s / np.maximum(s, 1), 0.8, 1.25)
        desloc = np.clip(alvo_m - m * ganho, -40, 40)
        out.append({"ganho": ganho.round(4).tolist(), "desloc": desloc.round(2).tolist()})
    return out


def lut_clipe(c):
    x = np.arange(256, dtype=np.float32)[:, None]
    return (x * np.array(c["ganho"], np.float32) + np.array(c["desloc"], np.float32)).clip(0, 255).astype(np.uint8)[None]
