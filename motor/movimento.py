"""Curvas de movimento (easing) usadas em todas as animações."""
import math


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):  # cúbica: rápida no começo, pousa macio
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp01(x)
    return x ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.70158):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def mola(x, amort=7.0, freq=11.0):
    """Mola amortecida: passa um pouco do alvo e assenta (0→1)."""
    if x <= 0:
        return 0.0
    return 1 - math.exp(-amort * x) * math.cos(freq * x)


def lerp(a, b, p):
    return a + (b - a) * p

