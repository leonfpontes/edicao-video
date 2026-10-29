"""`testar`: regressão visual (folha de cada marca), isolamento entre marcas e render ponta a ponta com medição de áudio."""
import json
import subprocess
import sys

import cv2
import numpy as np

from .analisar import rascunho_edl
from .audio import medir_audio
from .config import RAIZ, TESTES
from .fundo import FundoMarca
from .graficos import Cartao, blend, pil2np, sombra
from .guarda import conferir_edl, termos_de_outras
from .legendas import Legendas
from .marca import CFG, ErroDeMarca, ativar, ler_marca, listar_marcas, logo_marca, pasta_marca, politica_musica, tem_logo
from .util import sh
from .vinhetas import cartao_cta, quadro_intro


def folha_marca(W=1080, H=1920):
    """Folha de conferência da marca ativa: vinheta em 5 instantes, fundo, CTA e um quadro com título,
    destaque, legenda e marca d'água. Determinística (serve de referência para o teste)."""
    fundo = FundoMarca(W, H)
    cache, cc = {}, {}
    fr = [quadro_intro(W, H, t, fundo, cache, 2.2) for t in (0.3, 0.7, 1.0, 1.4, 1.95)]
    fr.append(fundo.quadro(3.0))
    if CFG.get("cta"):
        cta = dict({"ativo": True, "duracao": 3.5}, **CFG["cta"])
        fr += [cartao_cta(cta, W, H, t, fundo, cc) for t in (0.6, 2.0)]
    else:  # marca sem CTA: quadros vazios no lugar
        fr += [np.zeros((H, W, 3), np.uint8)] * 2
    f = fundo.quadro(5.0)
    img = Cartao("Título de teste da marca", W * 0.86, "titulo").render(1.2, 9)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.18)
    img = Cartao("Destaque", W * 0.8, "destaque").render(1.2, 9)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.32)
    pal = [{"t": w, "ini": 0.3 * i, "fim": 0.3 * i + 0.28, "p": 1} for i, w in enumerate("legenda palavra por palavra".split())]
    lg = Legendas(pal, {"enfase": ["palavra"]}, W, H, [(0, 99)])
    img = lg.render(0, 0.35)
    blend(f, img, W / 2 - img.shape[1] / 2, H * 0.68)
    if tem_logo():
        m, _ = sombra(pil2np(logo_marca(CFG.get("marca_dagua_alt", 80))), 6, 0.5, (0, 3))
        blend(f, m, W - m.shape[1] - 30, H * CFG.get("marca_dagua_y", 0.115), 0.85)
    fr.append(f)
    th = [cv2.resize(x, (270, 480), interpolation=cv2.INTER_AREA) for x in fr]
    return np.vstack([np.hstack(th[:5]), np.hstack(th[5:] + [np.zeros_like(th[0])])])


def isolamento_ok(mid):
    """A guarda precisa recusar, na marca mid, um EDL com termos e arquivos de cada uma das outras marcas."""
    for outra in listar_marcas():
        if outra == mid:
            continue
        termo = ler_marca(outra)["exclusivo"]["termos"][0]
        if termo in termos_de_outras(mid):
            edl = {"marca": mid, "elementos": [{"tipo": "titulo", "texto": f"Conheça {termo}"}]}
            try:
                conferir_edl(edl)
                return False
            except ErroDeMarca:
                pass
        edl = {"marca": mid, "elementos": [{"tipo": "imagem", "arquivo": str(pasta_marca(outra) / "marca.json")}]}
        try:
            conferir_edl(edl)
            return False
        except ErroDeMarca:
            pass
    return True


def cmd_testar(a):
    """Teste de regressão de todas as marcas: (1) a folha visual tem de bater com testes/referencia/<marca>.png;
    (2) um vídeo sintético de 4 s passa pelo render inteiro (cortes, fundo marca, título, legenda, CTA, áudio)
    e o áudio final precisa ficar entre -17 e -15 LUFS com pico abaixo de -1,5 dBFS; o arquivo leva o selo da marca."""
    ref_dir, tmp = TESTES / "referencia", TESTES / "_tmp"
    ref_dir.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    marcas = [a.marca] if a.marca else listar_marcas()
    falhas = []
    src = tmp / "sintetico.mov"
    if not src.exists() and not a.so_visual:
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=4", "-f", "lavfi",
            "-i", "sine=f=180:r=48000:d=4,volume='0.25+0.2*sin(2*PI*3*t)':eval=frame",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(src)])
    for m in marcas:
        ativar(m)
        ok_iso = isolamento_ok(m)
        print(f"[{m}] isolamento: {'OK' if ok_iso else 'FALHOU'}")
        if not ok_iso:
            falhas.append(f"{m}: isolamento")
        folha = folha_marca()
        ref = ref_dir / f"{m}.png"
        if a.atualizar or not ref.exists():
            cv2.imwrite(str(ref), folha)
            print(f"[{m}] referência visual gravada: {ref}")
        else:
            r = cv2.imread(str(ref))
            dif = float(np.abs(r.astype(np.int16) - folha.astype(np.int16)).mean()) if r.shape == folha.shape else 99.0
            ok = dif < 1.5
            cv2.imwrite(str(tmp / f"{m}-atual.png"), folha)
            print(f"[{m}] visual: diferença média {dif:.2f} {'OK' if ok else 'FALHOU (veja testes/_tmp/' + m + '-atual.png)'}")
            if not ok:
                falhas.append(f"{m}: visual")
        if a.so_visual:
            continue
        pasta = tmp / m
        pasta.mkdir(exist_ok=True)
        pal = [{"t": w, "ini": 0.4 + 0.35 * i, "fim": 0.4 + 0.35 * i + 0.3, "p": 0.99}
               for i, w in enumerate("este é um teste automático de marca do editor".split())]
        json.dump({"duracao": 4.0, "palavras": pal, "rosto": {"w": 1080, "h": 1920, "quadros": 120,
                   "amostras": [[0, 0.5, 0.35, 0.2]]}}, open(pasta / "analise.json", "w"))
        edl = rascunho_edl(src, pal, dur=4.0)
        edl["segmentos"] = [{"id": 0, "ini": 0.3, "fim": 1.8, "zoom": 1.0, "transicao": None},
                            {"id": 1, "ini": 2.1, "fim": 3.9, "zoom": 1.0, "transicao": "push"}]
        edl["fundo"] = {"tipo": "marca", "parallax": True, "sombra": True}
        edl["elementos"] = [{"tipo": "titulo", "texto": "Teste automático", "na": "teste", "segura": 0.8},
                            {"tipo": "objeto3d", "nome": "foguete", "na": "automático", "segura": 0.6, "x": 0.8, "y": 0.3},
                            {"tipo": "objeto3d", "nome": "claude", "na": "marca", "segura": 0.5, "x": 0.2, "y": 0.3},
                            {"tipo": "efeito", "nome": "confete", "na": "editor", "segura": 0.6},
                            {"tipo": "efeito", "nome": "grao", "ini": 0.3, "fim": 3.9}]
        edl["cta"]["duracao"] = 1.5
        if politica_musica() == "obrigatoria":  # marca com trilha: o teste também passa pela música e pelo ducking
            edl["musica"] = dict(edl.get("musica") or {}, faixa="carefree")
        json.dump(edl, open(pasta / "edl.json", "w"), ensure_ascii=False)
        r = subprocess.run([sys.executable, str(RAIZ / "editor.py"), "renderizar", str(pasta / "edl.json"), "--rapido"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[{m}] render: FALHOU\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
            falhas.append(f"{m}: render")
            continue
        lufs, pico = medir_audio(pasta / "final.mp4")
        ok = -17 <= lufs <= -15 and pico < -1.5
        print(f"[{m}] render: OK · áudio {lufs:.1f} LUFS, pico {pico:.1f} dBFS {'OK' if ok else 'FALHOU'}")
        if not ok:
            falhas.append(f"{m}: áudio")
        tags = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(pasta / "final.mp4")]))
        selo = tags["format"].get("tags", {}).get("comment", "")
        if f"marca={m};" not in selo + ";":
            print(f"[{m}] selo: FALHOU (metadados: {selo!r})")
            falhas.append(f"{m}: selo")
    print("\nTUDO OK" if not falhas else "\nFALHAS: " + "; ".join(falhas))
    sys.exit(1 if falhas else 0)

