#!/usr/bin/env python3
"""Desenha os objetos 3D próprios do @pontes_brain (identidade: ficam em marcas/pontes_brain/3d/, nunca na biblioteca).

Uso (da raiz do repositório): .venv/bin/python ferramentas/gerar_3d_pontes_brain.py

O motor extruda cada PNG (espessura, luz e reflexo). Saem na paleta Papel & Marinho, em Roboto:
- g1.png a g4.png: placas dos 4 gates (G1 Intake · Plan, G2 Business case · Plan, G3 Delivery · Do, G4 Benefits · Check · Act);
- pdca.png: o ciclo PDCA (quatro setas em anel com as letras), para "ciclo", "melhoria contínua", "metodologia".
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
MARCA = RAIZ / "marcas" / "pontes_brain"
FONTES = RAIZ / "biblioteca" / "fontes"
LADO = 1024
GATES = [("G1", "INTAKE", "PLAN"), ("G2", "BUSINESS CASE", "PLAN"), ("G3", "DELIVERY", "DO"), ("G4", "BENEFITS", "CHECK · ACT")]


def cor(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def placa(sigla, nome, fase, c):
    im = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = 40
    d.rounded_rectangle([m, m, LADO - m, LADO - m], 96, fill=cor(c["marinho"]), outline=cor(c["champanhe"]), width=26)
    d.rounded_rectangle([m + 60, m + 60, LADO - m - 60, LADO - m - 60], 60, outline=cor(c["marinho_2"]), width=8)
    f1 = ImageFont.truetype(str(FONTES / "Roboto-Black.ttf"), 400)
    f2 = ImageFont.truetype(str(FONTES / "Roboto-Bold.ttf"), 78)
    f3 = ImageFont.truetype(str(FONTES / "Roboto-Black.ttf"), 64)
    d.text((LADO / 2, LADO * 0.43), sigla, font=f1, fill=cor(c["papel_2"]), anchor="mm")
    while f2.getlength(nome) > LADO * 0.7:
        f2 = ImageFont.truetype(str(FONTES / "Roboto-Bold.ttf"), f2.size - 4)
    d.text((LADO / 2, LADO * 0.70), nome, font=f2, fill=cor(c["champanhe"]), anchor="mm")
    d.text((LADO / 2, LADO * 0.81), fase, font=f3, fill=cor(c["nevoa"]), anchor="mm")
    return im


def pdca(c):
    s = 2  # desenha em 2x e reduz: arcos lisos
    L = LADO * s
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = L / 2
    r_ext, esp = L * 0.44, L * 0.13
    cores = [c["champanhe"], c["papel_2"], c["champanhe"], c["papel_2"]]
    f = ImageFont.truetype(str(FONTES / "Roboto-Black.ttf"), int(L * 0.12))
    for k, letra in enumerate("PDCA"):
        a0, a1 = -90 + k * 90 + 6, -90 + (k + 1) * 90 - 14
        d.arc([cx - r_ext, cy - r_ext, cx + r_ext, cy + r_ext], a0, a1, fill=cor(cores[k]), width=int(esp))
        r_mid = r_ext - esp / 2
        ang = math.radians(a1)
        px, py = cx + r_mid * math.cos(ang), cy + r_mid * math.sin(ang)
        tx, ty = -math.sin(ang), math.cos(ang)  # tangente no sentido horário
        nx, ny = math.cos(ang), math.sin(ang)
        ponta = (px + tx * esp * 0.9, py + ty * esp * 0.9)
        base1 = (px + nx * esp * 0.85, py + ny * esp * 0.85)
        base2 = (px - nx * esp * 0.85, py - ny * esp * 0.85)
        d.polygon([ponta, base1, base2], fill=cor(cores[k]))
        am = math.radians(-90 + k * 90 + 45)
        rl = r_ext - esp - L * 0.11
        d.text((cx + rl * math.cos(am), cy + rl * math.sin(am)), letra, font=f, fill=cor(c["marinho"]), anchor="mm",
               stroke_width=int(L * 0.012), stroke_fill=cor(cores[k]))
    d.ellipse([cx - L * 0.06, cy - L * 0.06, cx + L * 0.06, cy + L * 0.06], fill=cor(c["champanhe"]))
    return im.resize((LADO, LADO), Image.LANCZOS)


def main():
    c = json.loads((MARCA / "marca.json").read_text())["cores"]
    (MARCA / "3d").mkdir(exist_ok=True)
    for i, (sigla, nome, fase) in enumerate(GATES, 1):
        placa(sigla, nome, fase, c).save(MARCA / "3d" / f"g{i}.png")
    pdca(c).save(MARCA / "3d" / "pdca.png")
    print("gravados: g1.png a g4.png e pdca.png em", MARCA / "3d")


if __name__ == "__main__":
    main()
