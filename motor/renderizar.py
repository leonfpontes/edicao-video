"""`renderizar`: aplica o EDL ao vídeo (cortes, enquadramento, fundo, elementos, legendas, vinheta, CTA e áudio)."""
import hashlib
import json
import math
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .audio import gerar_sfx, loudnorm_2a, medir_loudnorm, mixar_eventos, modo_sons, som_padrao
from .bibliotecas import musica_do_edl, som
from .camera import Camera, Rosto, borda_exposta, matriz_enquadre, transicao, zoom_em
from .config import BIBLIOTECA, FORMATOS, FPS
from .cor import aplicar_cor, aplicar_lut3d, ler_cube, lut_clipe, lut_cor, tabela_lut3d
from .elementos import Elementos
from .estilos import aplicar_estilo, aplicar_look, precisa_recorte
from .fundo import FundoMarca
from .graficos import blend, cobrir, pil2np, sombra
from .guarda import conferir_auditoria, conferir_edl
from .legendas import Legendas
from .marca import CFG, CORES, ErroDeMarca, ativar, logo_marca, padrao, registrar, tem_logo
from .perspectiva import bolha
from .planos import Palco, compor, legenda_y
from .qa import AMOSTRA, borda_ruim, conferir_quadro, relatorio
from .segmentacao import Segmentador
from .util import bgr, sh, tem_audio
from .vinhetas import cartao_cta, quadro_intro


def fixar_pontos(elementos, video, pasta):
    """Elementos com \"fixar\": [t, x, y] (um ponto do ambiente na fonte) ganham a trilha \"seguir\" pelo fluxo óptico.
    A trilha fica em cache em P/_cache/fixar.json (mesmo ponto e janela, mesma trilha)."""
    alvo = [e for e in elementos if e.get("fixar") and not e.get("seguir")]
    if not alvo:
        return
    from .cena import rastrear_ponto
    arq = Path(pasta) / "_cache" / "fixar.json"
    try:  # os processos do render leem e gravam o mesmo cache: leitura tolerante e gravação atômica
        cache = json.load(open(arq)) if arq.exists() else {}
    except (json.JSONDecodeError, OSError):
        cache = {}
    for e in alvo:
        t0, x, y = e["fixar"]
        # ancorado pela fala ("na"/"ate"), o tempo exato só sai depois; a janela em volta do ponto cobre a entrada e a saída
        ini, fim = e.get("ini", t0 - 1.0), e.get("fim", t0 + 4.0)
        chave = f"{t0}:{x}:{y}:{ini}:{fim}"
        if chave not in cache:
            cache[chave] = rastrear_ponto(video, t0, x, y, ini - 0.3, fim + 0.3)
        e["seguir"] = cache[chave]
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(f"fixar.{os.getpid()}.tmp")
    json.dump(cache, open(tmp, "w"))
    os.replace(tmp, arq)


def igualar_luz(segs, video, forca=0.8):
    """Mede a luz média de cada trecho (3 quadros) e grava em s["_lut_luz"] uma curva de gama que leva o trecho para a
    mediana do vídeo. Corrige sala escura e cozinha clara sem estourar (gama entre 0,75 e 1,3)."""
    cap = cv2.VideoCapture(str(video))
    medias = []
    for s in segs:
        vals = []
        for q in (0.2, 0.5, 0.8):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(s["ia"] + (s["ib"] - s["ia"]) * q))
            ok, f = cap.read()
            if ok:
                g = cv2.cvtColor(cv2.resize(f, (90, 160)), cv2.COLOR_BGR2GRAY)
                vals.append(float(np.clip(g.mean() / 255, 0.05, 0.95)))
        medias.append(float(np.mean(vals)) if vals else None)
    cap.release()
    ok = [m for m in medias if m]
    if not ok:
        return
    alvo = float(np.median(ok))
    x = np.arange(256) / 255
    for s, m in zip(segs, medias):
        if not m:
            continue
        gama = float(np.clip(math.log(alvo) / math.log(m), 0.75, 1.3)) ** forca
        s["_lut_luz"] = np.clip(255 * x ** gama + 0.5, 0, 255).astype(np.uint8) if abs(gama - 1) > 0.02 else None


def sons_do_video(segs, els, au, dur_intro, dur_fala, dur_cta, pasta):
    """Todos os efeitos sonoros do vídeo: [(início em s, arquivo, ganho em dB)], na linha do tempo final.
    Modo "biblioteca": o ápice de cada som (campo "ataque" do catálogo) cai no corte ou na entrada do elemento.
    Modo "gerado": o whoosh e o pop sintéticos, como sempre foram."""
    biblio = modo_sons() == "biblioteca"
    marcas_tempo = []  # (instante-alvo, id do som ou "whoosh"/"pop", ajuste em dB)
    if au.get("sfx_transicoes", True):
        n = 0
        for s in segs:
            tr, pedido = s.get("transicao"), s.get("som")
            if not tr or pedido is False or pedido == "":
                continue
            if isinstance(pedido, str):
                marcas_tempo.append((s["o"], pedido, 0))
            elif biblio:
                marcas_tempo.append((s["o"], som_padrao("transicoes", tr, n) or som_padrao("transicoes", "push", n), 0))
                n += 1
            else:
                marcas_tempo.append((s["o"] - 0.12, "whoosh", 0))
        if dur_cta:
            marcas_tempo.append((dur_fala, som_padrao("cta"), 0) if biblio else (dur_fala - 0.12, "whoosh", 0))
    if au.get("sfx_elementos", True):
        marcas_tempo += els.eventos(modo_sons())
    else:  # sons pedidos de propósito ("tipo": "som") tocam sempre
        marcas_tempo += [(e["o_ini"], e["nome"], e.get("volume_db", 0)) for e in els.items if e["tipo"] == "som"]
    marcas_tempo = [(t + dur_intro, sid, g) for t, sid, g in marcas_tempo]
    if dur_intro:  # assinatura sonora da vinheta: whoosh na abertura, toque no ponto, mergulho no fim
        if biblio:
            marcas_tempo += [(0.35, som_padrao("vinheta", "abertura"), 0), (1.05, som_padrao("vinheta", "ponto"), 0),
                             (dur_intro, som_padrao("vinheta", "mergulho"), 0)]
        else:
            marcas_tempo += [(0.0, "whoosh", 0), (dur_intro - 0.45, "whoosh", 0), (1.05, "pop", 0)]
    eventos = []
    gerados = None
    for t, sid, g in marcas_tempo:
        if not sid:
            continue
        if sid in ("whoosh", "pop"):
            gerados = gerados or gerar_sfx(pasta)
            eventos.append((t, gerados[0 if sid == "whoosh" else 1], g))
        else:
            cam, it = som(sid)
            eventos.append((t - it.get("ataque", 0), cam, it.get("volume_db", 0) + g))
    return sorted(eventos, key=lambda ev: ev[0])


class Parado:
    """Mede o maior trecho sem mudança visual (regra "nada parado por mais de N segundos" dos estilos)."""

    def __init__(self, limite):
        self.limite, self.ant, self.desde, self.pior = limite, None, 0.0, (0.0, 0.0)

    def quadro(self, f, t):
        if not self.limite:
            return
        pq = cv2.cvtColor(cv2.resize(f, (54, 96), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.int16)
        if self.ant is None or np.abs(pq - self.ant).mean() > 2.2:  # mudou: começa a contar de novo
            self.ant, self.desde = pq, t
        elif t - self.desde > self.pior[1] - self.pior[0]:
            self.pior = (self.desde, t)

    def relatar(self):
        if not self.limite:
            return
        a, b = self.pior
        if b - a > self.limite:
            print(f"Aviso de ritmo: {b - a:.1f}s sem mudança visual (de {a:.1f}s a {b:.1f}s); o estilo pede no máximo "
                  f"{self.limite:.1f}s. Ponha um elemento, um zoom ou um corte nesse trecho.")
        else:
            print(f"Ritmo: maior trecho parado {b - a:.1f}s (limite {self.limite:.1f}s)")


def caminho_edl(v, pasta):
    """Caminho de arquivo citado no EDL: relativo à pasta do próprio EDL (não à pasta de onde o comando roda).
    Caminhos absolutos, com ~ ou que não existem ao lado do EDL ficam como estão (a biblioteca resolve ids)."""
    if not isinstance(v, str) or not v:
        return v
    q = Path(v).expanduser()
    if q.is_absolute():
        return str(q)
    return str(pasta / q) if (pasta / q).exists() else v


def resolver_caminhos(edl, pasta):
    """Ajusta, no lugar, todo "arquivo"/"imagem"/"fonte" do EDL para a pasta do EDL."""
    if edl.get("fonte"):
        edl["fonte"] = caminho_edl(edl["fonte"], pasta)
    f = edl.get("fundo")
    if isinstance(f, dict) and f.get("imagem"):
        f["imagem"] = caminho_edl(f["imagem"], pasta)
    for e in edl.get("elementos", []):
        if e.get("arquivo"):
            e["arquivo"] = caminho_edl(e["arquivo"], pasta)
        if isinstance(e.get("arquivos"), list):
            e["arquivos"] = [caminho_edl(x, pasta) for x in e["arquivos"]]
    m = edl.get("musica")
    if isinstance(m, dict) and m.get("arquivo"):
        m["arquivo"] = caminho_edl(m["arquivo"], pasta)
    return edl


class Contexto:
    """Tudo o que o render precisa, montado a partir do EDL. Cada processo de render monta o seu (determinístico)."""

    def __init__(self, edl_p, falar=True, rapido=False, formato=None):
        edl_p = Path(edl_p).resolve()
        self.interp = cv2.INTER_LINEAR if rapido else cv2.INTER_CUBIC  # rápido: só para conferir
        self.pasta = pasta = edl_p.parent
        edl = self.edl = resolver_caminhos(aplicar_estilo(json.load(open(edl_p))), pasta)
        if formato:  # outro formato do mesmo EDL (exportar): sai com o nome do formato
            if formato not in FORMATOS:
                raise ErroDeMarca(f"formato desconhecido: {formato} (opções: {', '.join(FORMATOS)})")
            edl["formato"] = formato
            edl["saida"] = f"final_{formato}.mp4"
        if not edl.get("marca"):
            raise ErroDeMarca("o edl.json não diz a marca (\"marca\"): rode `analisar --marca <marca>` de novo")
        ativar(edl["marca"])
        an = self.an = json.load(open(pasta / "analise.json"))
        conferir_edl(edl, an, pasta)
        if falar:
            print(f"Marca: {CFG['nome']}", flush=True)
        self.formato = formato
        self.W, self.H = W, H = FORMATOS[edl.get("formato", "vertical")]
        self.src = edl["fonte"]

        # segmentos quantizados na grade de quadros (áudio e vídeo cortam no mesmo ponto).
        # A ordem do EDL é a ordem do vídeo; um segmento com "gancho": true repete um trecho no início.
        segs = [dict(s) for s in edl["segmentos"]]
        q = lambda t: round(t * FPS) / FPS
        for s in segs:
            s["qa"], s["qb"] = q(s["ini"]), q(s["fim"])
        segs = [s for s in segs if s["qb"] - s["qa"] >= 2 / FPS]
        for i in range(1, len(segs)):
            if not segs[i].get("gancho") and not segs[i - 1].get("gancho") and segs[i]["qa"] >= segs[i - 1]["qa"]:
                segs[i]["qa"] = max(segs[i]["qa"], segs[i - 1]["qb"])
        cap = cv2.VideoCapture(self.src)
        self.w0, self.h0 = int(cap.get(3)), int(cap.get(4))
        n_fonte = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 10 ** 9
        cap.release()
        for s in segs:  # quadros que o segmento realmente tem (a fonte pode acabar antes do "fim")
            s["ia"], s["ib"] = int(round(s["qa"] * FPS)), min(int(round(s["qb"] * FPS)), n_fonte)
            s["n"] = max(s["ib"] - s["ia"], 0)
        self.segs, self.keep = segs, [(s["qa"], s["qb"]) for s in segs]
        o = 0.0
        for s in segs:
            s["o"] = o
            o += s["qb"] - s["qa"]
        self.dur_fala = o
        self.cta = cta = padrao(edl, "cta", {})
        if cta.get("ativo") and not cta.get("chamada"):
            sys.exit("CTA ligado sem 'chamada' (e 'url'): preencha o cta no edl.json ou desligue com \"ativo\": false")
        self.dur_cta = cta.get("duracao", 3.5) if cta.get("ativo") else 0
        intro = padrao(edl, "intro", {"ativo": True})
        self.dur_intro = round(intro.get("duracao", 2.2) * FPS) / FPS if intro.get("ativo", True) else 0.0
        self.n_intro = int(round(self.dur_intro * FPS))
        self.total = self.dur_intro + self.dur_fala + self.dur_cta
        # "intro": {"apos_gancho": true}: o gancho abre o vídeo e a vinheta entra logo depois dele, fazendo a ponte
        n_g = 0
        while n_g < len(segs) and segs[n_g].get("gancho"):
            n_g += 1
        self.apos_gancho = bool(intro.get("apos_gancho") and self.n_intro and 0 < n_g < len(segs))
        self.i_pos_gancho = n_g if self.apos_gancho else None
        self.dur_gancho = segs[n_g]["o"] if self.apos_gancho else 0.0
        self.n_gancho = sum(sg["n"] for sg in segs[:n_g]) if self.apos_gancho else 0

        # componentes
        self.rosto = Rosto(an["rosto"])
        self.fundo = fundo = edl.get("fundo", {})
        self.tipo_fundo = fundo.get("tipo", "original")
        self.fundo_vivo = FundoMarca(W, H, fundo.get("variante", "marinho"))
        self.bg_img = (cobrir(cv2.imread(str(registrar(fundo["imagem"]))), int(W * 1.2), int(H * 1.2))
                       if self.tipo_fundo == "imagem" else None)
        self.cor = edl.get("cor", {})
        self.luts = lut_cor(self.cor)
        self.lut3d = None
        if self.cor.get("lut"):  # LUT 3D (.cube) da marca, da biblioteca ou da pasta do vídeo
            arq = self.cor["lut"]
            caminho = registrar(arq if Path(arq).exists() else BIBLIOTECA / "luts" / f"{arq}.cube")
            self.lut3d = tabela_lut3d(ler_cube(caminho), float(self.cor.get("lut_intensidade", 1.0)))
        if self.cor.get("igualar_luz"):  # cômodos com luz diferente: cada trecho vai para a exposição do meio do vídeo
            igualar_luz(segs, self.src, float(self.cor.get("igualar_luz_forca", 0.8)))
        cc = an.get("cor_clipes")
        self.luts_clipes = [lut_clipe(x) for x in cc] if cc and self.cor.get("igualar_clipes", True) else None
        self.leg = (Legendas(an["palavras"], edl.get("legendas", {}), W, H, self.keep)
                    if edl.get("legendas", {}).get("ativo", True) else None)
        fixar_pontos(edl.get("elementos", []), self.src, self.pasta)
        self.els = Elementos(edl.get("elementos", []), W, H, self.map_out, an["palavras"])
        self.els.fonte = (self.w0, self.h0)  # para projetar as trilhas ("seguir") da fonte no quadro de saída
        self.zooms = edl.get("zooms", [])
        self.marca = None
        self.barra = padrao(edl, "barra_progresso", True)
        if padrao(edl, "marca_dagua", True) and tem_logo():
            self.marca, _ = sombra(pil2np(logo_marca(CFG.get("marca_dagua_alt", 80))), 6, 0.5, (0, 3))
        self.TRN = int(FPS * edl.get("duracao_transicao", 0.3))
        self.clipes_ini = an.get("rosto", {}).get("clipes_ini", [0.0])
        self.cache_recorte = None
        if edl.get("cache_recorte", True):
            st = Path(self.src).stat()
            chave = hashlib.sha1(f"{Path(self.src).resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:12]
            self.cache_recorte = pasta / "_cache" / f"recorte-{chave}"
            self.cache_recorte.mkdir(parents=True, exist_ok=True)
        self.usa_recorte = (self.tipo_fundo != "original" or any(precisa_recorte(s.get("look")) for s in segs)
                            or any(e["tipo"] == "texto_atras" for e in self.els.items))

    def map_out(self, t):
        normais = [s for s in self.segs if not s.get("gancho")]
        for s in normais:
            if s["qa"] <= t < s["qb"]:
                return s["o"] + t - s["qa"]
        depois = [s for s in normais if s["qa"] > t]
        return min(depois, key=lambda s: s["qa"])["o"] if depois else self.dur_fala

    def clipe_de(self, t):
        return sum(1 for c in self.clipes_ini[1:] if t >= c)

    def quadros_antes(self, i):
        """Quadros de saída antes do segmento i (vinheta + segmentos anteriores)."""
        return self.n_intro + sum(s["n"] for s in self.segs[:i])


class Trecho:
    """Renderiza um grupo contínuo de segmentos [i0, i1). Com i0 > 0, aquece a câmera, o recorte e o
    quadro da transição com o fim do segmento anterior, para o resultado ser igual ao do render corrido."""

    def __init__(self, ctx, seg=None):
        self.c = ctx
        self.camera = Camera()
        self.seg = seg  # recorte da pessoa sob demanda (pode vir de um trecho anterior do mesmo processo)
        if seg is not None and seg.rvm is not None:
            seg.reset()
        self.palco = None
        self.rvm_fi = None
        self.ultimo = None
        self.avisos = []  # conferência visual: (problema, onde, instante)
        self.cap = cv2.VideoCapture(ctx.src)
        self.n_src = 0

    def ler(self, fi):
        if fi < self.n_src or fi - self.n_src > FPS * 20:  # trecho anterior (gancho) ou salto longo: busca direta
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            self.n_src = fi
        while self.n_src < fi:
            self.cap.grab()
            self.n_src += 1
        ok, f = self.cap.read()
        self.n_src += 1
        return f if ok else None

    def recortador(self):
        if self.seg is None:
            self.seg = Segmentador()
        return self.seg

    def recorte(self, fi, f, com_frente):
        """Recorte da pessoa no quadro fi, com cache em disco (o mesmo vídeo é renderizado muitas vezes enquanto
        o EDL é ajustado; o recorte é a parte mais cara e não depende do EDL)."""
        c = self.c
        arq_a = c.cache_recorte / f"{fi:06d}a.png" if c.cache_recorte else None
        arq_f = c.cache_recorte / f"{fi:06d}f.jpg" if c.cache_recorte else None
        if arq_a is not None and arq_a.exists() and (not com_frente or arq_f.exists()):
            a = cv2.imread(str(arq_a), cv2.IMREAD_GRAYSCALE)
            if a is not None:
                frente = cv2.imread(str(arq_f)) if com_frente else f
                self.rvm_fi = None  # a rede não viu este quadro: o próximo cálculo recomeça o estado
                return a.astype(np.float32) * (1 / 255), frente
        seg = self.recortador()
        if fi != (self.rvm_fi if self.rvm_fi is not None else -10) + 1 and seg.rvm is not None:
            seg.reset()
        alfa, frente = seg.recortar(f)
        self.rvm_fi = fi
        if arq_a is not None:
            cv2.imwrite(str(arq_a), (alfa * 255 + 0.5).astype(np.uint8))
            if com_frente:
                cv2.imwrite(str(arq_f), frente, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return alfa, frente

    def base(self, s, fi, f, t_out):
        """Quadro-base (antes de transição, elementos e legenda) do quadro fi da fonte."""
        c, els, W, H = self.c, self.c.els, self.c.W, self.c.H
        t_src = fi / FPS
        zb, face = self.camera.passo(s.get("zoom", 1.0), c.rosto.em(t_src))
        respira = 1 + 0.02 * math.sin((t_out + c.dur_intro) * 0.3)  # aproximação lenta e contínua
        zf, tremor = zoom_em(t_src, c.zooms, s["qb"])
        z = zb * respira * zf
        M = matriz_enquadre(c.w0, c.h0, W, H, z, face, tremor)
        els.M, els.t_src = M, t_src  # elementos com "seguir" acompanham a mão, o rosto ou a parede neste quadro
        if s.get("_lut_luz") is not None:
            f = cv2.LUT(f, s["_lut_luz"])
        if c.luts_clipes:  # clipes gravados em momentos diferentes ficam com a mesma cor
            f = cv2.LUT(f, c.luts_clipes[min(c.clipe_de(t_src), len(c.luts_clipes) - 1)])
        plano = s.get("plano", "rosto")
        els.plano = plano
        br_e = els.broll_ativo(t_out)
        br = els.broll(t_out) if br_e is not None else None
        fundo, tipo_fundo = c.fundo, c.tipo_fundo
        if (br is None and plano != "motion") or (br is not None and br_e.get("bolha")):
            look = s.get("look")
            atras = plano != "motion" and bool(els.ativos(t_out, "texto_atras"))
            com_fundo = tipo_fundo != "original"
            precisa_m = com_fundo or precisa_recorte(look) or atras
            base = cv2.warpAffine(f, M, (W, H), flags=c.interp, borderMode=cv2.BORDER_REPLICATE)
            if borda_exposta(M, c.w0, c.h0, W, H) or (fi % (AMOSTRA * 2) == 0 and borda_ruim(base)):
                self.avisos.append(("borda esticada", "enquadramento", t_out))  # nunca entregue com borda fora da imagem
            m = None
            if precisa_m:
                alfa, frente = self.recorte(fi, f, com_fundo)
                m = cv2.warpAffine(alfa, M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
            if com_fundo:
                base = cv2.warpAffine(frente, M, (W, H), flags=c.interp, borderMode=cv2.BORDER_REPLICATE)
                if tipo_fundo == "desfoque":
                    pq = cv2.resize(base, (W // 4, H // 4))
                    bg = cv2.resize(cv2.GaussianBlur(pq, (0, 0), 7), (W, H))
                else:
                    # parallax: o fundo anda menos que a pessoa (sensação de profundidade)
                    par = fundo.get("parallax", True)
                    pz = 1 + (z - 1) * 0.3 if par else 1
                    dx = 0.5 + 0.025 * math.sin(t_out * 0.22) if par else 0.5
                    bg = c.fundo_vivo.quadro(t_out, pz, dx) if c.bg_img is None else cobrir(c.bg_img, W, H, pz, dx, 0.5)
                if fundo.get("sombra", True) and tipo_fundo != "desfoque":
                    sm = cv2.GaussianBlur(np.roll(m[..., 0], (22, 12), (0, 1)), (0, 0), 18)[..., None]
                    bg = (bg.astype(np.float32) * (1 - 0.4 * sm)).astype(np.uint8)
                base = (base.astype(np.float32) * m + bg.astype(np.float32) * (1 - m)).astype(np.uint8)
            base = aplicar_cor(base, c.luts, c.cor)
            if c.lut3d is not None:
                base = aplicar_lut3d(base, c.lut3d)
            base = aplicar_look(base, look, m, c.cor.get("proteger_pele", True))
            if atras:  # texto atrás da pessoa: desenha no quadro e cola a pessoa recortada por cima
                camada = base.copy()
                els.desenhar(camada, t_out, "atras")
                base = (camada.astype(np.float32) * (1 - m) + base.astype(np.float32) * m).astype(np.uint8)
            rx_, ry_ = M @ np.array([face[0] * c.w0, face[1] * c.h0, 1.0])
            els.rosto = (float(rx_), float(ry_), float(face[2] * c.h0 * M[0, 0]))
            if br is not None:  # b-roll com bolha de rosto
                base = bolha(br.copy(), base, br_e.get("bolha"), W, H, els.rosto)
        elif br is not None:
            base = br
            els.rosto = None
        else:  # plano só de motion: a câmera não aparece
            base = None
            els.rosto = None
        if plano != "rosto" and br is None:
            self.palco = self.palco or Palco(W, H)
            corte_y = s.get("corte_y", 0.36)
            base = compor(plano, base if base is not None else self.palco.quadro, self.palco.quadro, W, H, corte_y)
            if plano == "dividido" and els.rosto:
                y0 = int(np.clip(corte_y * H - H // 4, 0, H - H // 2))
                els.rosto = (els.rosto[0], els.rosto[1] - y0 + H // 2, els.rosto[2])
        return base

    def acabamento(self, out, t_out, t_src, conferir=False):
        c, els, W, H = self.c, self.c.els, self.c.W, self.c.H
        els.caixas = [] if conferir else None
        els.desenhar(out, t_out)
        caixa_leg = fundo_leg = None
        # elemento com "sem_legenda": true tira a legenda enquanto está na tela (o rótulo já diz a mesma coisa)
        cala = any(e.get("sem_legenda") and e["o_ini"] <= t_out < e["o_fim"] for e in els.items)
        if c.leg and not cala:
            bi = c.leg.bloco_em(t_src)
            if bi is not None:
                img = c.leg.render(bi, t_src)
                pl = els.plano
                y = H * legenda_y(pl, c.leg.cfg.get("posicao_y", 0.68), c.leg.cfg)
                x, y = W / 2 - img.shape[1] / 2, y if pl == "rosto" else y - img.shape[0] / 2
                if conferir:
                    m = (img[..., 3] > 60).nonzero() if img.shape[2] == 4 else None
                    if m is not None and len(m[0]):
                        caixa_leg = (x + m[1].min(), y + m[0].min(), x + m[1].max(), y + m[0].max())
                        if c.leg.cfg.get("estilo") == "limpa":
                            x0, y0, x1, y1 = (int(np.clip(v, 0, lim)) for v, lim in zip(caixa_leg, (W, H, W, H)))
                            if x1 > x0 and y1 > y0:
                                fundo_leg = float(cv2.cvtColor(out[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).mean())
                blend(out, img, x, y)
                emo = c.leg.emoji(bi, t_src)
                if emo is not None:
                    blend(out, emo, W / 2 - emo.shape[1] / 2, y - emo.shape[0] * 0.92)
        if conferir:
            self.avisos += conferir_quadro(W, H, t_out, els.caixas, caixa_leg, els.rosto, els.plano, fundo_leg, H > W)
            els.caixas = None
        if c.marca is not None and not els.ativo(t_out, "titulo"):
            blend(out, c.marca, W - c.marca.shape[1] - 30, H * CFG.get("marca_dagua_y", 0.115) if H > W else 40, 0.85)
        if c.barra:
            t_barra = t_out if c.apos_gancho and t_out < c.dur_gancho else t_out + c.dur_intro  # o gancho vem antes da vinheta
            cv2.rectangle(out, (0, 0), (int(W * t_barra / c.total), 6), bgr(CORES["champanhe"]), -1)
        els.desenhar(out, t_out, "pos")  # efeitos de quadro inteiro (grão, vinheta, glitch…) por cima de tudo

    def salto(self, s):
        """"salto": true no segmento troca o zoom no corte (jump cut com mudança de enquadramento), sem deslizar."""
        if s.get("salto") and self.camera.z is not None:
            self.camera.z = s.get("zoom", 1.0)

    def aquecer(self, i0):
        """Põe câmera, recorte e quadro da transição no estado em que o render corrido chegaria ao segmento i0."""
        c = self.c
        for j, s in enumerate(c.segs[:i0]):
            if j and c.clipe_de(s["qa"]) != c.clipe_de(c.segs[j - 1]["qa"]):
                self.camera = Camera()
            self.salto(s)
            ultimo_seg = j == i0 - 1
            cheios = (12 if c.usa_recorte else 1) if ultimo_seg else 0  # quadros finais refeitos por inteiro
            n_out = c.quadros_antes(j)
            for k, fi in enumerate(range(s["ia"], s["ib"])):
                if k < s["n"] - cheios:
                    self.camera.passo(s.get("zoom", 1.0), c.rosto.em(fi / FPS))
                    continue
                f = self.ler(fi)
                if f is None:
                    break
                self.ultimo = self.base(s, fi, f, (n_out + k) / FPS - c.dur_intro)
        if i0 < len(c.segs) and i0 and c.clipe_de(c.segs[i0]["qa"]) != c.clipe_de(c.segs[i0 - 1]["qa"]):
            self.camera = Camera()
        if self.ultimo is not None:
            self.ultimo = self.ultimo.copy()

    def render(self, i0, i1, saida, rapido, com_cta, progresso=None, fechar=True, janela=None, passo=1):
        """Escreve os quadros dos segmentos [i0, i1) em `saida` (com a vinheta se i0 == 0 e o CTA se com_cta).
        Prévia: `janela` (ini, fim) em segundos do vídeo final e `passo` (1 a cada N quadros) limitam o que é desenhado.
        Devolve o pior trecho parado (início, fim) visto aqui."""
        c, W, H = self.c, self.c.W, self.c.H
        quer = lambda n: (janela is None or janela[0] <= n / FPS < janela[1]) and n % passo == 0
        enc = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{FPS / passo:g}", "-i", "-",
               "-c:v", "libx264", "-preset", "ultrafast" if rapido else "medium", "-crf", "18",
               "-pix_fmt", "yuv420p", str(saida)]
        proc = subprocess.Popen(enc, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        parado = Parado(c.edl.get("parado_max"))
        n_out = c.quadros_antes(i0)
        if i0 == 0:
            cache_intro = {}
            for k in range(c.n_intro):  # vinheta de abertura (igual em todos os vídeos)
                if not quer(k) and k != c.n_intro - 1:
                    continue
                out = quadro_intro(W, H, k / FPS, c.fundo_vivo, cache_intro, c.dur_intro)
                self.ultimo = out
                if not quer(k):
                    continue
                proc.stdin.write(out.tobytes())
            n_out = c.n_intro
        else:
            self.aquecer(i0)
        for si in range(i0, i1):
            s = c.segs[si]
            if si > i0 and c.clipe_de(s["qa"]) != c.clipe_de(c.segs[si - 1]["qa"]):
                self.camera = Camera()  # outra cena: o enquadramento começa no lugar certo, sem deslizar
            self.salto(s)
            base = None
            tipo_tr = s.get("transicao") or ("zoom" if si == 0 and c.dur_intro and not c.apos_gancho else None)
            if c.apos_gancho and si == 0:
                tipo_tr = None  # o gancho abre o vídeo seco
            if c.apos_gancho and si == c.i_pos_gancho:  # depois da vinheta: a transição sai do último quadro dela
                self.ultimo = quadro_intro(W, H, (c.n_intro - 1) / FPS, c.fundo_vivo, {}, c.dur_intro)
                tipo_tr = s.get("transicao") or "zoom"
            for k, fi in enumerate(range(s["ia"], s["ib"])):
                if not quer(n_out) and k != s["n"] - 1:  # prévia: fora da janela só a câmera anda
                    self.camera.passo(s.get("zoom", 1.0), c.rosto.em(fi / FPS))
                    n_out += 1
                    continue
                f = self.ler(fi)
                if f is None:
                    raise RuntimeError(f"a fonte acabou antes do quadro {fi}: rode o analisar de novo")
                t_src, t_out = fi / FPS, n_out / FPS - c.dur_intro
                base = self.base(s, fi, f, t_out)
                out = base
                if tipo_tr and self.ultimo is not None and k < c.TRN:
                    out = transicao(self.ultimo, base, (k + 1) / (c.TRN + 1), tipo_tr, W, H)
                if not quer(n_out):
                    n_out += 1
                    continue
                out = out.copy()
                self.acabamento(out, t_out, t_src, conferir=n_out % AMOSTRA == 0)
                parado.quadro(out, t_out)
                proc.stdin.write(out.tobytes())
                n_out += 1
            if base is not None:
                self.ultimo = base.copy()
            if progresso:
                progresso(s["n"])
        self.cap.release()
        if self.seg is not None and fechar:
            self.seg.fechar()
        if com_cta:
            cache = {}
            for k in range(int(round(c.dur_cta * FPS))):
                if not quer(n_out):
                    n_out += 1
                    continue
                out = cartao_cta(c.cta, W, H, k / FPS, c.fundo_vivo, cache)
                if k < c.TRN and self.ultimo is not None:
                    out = transicao(self.ultimo, out, (k + 1) / (c.TRN + 1), c.edl.get("transicao_cta", "zoom"), W, H)
                if c.barra:
                    cv2.rectangle(out, (0, 0), (int(W * (n_out / FPS) / c.total), 6), bgr(CORES["champanhe"]), -1)
                proc.stdin.write(out.tobytes())
                n_out += 1
        proc.stdin.close()
        proc.wait()
        if proc.returncode:
            raise RuntimeError(f"o ffmpeg falhou ao codificar {saida}")
        return parado.pior


def dividir_trechos(segs, n, minimo=1.5):
    """Grupos contínuos de segmentos com quantidade parecida de quadros (no máximo n grupos, cada um com `minimo` s ou mais)."""
    total = sum(s["n"] for s in segs)
    n = max(1, min(n, len(segs), int(total // (minimo * FPS)) or 1))
    alvo, grupos, ini, acum = total / n, [], 0, 0
    for i, s in enumerate(segs):
        acum += s["n"]
        if acum >= alvo * (len(grupos) + 1) and len(grupos) < n - 1 and i + 1 < len(segs):
            grupos.append((ini, i + 1))
            ini = i + 1
    grupos.append((ini, len(segs)))
    return grupos


_CACHE = {}  # por processo de render: contexto e recorte reaproveitados entre os trechos que ele pega


def _trabalho(edl_p, i0, i1, saida, rapido, com_cta, threads, formato=None):
    """Processo de render de um trecho (monta o próprio contexto: o render é determinístico)."""
    cv2.setNumThreads(threads)
    os.environ["EDITOR_THREADS"] = str(threads)
    if _CACHE.get("chave") != (edl_p, rapido, formato):
        _CACHE.clear()
        _CACHE.update(chave=(edl_p, rapido, formato), ctx=Contexto(edl_p, falar=False, rapido=rapido, formato=formato))
    tr = Trecho(_CACHE["ctx"], _CACHE.get("seg"))
    pior = tr.render(i0, i1, saida, rapido, com_cta, fechar=False)
    _CACHE["seg"] = tr.seg
    return pior, sorted(str(p) for p in conferir_auditoria()), tr.avisos


def processos_padrao():
    return max(1, min(8, (os.cpu_count() or 2)))


def render_video(ctx, edl_p, saida, rapido, processos):
    """Renderiza o vídeo (sem áudio). Com mais de um processo, divide em trechos, renderiza em paralelo e emenda."""
    grupos = dividir_trechos(ctx.segs, processos * 3 if processos > 1 else 1)
    t0 = time.time()
    tot = ctx.n_intro + sum(s["n"] for s in ctx.segs) + int(round(ctx.dur_cta * FPS))
    if len(grupos) == 1:
        feitos = [ctx.n_intro]

        def progresso(n):
            feitos[0] += n
            gasto = time.time() - t0
            print(f"  {feitos[0] / FPS:5.1f}s / {ctx.total:.1f}s  ({feitos[0] / max(gasto, 1e-3):.1f} quadros/s)", flush=True)
        tr = Trecho(ctx)
        piores = [tr.render(0, len(ctx.segs), saida, rapido, True, progresso)]
        avisos = tr.avisos
    else:
        n_proc = min(processos, len(grupos))
        print(f"  render em {n_proc} processos ({len(grupos)} trechos)", flush=True)
        partes = [ctx.pasta / f"_parte{k:02d}.mp4" for k in range(len(grupos))]
        threads = max(1, (os.cpu_count() or 2) // n_proc)
        mpc = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=n_proc, mp_context=mpc) as ex:
            futs = [ex.submit(_trabalho, str(edl_p), i0, i1, str(p), rapido, k == len(grupos) - 1, threads, ctx.formato)
                    for k, ((i0, i1), p) in enumerate(zip(grupos, partes))]
            res = [f.result() for f in futs]
        piores = [r[0] for r in res]
        avisos = [a for r in res for a in r[2]]
        for r in res:
            for arq in r[1]:
                registrar(arq)
        lista = ctx.pasta / "_partes.txt"
        lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
        sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(saida)])
        for p in partes + [lista]:
            p.unlink()
    gasto = time.time() - t0
    print(f"  vídeo pronto em {gasto:.1f}s ({tot / max(gasto, 1e-3):.1f} quadros/s)", flush=True)
    a, b = max(piores, key=lambda p: p[1] - p[0])
    par = Parado(ctx.edl.get("parado_max"))
    par.pior = (a, b)
    par.relatar()
    return avisos


def render_audio(ctx, trilha):
    """Áudio final: mesmos cortes, limpeza de voz, sons, trilha com ducking e loudness para o Instagram (-16 LUFS).
    Devolve o caminho do wav e os arquivos temporários a apagar."""
    pasta, edl, an, src = ctx.pasta, ctx.edl, ctx.an, ctx.src
    segs, keep, els = ctx.segs, ctx.keep, ctx.els
    dur_intro, dur_fala, dur_cta, total = ctx.dur_intro, ctx.dur_fala, ctx.dur_cta, ctx.total
    au = edl.get("audio", {})
    parts, labels = [], []
    for i, s in enumerate(segs):
        d = s["qb"] - s["qa"]
        parts.append(f"[0:a]atrim={s['qa']:.4f}:{s['qb']:.4f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.012,afade=t=out:st={max(d - 0.012, 0):.4f}:d=0.012[a{i}]")
        labels.append(f"[a{i}]")
    # Cadeia conservadora (voz limpa e cheia, sem "estourar"): filtros suaves, compressão leve,
    # loudnorm em DUAS passadas (medida + linear) e um limitador no fim, depois dos efeitos.
    cadeia = ["highpass=f=80", "lowpass=f=14000"]
    if au.get("denoise", True):
        cadeia.append(f"afftdn=nr={au.get('denoise_db', 10)}:nf=-42:tn=1")
    cadeia += ["equalizer=f=250:t=q:w=1.0:g=-2"]
    if au.get("presenca_db", 1.0):
        cadeia.append(f"equalizer=f=3200:t=q:w=1.2:g={au.get('presenca_db', 1.0)}")
    cadeia += ["deesser=i=0.4", "acompressor=threshold=-24dB:ratio=2.5:attack=15:release=200:makeup=1",
               "aresample=48000"]
    fc_voz = ";".join(parts) + f";{''.join(labels)}concat=n={len(segs)}:v=0:a=1,{','.join(cadeia)}[v]"
    voz_bruta, voz = pasta / "_voz_bruta.wav", pasta / "_voz.wav"
    if au.get("voz", True) and tem_audio(src):
        sh(["ffmpeg", "-y", "-i", src, "-filter_complex", fc_voz, "-map", "[v]", "-ac", "1", str(voz_bruta)])
    else:  # clipe mudo ou "voz": false (só a trilha): silêncio do tamanho dos cortes
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{dur_fala:.4f}", str(voz_bruta)])
    alvo_lufs, alvo_tp = au.get("loudness", -16), -2.0
    m = medir_loudnorm(voz_bruta, alvo_lufs, alvo_tp)
    if m:
        sh(["ffmpeg", "-y", "-i", str(voz_bruta), "-af", loudnorm_2a(m, alvo_lufs, alvo_tp) + ",aresample=48000",
            "-ac", "1", str(voz)])
    else:  # som original em silêncio: não há o que normalizar
        shutil.copy(voz_bruta, voz)
    ganho = au.get("original_db", 0)  # som ambiente mais baixo sob a trilha (ex.: -8)
    fc = (f"[0:a]adelay={int(dur_intro * 1000)}:all=1,apad=whole_dur={total:.4f}"
          + (f",volume={ganho}dB" if ganho else "") + "[voz]")
    ins = ["-i", str(voz)]
    eventos = sons_do_video(segs, els, au, dur_intro, dur_fala, dur_cta, pasta)
    alvo, mix = "[voz]", []
    if eventos:
        ins_s, fc_s, mix = mixar_eventos(eventos, 1)
        ins += ins_s
        fc += fc_s
    rot_voz = "[voz]"
    if trilha:
        # trilha real: nivelada pelo loudness medido, em loop se for curta, com fade na entrada e no fim;
        # sob a voz, o ducking (sidechain) abaixa a música só enquanto ele fala
        mus = padrao(edl, "musica", {})
        fala = au.get("voz", True) and any(qa <= (w["ini"] + w["fim"]) / 2 < qb for w in an["palavras"] for qa, qb in keep)
        vol = mus.get("volume_db")
        vol = (-9 if fala else 0) if vol is None else vol
        mm = medir_loudnorm(trilha, alvo_lufs, alvo_tp)
        g = alvo_lufs + vol - float(mm["input_i"]) if mm else vol
        fi, fo = mus.get("fade_in", 0.8), mus.get("fade_out", 2.5)
        idx = len([x for x in ins if x == "-i"])
        ins += ["-stream_loop", "-1", "-ss", f"{mus.get('ini', 0)}", "-i", str(trilha)]
        fc += (f";[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.4f},asetpts=PTS-STARTPTS,"
               f"volume={g:.2f}dB,afade=t=in:d={fi},afade=t=out:st={max(total - fo, 0):.4f}:d={fo}[mus]")
        if mus.get("ducking", True) and fala:
            fc += (";[voz]asplit=2[vozm][vsc];[vsc]aformat=channel_layouts=stereo[sc];"
                   "[mus][sc]sidechaincompress=threshold=0.02:ratio=8:attack=30:release=450[musd]")
            rot_voz = "[vozm]"
            mix.append("[musd]")
        else:
            mix.append("[mus]")
    if mix:
        fc += f";{rot_voz}" + "".join(mix) + f"amix=inputs={len(mix) + 1}:normalize=0:duration=first[mix]"
        alvo = "[mix]"
    limitador = "alimiter=limit=0.79:attack=5:release=60:level=disabled"  # teto em -2 dBFS
    tmp_a = pasta / "_audio.wav"
    if trilha:
        # com trilha, o alvo de loudness vale para o conjunto (voz + música): mede a mistura e normaliza
        mix_wav = pasta / "_mix.wav"
        sh(["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", alvo, "-t", f"{total:.4f}", "-ar", "48000", "-ac", "2", str(mix_wav)])
        mm = medir_loudnorm(mix_wav, alvo_lufs, alvo_tp)
        af = (loudnorm_2a(mm, alvo_lufs, alvo_tp) + ",aresample=48000," if mm else "") + limitador
        sh(["ffmpeg", "-y", "-i", str(mix_wav), "-af", af, "-ar", "48000", "-ac", "2", str(tmp_a)])
        mix_wav.unlink()
    else:
        fc += f";{alvo}{limitador}[fim]"
        sh(["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", "[fim]", "-t", f"{total:.4f}", "-ar", "48000", "-ac", "2", str(tmp_a)])

    return tmp_a, [voz_bruta, voz]


def gancho_antes_da_vinheta(ctx, tmp_v, tmp_a, pasta):
    """Troca de lugar os dois blocos do começo: [vinheta][gancho][resto] vira [gancho][vinheta][resto]."""
    a, b = ctx.dur_intro, ctx.dur_intro + ctx.n_gancho / FPS
    v2, a2 = pasta / "_video_gancho.mp4", pasta / "_audio_gancho.wav"
    partes = [(a, b), (0, a), (b, None)]
    fv = "".join(f"[0:v]trim=start={x:.4f}" + (f":end={y:.4f}" if y else "") + f",setpts=PTS-STARTPTS[v{i}];" for i, (x, y) in enumerate(partes))
    fa = "".join(f"[1:a]atrim=start={x:.4f}" + (f":end={y:.4f}" if y else "") + f",asetpts=PTS-STARTPTS[a{i}];" for i, (x, y) in enumerate(partes))
    sh(["ffmpeg", "-y", "-i", str(tmp_v), "-i", str(tmp_a), "-filter_complex", fv + "[v0][v1][v2]concat=n=3:v=1:a=0[v]", "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", str(v2)])
    sh(["ffmpeg", "-y", "-i", str(tmp_v), "-i", str(tmp_a), "-filter_complex", fa + "[a0][a1][a2]concat=n=3:v=0:a=1[a]", "-map", "[a]",
        "-c:a", "pcm_s16le", str(a2)])
    return v2, a2


def cmd_renderizar(a):
    edl_p = Path(a.edl).resolve()
    if getattr(a, "previa", False):
        return previa(edl_p, a)
    ctx = Contexto(edl_p, rapido=a.rapido, formato=getattr(a, "formato", None))
    pasta, edl, total = ctx.pasta, ctx.edl, ctx.total
    trilha, faixa = musica_do_edl(dict(padrao(edl, "musica", {}) or {}))

    tmp_v = pasta / "_video.mp4"
    final = pasta / (edl.get("saida") or "final.mp4")
    if a.so_audio:  # refaz só o áudio, reaproveitando o vídeo já renderizado
        shutil.copy(final, tmp_v)
    else:
        avisos = render_video(ctx, edl_p, tmp_v, a.rapido, getattr(a, "processos", None) or processos_padrao())

    tmp_a, temporarios = render_audio(ctx, trilha)
    if ctx.apos_gancho:  # o render sai com a vinheta na frente; aqui o gancho passa para antes dela (vídeo e áudio)
        temporarios = [*temporarios, tmp_v, tmp_a]
        tmp_v, tmp_a = gancho_antes_da_vinheta(ctx, tmp_v, tmp_a, pasta)
    sh(["ffmpeg", "-y", "-i", str(tmp_v), "-i", str(tmp_a), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-metadata", f"comment=marca={CFG['id']}; editor=edicao-video {__version__}", "-metadata", f"artist={CFG['nome']}",
        "-shortest", "-movflags", "+faststart", str(final)])
    passo = max(total / 12, 0.1)
    sh(["ffmpeg", "-y", "-i", str(final), "-vf", f"fps=1/{passo:.3f},scale=270:-2,tile=6x2:padding=6:color=white",
        "-frames:v", "1", str(pasta / "previa.jpg")])
    for p in (tmp_v, tmp_a, *temporarios, pasta / "_whoosh.wav", pasta / "_pop.wav"):
        if p.exists():
            p.unlink()
    usados = conferir_auditoria()
    escrever_manifesto(pasta, final, edl, faixa, usados, total)
    print(f"Pronto: {final} ({total:.1f}s, {len(ctx.segs)} cortes, marca {CFG['id']}) e {pasta / 'previa.jpg'}")
    if faixa:
        print(f"Crédito da música (cole na legenda): {faixa['credito']}")
    if not a.so_audio and not getattr(a, "sem_conferencia", False):
        relatorio(ctx, final, avisos)


def previa(edl_p, a):
    """Prévia rápida para revisar o EDL: 10 quadros por segundo, só a janela pedida (--de/--ate, em segundos do vídeo
    final), com o áudio de verdade. Sai em previa.mp4, em segundos em vez de minutos."""
    ctx = Contexto(edl_p, rapido=True)
    de = max(0.0, getattr(a, "de", None) or 0.0)
    ate = min(ctx.total, getattr(a, "ate", None) or ctx.total)
    if ate <= de:
        sys.exit(f"janela vazia: --de {de} --ate {ate} (o vídeo tem {ctx.total:.1f}s)")
    t0 = time.time()
    n_de, n_ate = int(de * FPS), int(math.ceil(ate * FPS))
    acum, i0, i1 = ctx.n_intro, 0, len(ctx.segs)
    for i, s in enumerate(ctx.segs):  # só os segmentos que tocam a janela
        if acum + s["n"] <= n_de:
            i0 = i + 1
        if acum >= n_ate:
            i1 = i
            break
        acum += s["n"]
    i1 = max(i1, i0)
    tmp_v = ctx.pasta / "_previa_video.mp4"
    tr = Trecho(ctx)
    tr.render(i0, i1, tmp_v, True, i1 == len(ctx.segs), janela=(de, ate), passo=3)
    trilha, _ = musica_do_edl(dict(padrao(ctx.edl, "musica", {}) or {}))
    tmp_a, temporarios = render_audio(ctx, trilha)
    saida = ctx.pasta / "previa.mp4"
    sh(["ffmpeg", "-y", "-i", str(tmp_v), "-ss", f"{de:.3f}", "-t", f"{ate - de:.3f}", "-i", str(tmp_a),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(saida)])
    for p in (tmp_v, tmp_a, *temporarios, ctx.pasta / "_whoosh.wav", ctx.pasta / "_pop.wav"):
        if p.exists():
            p.unlink()
    print(f"Prévia: {saida} ({de:.1f}s a {ate:.1f}s, em {time.time() - t0:.1f}s). Não é o vídeo final: rode sem --previa.")


def escrever_manifesto(pasta, final, edl, faixa, usados, total):
    """manifesto.json: de que marca é o vídeo e tudo que entrou nele (para conferência e licenças).
    creditos.txt: a linha de crédito da música, quando houver."""
    from .config import RAIZ
    rel = lambda p: str(p.relative_to(RAIZ)) if RAIZ in p.parents else str(p)
    man = {"marca": CFG["id"], "nome_marca": CFG["nome"], "editor": __version__, "video": final.name,
           "duracao": round(total, 2), "arquivos": [rel(p) for p in usados],
           "musica": {k: faixa.get(k) for k in ("id", "titulo", "artista", "licenca", "credito", "pagina")} if faixa else None}
    json.dump(man, open(pasta / "manifesto.json", "w"), ensure_ascii=False, indent=1)
    cred = pasta / "creditos.txt"
    if faixa:
        cred.write_text(faixa["credito"] + "\n")
    elif cred.exists():
        cred.unlink()

