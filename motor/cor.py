"""Correção de cor por LUT (contraste, calor), saturação e nitidez."""
import cv2
import numpy as np


def lut_cor(c):
    x = np.arange(256, dtype=np.float32)
    y = (x - 128) * c.get("contraste", 1.0) + 128
    q = c.get("calor", 0.0)
    b = np.clip(y * (1 - q), 0, 255)
    r = np.clip(y * (1 + q), 0, 255)
    return [b.astype(np.uint8), np.clip(y, 0, 255).astype(np.uint8), r.astype(np.uint8)]


def aplicar_cor(f, luts, c):
    f = cv2.merge([cv2.LUT(ch, l) for ch, l in zip(cv2.split(f), luts)])
    s = c.get("saturacao", 1.0)
    if abs(s - 1) > 0.01:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = cv2.LUT(hsv[..., 1], np.clip(np.arange(256) * s, 0, 255).astype(np.uint8))
        f = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    n = c.get("nitidez", 0)
    if n > 0:
        f = cv2.addWeighted(f, 1 + n, cv2.GaussianBlur(f, (0, 0), 2), -n, 0)
    return f

