"""Pausas pelo áudio: acerta o começo e o fim de cada palavra do Whisper.

O Whisper estica uma palavra até a seguinte quando há pausa ("algumas" durando 2,7 s) ou a faz começar antes da hora,
depois de um silêncio. Com isso a pausa some da transcrição e o rascunho não corta: a caminhada muda fica no vídeo.

Aqui o volume do áudio (dB RMS a cada 10 ms) decide. Numa palavra comprida demais para o número de letras, o trecho mais
longo abaixo do limiar de silêncio, encostado no fim (ou no começo), sai da palavra; no meio, vira o campo "pausa"
[ini, fim] e o rascunho corta esse trecho sem mexer nos tempos da palavra. O limiar é local: 14 dB abaixo do pico
da palavra, mas nunca abaixo do ruído de fundo dos 4 s em volta mais 5 dB.
"""
import subprocess

import numpy as np

PASSO = 0.01  # 10 ms por amostra de volume


def volume_db(video):
    """dB RMS a cada 10 ms (suavizado em 50 ms). None se o vídeo não tiver áudio."""
    try:
        pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    h = int(16000 * PASSO)
    n = len(x) // h
    if n < 10:
        return None
    db = 10 * np.log10(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1) + 1e-10)
    return np.convolve(db, np.ones(5) / 5, "same")


def _letras(t):
    return sum(c.isalpha() for c in t)


def _corrida_baixa(baixo):
    """(início, fim) da maior sequência de True; (0, 0) se não houver."""
    melhor, ini = (0, 0), None
    for k, v in enumerate(list(baixo) + [False]):
        if v and ini is None:
            ini = k
        elif not v and ini is not None:
            if k - ini > melhor[1] - melhor[0]:
                melhor = (ini, k)
            ini = None
    return melhor


def aparar_palavras(palavras, db, passo=PASSO, minimo=0.2):
    """Devolve (palavras acertadas, quantas mudaram). Não mexe em palavra de duração normal nem no cache do Whisper."""
    if db is None or not palavras:
        return palavras, 0
    out, n = [], 0
    for w in palavras:
        w = dict(w)
        dur = w["fim"] - w["ini"]
        esperado = max(0.35, 0.18 + 0.085 * _letras(w["t"]))
        a, b = int(w["ini"] / passo), min(int(w["fim"] / passo), len(db))
        if dur > esperado and b - a > 4:
            trecho = db[a:b]
            viz = db[max(a - int(2 / passo), 0):min(b + int(2 / passo), len(db))]
            limiar = max(float(trecho.max()) - 14, float(np.percentile(viz, 5)) + 5)
            i, j = _corrida_baixa(trecho < limiar)
            if (j - i) * passo >= minimo:
                if j >= len(trecho) - int(0.2 / passo) and i * passo >= 0.1:  # silêncio no fim: a palavra acaba antes
                    w["fim"] = round(w["ini"] + i * passo + 0.04, 3)
                    n += 1
                elif i <= int(0.06 / passo) and (len(trecho) - j) * passo >= 0.1:  # silêncio no começo: começa depois
                    w["ini"] = round(w["ini"] + j * passo - 0.04, 3)
                    n += 1
                elif (j - i) * passo >= 0.4:  # silêncio no meio: não dá para saber de que lado está a palavra; o corte pula a pausa
                    w["pausa"] = [round(w["ini"] + i * passo + 0.04, 3), round(w["ini"] + j * passo - 0.04, 3)]
                    n += 1
        out.append(w)
    return out, n
