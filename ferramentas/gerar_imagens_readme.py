"""Gera as imagens do README (docs/img/) com o próprio motor: nada é desenhado à mão.

  .venv/bin/python ferramentas/gerar_imagens_readme.py

Cada quadro sai da marca ativa no momento, com as cores, fontes, fundo e vinheta dela. Rode de novo
quando o visual de uma marca mudar.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor import marca  # noqa: E402
from motor.bibliotecas import itens, objeto_3d  # noqa: E402
from motor.config import BIBLIOTECA, FONTES_DIR, RAIZ  # noqa: E402
from motor.efeitos import criar_efeito  # noqa: E402
from motor.fundo import FundoMarca  # noqa: E402
from motor.graficos import Cartao, blend, pil2np, sombra  # noqa: E402
from motor.legendas import Legendas  # noqa: E402
from motor.vinhetas import quadro_intro  # noqa: E402

SAIDA = RAIZ / "docs" / "img"
W, H = 1080, 1920

# texto de exemplo de cada marca, no tom dela
VITRINE = {
    "pontes_brain": {"titulo": "Por que seu produto trava antes de começar?", "destaque": "PDCA em 4 gates",
                     "legenda": "nunca é tecnologia", "enfase": ["tecnologia"], "objeto": "foguete",
                     "efeito": {"nome": "brilhos", "x": 0.78, "y": 0.47}},
    "girahub": {"titulo": "A senha da gira, sem fila no portão", "destaque": "Check-in em 3 segundos",
                "legenda": "na sua vez", "enfase": ["vez"], "objeto": "ticket",
                "efeito": {"nome": "confete", "x": 0.5, "y": 0.45}},
    "leopontesrp": {"titulo": "Domingo de sol", "destaque": "Aprendendo a viver a vida",
                    "legenda": "devagar e sempre", "enfase": ["sempre"], "objeto": "sol",
                    "efeito": {"nome": "vazamento_luz"}},
}
MARCAS = list(VITRINE)


def fonte(peso, tam):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTES_DIR / f"Roboto-{peso}.ttf"), tam)


def quadro_vitrine(mid, t=1.4):
    """Um quadro "editado" da marca: fundo, título, destaque, objeto 3D, efeito, legenda e marca d'água."""
    v = VITRINE[mid]
    fundo = FundoMarca(W, H)
    f = fundo.quadro(4.0)
    img = Cartao(v["titulo"], W * 0.86, "titulo").render(t, 9)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.16)
    obj = Image.open(objeto_3d(v["objeto"])[0]).convert("RGBA")
    obj = obj.crop(obj.getbbox())
    obj.thumbnail((int(W * 0.36), int(W * 0.36)), Image.LANCZOS)
    o, _ = sombra(pil2np(obj), 22, 0.5, (0, 18))
    blend(f, o, W / 2 - o.shape[1] / 2, H * 0.40)
    img = Cartao(v["destaque"], W * 0.8, "destaque").render(t, 9)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.64)
    pal = [{"t": w, "ini": 0.3 * i, "fim": 0.3 * i + 0.28, "p": 1} for i, w in enumerate(v["legenda"].split())]
    lg = Legendas(pal, {"enfase": v["enfase"]}, W, H, [(0, 99)])
    img = lg.render(0, 0.3 * (len(pal) - 1) + 0.26)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.76)
    ef = criar_efeito(dict({"tipo": "efeito"}, **v["efeito"]), W, H, 1)
    ef.desenhar(f, 0.8, 1.2)
    if marca.tem_logo():
        m, _ = sombra(pil2np(marca.logo_marca(marca.CFG.get("marca_dagua_alt", 80))), 6, 0.5, (0, 3))
        blend(f, m, W - m.shape[1] - 30, H * marca.CFG.get("marca_dagua_y", 0.115), 0.85)
    return f


def celular(quadro, larg=360, raio=44, borda=10):
    """Quadro BGR dentro de uma moldura de celular (RGBA)."""
    h = int(larg * 16 / 9)
    tela = Image.fromarray(cv2.cvtColor(cv2.resize(quadro, (larg, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
    m = Image.new("L", (larg, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, larg - 1, h - 1], raio, fill=255)
    cel = Image.new("RGBA", (larg + 2 * borda, h + 2 * borda), (0, 0, 0, 0))
    ImageDraw.Draw(cel).rounded_rectangle([0, 0, cel.width - 1, cel.height - 1], raio + borda, fill=(12, 12, 14, 255))
    cel.paste(tela, (borda, borda), m)
    return cel


def colar_com_sombra(base, im, xy, raio=30, opac=110):
    s = Image.new("RGBA", base.size, (0, 0, 0, 0))
    a = im.split()[3].point(lambda v: opac if v else 0)
    s.paste((0, 0, 0, 255), (xy[0], xy[1] + 24), a)
    base.alpha_composite(s.filter(ImageFilter.GaussianBlur(raio)))
    base.alpha_composite(im, xy)


def gradiente(w, h, c1, c2):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.clip(np.sqrt(((xx - w * 0.72) / w) ** 2 + ((yy - h * 0.45) / h) ** 2) * 1.6, 0, 1)[..., None]
    arr = np.array(c2, np.float32) * (1 - r) + np.array(c1, np.float32) * r
    return Image.fromarray(arr.astype(np.uint8)).convert("RGBA")


def capa(vitrines):
    marca.ativar("pontes_brain")
    c = marca.CORES
    cw, ch = 1600, 800
    im = gradiente(cw, ch, tuple(int(v * 0.55) for v in c["marinho"]), c["marinho_2"])
    d = ImageDraw.Draw(im)
    logo = Image.open(marca.arquivo_marca("logo.png")).convert("RGBA")
    logo.thumbnail((72, 72), Image.LANCZOS)
    im.alpha_composite(logo, (90, 92))
    d.text((90, 210), "Editor de vídeo", font=fonte("Black", 76), fill=c["papel_2"])
    d.text((90, 296), "multimarca", font=fonte("Black", 76), fill=c["champanhe"])
    sub = ["Reels e Stories editados por um agente de IA,", "com a identidade de cada marca e zero mistura.",
           "Local, gratuito e testado a cada mudança."]
    for i, s in enumerate(sub):
        d.text((92, 410 + i * 40), s, font=fonte("Regular", 30), fill=c["nevoa"])
    x = 92
    for txt in ("3D", "Música licenciada", "Efeitos", "Guarda de marca"):
        f = fonte("Bold", 22)
        w = int(f.getlength(txt)) + 32
        d.rounded_rectangle([x, 560, x + w, 600], 10, outline=c["champanhe"], width=2)
        d.text((x + w / 2, 580), txt, font=f, fill=c["champanhe"], anchor="mm")
        x += w + 12
    d.text((92, 690), "@pontes_brain  ·  GiraHub  ·  @leopontesrp", font=fonte("Bold", 24), fill=c["papel"])
    cels = [celular(vitrines[m], 280) for m in ("girahub", "pontes_brain", "leopontesrp")]
    pos = [(800, 150), (1035, 80), (1270, 150)]
    for cel, xy, ang in zip([cels[0], cels[2]], [pos[0], pos[2]], (4, -4)):
        r = cel.rotate(ang, Image.BICUBIC, expand=True)
        colar_com_sombra(im, r, (xy[0] - (r.width - cel.width) // 2, xy[1]))
    colar_com_sombra(im, cels[1], pos[1])
    return im.crop((0, 0, cw, ch))


def faixa_marcas(vitrines):
    """As três marcas lado a lado: vinheta (quando há) e um quadro editado."""
    cel_w, gap = 260, 28
    quadros = []
    for mid in MARCAS:
        marca.ativar(mid)
        fundo = FundoMarca(W, H)
        if marca.padrao({}, "intro", {}).get("ativo", True) is False or not marca.CFG.get("logo"):
            # marca sem vinheta (Instagram pessoal): um quadro de vlog com a moldura REC e o contador
            q1 = fundo.quadro(2.0)
            criar_efeito({"tipo": "efeito", "nome": "moldura_rec"}, W, H).desenhar(q1, 1.0, 3.0)
            criar_efeito({"tipo": "efeito", "nome": "contador", "ate": 10, "sufixo": " km", "y": 0.45}, W, H).desenhar(q1, 2.0, 2.0)
        else:
            q1 = quadro_intro(W, H, 1.95, fundo, {}, 2.2)
        quadros.append((mid, marca.CFG["nome"].split(" (")[0], [q1, vitrines[mid]]))
    larg = len(MARCAS) * (2 * cel_w + gap) + (len(MARCAS) - 1) * 70 + 120
    alt = int(cel_w * 16 / 9) + 160
    im = Image.new("RGBA", (larg, alt), (18, 18, 22, 255))
    d = ImageDraw.Draw(im)
    x = 60
    for mid, nome, qs in quadros:
        for i, q in enumerate(qs):
            im.alpha_composite(celular(q, cel_w - 12, 30, 6), (x + i * (cel_w + gap), 40))
        d.text((x + cel_w + gap / 2, alt - 70), nome, font=fonte("Bold", 26), fill=(240, 240, 240), anchor="mm")
        d.text((x + cel_w + gap / 2, alt - 36), f"--marca {mid}", font=fonte("Regular", 20), fill=(160, 160, 170), anchor="mm")
        x += 2 * cel_w + gap + 70
    return im


def galeria_3d(lado=150, col=12, linhas=5):
    lst = itens("3d")
    renders = [it for it in lst if it["tipo"] == "render"]
    logos = [it for it in lst if it["tipo"] == "extrusao"]
    escolha = renders[: col * (linhas - 1)] + logos[:col]
    im = Image.new("RGBA", (col * lado, linhas * lado), (20, 20, 24, 255))
    for i, it in enumerate(escolha):
        o = Image.open(BIBLIOTECA / "3d" / it["arquivo"]).convert("RGBA")
        o = o.crop(o.getbbox())
        o.thumbnail((lado - 34, lado - 34), Image.LANCZOS)
        cx, cy = (i % col) * lado + lado // 2, (i // col) * lado + lado // 2
        im.alpha_composite(o, (cx - o.width // 2, cy - o.height // 2))
    return im


def gif_vinheta(mid, saida, larg=270, fps=15, dur=2.2):
    marca.ativar(mid)
    fundo = FundoMarca(W, H)
    cache = {}
    fr = []
    for i in range(int(dur * fps) + 8):
        t = min(i / fps, dur - 0.02)
        q = quadro_intro(W, H, t, fundo, cache, dur)
        q = cv2.resize(q, (larg, int(larg * 16 / 9)), interpolation=cv2.INTER_AREA)
        fr.append(Image.fromarray(cv2.cvtColor(q, cv2.COLOR_BGR2RGB)).quantize(96, Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    fr[0].save(saida, save_all=True, append_images=fr[1:], duration=int(1000 / fps), loop=0, optimize=True)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    vitrines = {}
    for mid in MARCAS:
        marca.ativar(mid)
        vitrines[mid] = quadro_vitrine(mid)
        cv2.imwrite(str(SAIDA / f"vitrine-{mid}.jpg"), cv2.resize(vitrines[mid], (540, 960), interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])
    capa(vitrines).convert("RGB").save(SAIDA / "capa.png", optimize=True)
    faixa_marcas(vitrines).convert("RGB").save(SAIDA / "marcas.png", optimize=True)
    galeria_3d().convert("RGB").save(SAIDA / "biblioteca-3d.png", optimize=True)
    from motor.comandos import previa_efeitos
    marca.ativar("pontes_brain")
    ef = previa_efeitos()
    cv2.imwrite(str(SAIDA / "biblioteca-efeitos.jpg"), cv2.resize(ef, (ef.shape[1] * 2 // 3, ef.shape[0] * 2 // 3)),
                [cv2.IMWRITE_JPEG_QUALITY, 86])
    gif_vinheta("pontes_brain", SAIDA / "vinheta-pontes_brain.gif")
    gif_vinheta("girahub", SAIDA / "vinheta-girahub.gif")
    for p in sorted(SAIDA.iterdir()):
        print(f"{p.relative_to(RAIZ)}  {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
