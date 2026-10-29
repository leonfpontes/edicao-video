#!/usr/bin/env python3
"""Monta a biblioteca de efeitos sonoros (biblioteca/sons/): arquivos .ogg, catalogo.json e CREDITOS.md.

Uso (da raiz do repositório): .venv/bin/python ferramentas/montar_sons.py

Duas origens, ambas livres para uso comercial:

- gravações reais **CC0 1.0** do OpenGameArt (Kenney, qubodup, starninjas…), baixadas da página oficial e conferidas
  por sha256 (se a fonte mudar o arquivo, o script para);
- efeitos **próprios**, desenhados aqui por síntese (whooshes, risers, impactos, brilho de vidro). Efeito sonoro
  curto é design de som, não música: a regra "nunca sintetize música" continua valendo.

Cada som sai cortado, com fade, nivelado pela janela de 50 ms mais forte (todos com a mesma força percebida) e com
pico máximo de -1 dBFS. O campo `ataque` guarda o instante do pico: o motor alinha esse ponto com o corte ou com a
palavra (o whoosh "passa" exatamente no corte; o riser "chega" exatamente na palavra).
"""
import hashlib
import io
import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "biblioteca" / "sons"
CACHE = Path.home() / ".cache" / "edicao-video" / "sons"
SR = 48000
OGA = "https://opengameart.org/sites/default/files/"
CC0 = "CC0 1.0"

# fonte: (arquivo no OpenGameArt, sha256, autor, página)
FONTES = {
    "kenney-interface": ("kenney_interfaceSounds.zip", "f2193d072726d6758a5f7871b2dcc54dcce0d5c35c6f0a62f92549b327c81232",
                         "Kenney (kenney.nl)", "https://opengameart.org/content/interface-sounds"),
    "kenney-ui": ("UI_SFX_Set.zip", "66026b9e39859b85964dbb3ee7a2d1fc46a6a406bb3e97c8b0defee0e25fb369",
                  "Kenney (kenney.nl)", "https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks"),
    "kenney-casino": ("kenney_casino-audio.zip", "f36250766ac5bc378c13708ddf12a23a8e54a3251f8d482c7536e51b5dbafa18",
                      "Kenney (kenney.nl)", "https://opengameart.org/content/54-casino-sound-effects-cards-dice-chips"),
    "kenney-scifi": ("sci-fi_sounds.zip", "119340f351a5098ad814f78719438c0da355a9ce8a4c8a3af6a8d48aa3d49e04",
                     "Kenney (kenney.nl)", "https://opengameart.org/content/sci-fi-sounds"),
    "rubberduck-100": ("100-CC0-SFX_0.zip", "a5c135878c132f1c59cca54e60061c296cd0ac27ad031ca2c41b8cd5cab3c706",
                       "rubberduck", "https://opengameart.org/content/100-cc0-sfx"),
    "qubodup-swosh": ("qubodup-timehitwind.zip", "8ed235b84ed19a5a72c47771e33d347406e67750b2a6ba72a2f558e64cc6205e", "qubodup", "https://opengameart.org/content/wind-hit-time-morph"),
    "pyrano-whoosh": ("whoosh2_0.wav", "d3fbff5bb78b289af16b2dfa29083f07ef83b0cbaff4514c48dfda16d082b468",
                      "Pyranostudios", "https://opengameart.org/content/air-whoosh"),
    "starninjas-livro": ("book_flips_-_starninjas.zip", "0ff49c3677ea0e64544aeda3a0aa2ce71ee5d42b266da9e54421252a5ca5f20f",
                         "StarNinjas", "https://opengameart.org/content/10-book-page-flips"),
    "starninjas-ding": ("ding_-_starninjas.zip", "2da62025a7eb90c91a62f68b6b25a7c54e632ccb82bca9446f6eda7110a6ebe2",
                        "StarNinjas", "https://opengameart.org/content/4-metal-dingsrings"),
    "frosty-alerta": ("alert.wav", "d275225f0d68e14331fade06451e3ce3a0f6665219936553968300557ff82666",
                      "Frosty Ham", "https://opengameart.org/content/alertnotification-sound"),
    "unicae-teclado": ("unicae_games_keyboard_soundpack_1_0.zip", "935eae2fa5c3742eacdd38c4ea0e9047f3887faa0701996498492c256db1b351",
                       "Unicae Games", "https://opengameart.org/content/keyboard-soundpack-1-typing-and-single-keystrokes"),
    "antum-lapis": ("pencil.zip", "e944c3a6261b4eda793247e90e0905a9b3a2bec48a4fab44fdd63a08109cd28a",
                    "Jordan Irwin (AntumDeluge)", "https://opengameart.org/content/pencil-sounds"),
    "cassie-maquina": ("typewriter1.wav", "f860766aa7922afbf1523ea1a41504c64f3f6362fa03a60b6497c75c1d0d0344", "Cassie (Orbit Games)", "https://opengameart.org/content/typewriter-sounds"),
}

# id, categoria, fonte (chave de FONTES ou "propria"), arquivo dentro do zip, (início, duração) em s ou None,
# tags (pt), quando usar, volume_db (ajuste fino de mix sobre o nível comum)
CURADORIA = [
    # ── transições (whooshes reais e desenhados: o motor alterna as variações para o ouvido não cansar)
    ("whoosh-ar", "transicao", "qubodup-swosh", "qubodup-megaswosh1.wav", None, ["whoosh", "ar", "rápido", "corte"],
     "Virada de assunto com empurrão lateral (push/whip). Passa exatamente no corte.", -7),
    ("whoosh-vento", "transicao", "qubodup-swosh", "qubodup-megaswosh2.wav", None, ["whoosh", "vento", "corte"],
     "Variação do whoosh de transição, um pouco mais encorpada.", -7),
    ("whoosh-curto", "transicao", "qubodup-swosh", "60009__qubodup__swosh_22.flac", None, ["whoosh", "curto", "swish"],
     "Swish curto e seco: entrada de título, troca rápida.", -9),
    ("whoosh-lento", "transicao", "qubodup-swosh", "qubodup-slomo1.wav", None, ["whoosh", "lento", "câmera lenta"],
     "Passagem lenta, câmera lenta, mergulho calmo.", -8),
    ("whoosh-sopro", "transicao", "pyrano-whoosh", "", (0.8, 1.05), ["whoosh", "sopro", "suave", "ar"],
     "Sopro de ar macio para fusão, abertura e fim de vídeo.", -6),
    ("whoosh-suave", "transicao", "propria", "", None, ["whoosh", "suave", "elegante", "pan"],
     "Whoosh desenhado, limpo e elegante, atravessando da esquerda para a direita.", -7),
    ("whoosh-rapido", "transicao", "propria", "", None, ["whoosh", "rápido", "whip", "agudo"],
     "Whip pan: whoosh curto e brilhante para o chicote de câmera.", -8),
    ("whoosh-profundo", "transicao", "propria", "", None, ["whoosh", "grave", "mergulho", "zoom"],
     "Mergulho com corpo grave: transição zoom, entrada do CTA, mergulho da vinheta.", -6),
    ("whoosh-giro", "transicao", "propria", "", None, ["whoosh", "giro", "rotação", "spin"],
     "Rotação acelerando: transição de giro 3D.", -7),
    ("deslizar", "transicao", "kenney-casino", "Audio/card-slide-1.ogg", None, ["swipe", "deslizar", "cartão", "slide"],
     "Cartão deslizando na mesa: slide para cima, lista, próximo passo.", -6),
    ("pagina", "transicao", "starninjas-livro", "book_flip.1.ogg", None, ["página", "papel", "virar", "livro"],
     "Virar de página: próximo capítulo, rasgo de papel, 'agora a parte dois'.", -6),
    ("papel-rasgo", "transicao", "rubberduck-100", "paper_01.ogg", None, ["papel", "rasgo", "amassar", "colagem"],
     "Papel sendo amassado e rasgado: transição rasgo e estética de colagem.", -5),
    ("vidro-shimmer", "transicao", "propria", "", None, ["vidro", "brilho", "cristal", "shimmer", "liquid glass"],
     "Cintilar de cristal: transição de vidro, brilho, revelação elegante.", -9),
    # ── tensão e impacto
    ("riser-curto", "tensao", "propria", "", None, ["riser", "subida", "tensão", "antes da revelação"],
     "Subida de 1,2 s que chega no ápice exatamente na palavra (ancore na palavra da revelação).", -8),
    ("riser-longo", "tensao", "propria", "", None, ["riser", "subida", "suspense", "build-up"],
     "Subida longa de 2,5 s para gancho e grande revelação.", -9),
    ("reverso", "tensao", "propria", "", None, ["reverso", "sucção", "swell", "antes do corte"],
     "Prato ao contrário: puxa para o próximo momento; bom antes de um corte seco ou flash.", -8),
    ("impacto-grave", "impacto", "propria", "", None, ["impacto", "boom", "sub", "drop", "peso"],
     "Batida grave cinematográfica: número forte, conclusão, 'é isso'.", -6),
    ("impacto-seco", "impacto", "rubberduck-100", "hit_03.ogg", None, ["impacto", "batida", "seco", "soco"],
     "Batida seca e curta: carimbo, xis, 'não faça isso'.", -9),
    ("sub-boom", "impacto", "kenney-scifi", "Audio/lowFrequency_explosion_000.ogg", (0.0, 1.2), ["boom", "sub", "grave", "explosão"],
     "Grave longo e profundo, discreto: revelação grande, entrada da vinheta.", -8),
    # ── interface (UI): texto, cartões, listas
    ("pop-limpo", "interface", "propria", "", None, ["pop", "bolha", "entrada", "texto"],
     "Pop limpo e curto: entrada de destaque, rótulo, item de lista.", -10),
    ("pop-bolha", "interface", "rubberduck-100", "plop_01.ogg", None, ["pop", "bolha", "plop", "orgânico"],
     "Pop orgânico de bolha: objeto 3D surgindo, emoji, reação.", -11),
    ("clique", "interface", "kenney-interface", "Audio/click_002.ogg", None, ["clique", "mouse", "botão", "ui"],
     "Clique de botão: cursor, seleção, 'clica aqui'.", -10),
    ("tique", "interface", "kenney-interface", "Audio/tick_002.ogg", None, ["tique", "tick", "item", "lista"],
     "Tique curto: item de checklist marcado, contagem.", -12),
    ("toque-vidro", "interface", "kenney-interface", "Audio/glass_002.ogg", None, ["vidro", "toque", "cristal", "ui"],
     "Toque de vidro: cartão de vidro (liquid glass) aparecendo.", -10),
    ("ui-sobe", "interface", "kenney-interface", "Audio/maximize_001.ogg", None, ["subir", "abrir", "entrada", "ui"],
     "Tom que sobe: painel abrindo, Leo entrando, barra enchendo.", -12),
    ("ui-desce", "interface", "kenney-interface", "Audio/minimize_001.ogg", None, ["descer", "fechar", "saída", "ui"],
     "Tom que desce: painel fechando, saída de elemento.", -12),
    ("interruptor", "interface", "kenney-ui", "switch7.wav", None, ["interruptor", "switch", "liga", "toggle"],
     "Interruptor: liga/desliga, antes e depois, 'virou a chave'.", -10),
    ("rolagem", "interface", "kenney-interface", "Audio/scroll_002.ogg", None, ["rolagem", "scroll", "contagem", "roleta"],
     "Catraca de rolagem: contador subindo, barra carregando.", -13),
    ("notificacao", "interface", "frosty-alerta", "", None, ["notificação", "alerta", "mensagem", "celular"],
     "Notificação de celular: cartão de notificação, mensagem de cliente.", -8),
    ("glitch", "interface", "propria", "", None, ["glitch", "falha", "digital", "bug"],
     "Falha digital curta: efeito glitch, erro, 'bug no processo'.", -12),
    # ── marcações, acerto e erro
    ("acerto", "marcacao", "kenney-interface", "Audio/confirmation_002.ogg", None, ["acerto", "certo", "confirmação", "sucesso"],
     "Arpejo de confirmação: check, aprovado, 'faça assim'.", -11),
    ("erro", "marcacao", "kenney-interface", "Audio/error_006.ogg", None, ["erro", "errado", "não", "alerta"],
     "Buzina suave de erro: xis, mito, 'não faça isso'.", -13),
    ("ding", "marcacao", "starninjas-ding", "ding.1.ogg", (0.0, 1.6), ["ding", "sino", "ideia", "insight"],
     "Ding metálico: insight, ideia, 'percebe?'.", -11),
    ("lapis", "marcacao", "antum-lapis", "flac/pencil_write.flac", (0.0, 0.9), ["lápis", "escrever", "rabisco", "mão"],
     "Lápis escrevendo: círculo, sublinhado, seta e marca-texto desenhados à mão.", -6),
    ("brilho", "marcacao", "propria", "", None, ["brilho", "faísca", "mágico", "valioso"],
     "Faíscas cintilando: algo valioso, novo, premium.", -10),
    # ── objetos e cotidiano de trabalho
    ("teclado", "objetos", "unicae-teclado", "Human Typing/human_vel-003.wav", (0.4, 1.8), ["teclado", "digitar", "computador", "escrever"],
     "Digitação em teclado: texto se escrevendo, prompt, e-mail, 'eu escrevi…'.", -10),
    ("maquina-escrever", "objetos", "cassie-maquina", "", None, ["máquina de escrever", "texto", "roteiro", "retrô"],
     "Máquina de escrever: título letra a letra, roteiro, citação.", -9),
    ("moedas", "objetos", "kenney-casino", "Audio/chips-stack-3.ogg", None, ["moedas", "dinheiro", "fichas", "custo"],
     "Fichas/moedas empilhando: dinheiro, custo, orçamento, ROI.", -8),
]

PROPRIAS = {}


def propria(fn):
    PROPRIAS[fn.__name__.replace("_", "-")] = fn
    return fn


# ───────────────────────────── síntese (efeitos próprios) ─────────────────────────────

def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _ruido(n, rng, cor="rosa"):
    x = rng.standard_normal(n)
    if cor == "branco":
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[1:] /= np.sqrt(f[1:] / 100)  # 1/f: ruído rosa, mais natural que o branco
    X[0] = 0
    y = np.fft.irfft(X, n)
    return y / (np.abs(y).max() + 1e-9)


def _filtro_movel(x, centro, largura_oct=1.0):
    """Passa-faixa que se move no tempo (centro em Hz, um valor por amostra), via STFT."""
    n, hop = 1024, 256
    pad = np.concatenate([np.zeros(n), x, np.zeros(n)])
    jan = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / SR)
    lf = np.log2(np.maximum(f, 1))
    out = np.zeros_like(pad)
    norm = np.zeros_like(pad)
    cen = np.concatenate([np.full(n, centro[0]), centro, np.full(n, centro[-1])])
    for i in range(0, len(pad) - n, hop):
        quadro = np.fft.rfft(pad[i:i + n] * jan)
        c = np.log2(max(cen[i + n // 2], 20))
        ganho = np.exp(-0.5 * ((lf - c) / (largura_oct / 2)) ** 2)
        out[i:i + n] += np.fft.irfft(quadro * ganho, n) * jan
        norm[i:i + n] += jan ** 2
    return (out / np.maximum(norm, 1e-6))[n:n + len(x)]


def _sino(t, f0, decai, rng=None):
    """Sino por FM (timbre de cristal/metal)."""
    mod = np.exp(-t * decai * 1.5) * 2.2
    return np.sin(2 * np.pi * f0 * t + mod * np.sin(2 * np.pi * f0 * 3.5 * t)) * np.exp(-t * decai)


def _reverb(x, tempo=0.6, mistura=0.25, rng=None):
    rng = rng or np.random.default_rng(7)
    ir_t = _t(tempo * 1.5)
    ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 6.9 / tempo)
    ir = np.convolve(ir, np.ones(8) / 8, "same")  # tira o chiado: cauda mais escura
    ir /= np.sqrt((ir ** 2).sum())
    n = len(x) + len(ir)
    molhado = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:n]
    seco = np.concatenate([x, np.zeros(len(ir))])
    return seco * (1 - mistura) + molhado * mistura * (np.abs(seco).max() / (np.abs(molhado).max() + 1e-9))


def _estereo(m, pan):
    """pan -1 (esquerda) a 1 (direita), um valor por amostra ou escalar (potência constante)."""
    a = (np.asarray(pan) + 1) * np.pi / 4
    return np.stack([m * np.cos(a), m * np.sin(a)], 1)


def _whoosh(dur, f_ini, f_pico, f_fim, pico=0.55, largura=1.1, pan=(-0.7, 0.7), semente=1, grave=0.0):
    rng = np.random.default_rng(semente)
    t = _t(dur)
    p = t / dur
    sobe = np.clip(p / pico, 0, 1)
    desce = np.clip((p - pico) / (1 - pico), 0, 1)
    centro = np.where(p < pico, f_ini * (f_pico / f_ini) ** sobe, f_pico * (f_fim / f_pico) ** desce)
    som = _filtro_movel(_ruido(len(t), rng), centro, largura)
    env = np.where(p < pico, sobe ** 2.2, (1 - desce) ** 1.6)
    som = som * env
    if grave:
        corpo = np.sin(2 * np.pi * np.cumsum(55 + 40 * env) / SR) * env ** 3
        som = som / (np.abs(som).max() + 1e-9) + grave * corpo
    return _estereo(som, np.interp(p, [0, 1], pan))


@propria
def whoosh_suave():
    return _whoosh(0.75, 250, 2400, 500, 0.55, 1.2, (-0.75, 0.75), 11)


@propria
def whoosh_rapido():
    return _whoosh(0.38, 700, 5200, 1800, 0.5, 1.0, (-0.9, 0.9), 12)


@propria
def whoosh_profundo():
    return _whoosh(0.95, 110, 1300, 180, 0.6, 1.4, (-0.3, 0.3), 13, grave=0.55)


@propria
def whoosh_giro():
    t = _t(0.8)
    p = t / 0.8
    base = _whoosh(0.8, 300, 2600, 600, 0.6, 1.1, (0, 0), 14)[:, 0] * np.sqrt(2)
    fase = 2 * np.pi * np.cumsum(3 + 22 * p ** 2) / SR  # gira cada vez mais rápido
    am = 0.55 + 0.45 * np.sin(fase)
    return _estereo(base * am, 0.8 * np.sin(fase + 1.2))


@propria
def vidro_shimmer():
    rng = np.random.default_rng(21)
    t = _t(1.3)
    m = np.zeros(len(t))
    for k in range(16):
        ini = 0.02 + 0.55 * (k / 16) ** 1.3 + rng.uniform(0, 0.04)
        f0 = rng.choice([2093, 2349, 2637, 3136, 3520, 4186, 4699])
        tt = np.clip(t - ini, 0, None)
        m += _sino(tt, f0 * rng.uniform(0.995, 1.005), 9) * (t >= ini) * (0.4 + 0.6 * (1 - k / 16))
    ar = _filtro_movel(_ruido(len(t), rng, "branco"), np.full(len(t), 7000), 1.5) * np.exp(-((t - 0.35) / 0.25) ** 2) * 0.25
    m = m / (np.abs(m).max() + 1e-9) + ar
    m = _reverb(m, 0.9, 0.35)
    return _estereo(m, np.sin(np.arange(len(m)) / SR * 5) * 0.5)


@propria
def brilho():
    rng = np.random.default_rng(22)
    t = _t(0.9)
    m = np.zeros(len(t))
    for k in range(9):
        ini = rng.uniform(0, 0.45)
        tt = np.clip(t - ini, 0, None)
        m += _sino(tt, rng.uniform(3500, 6500), 14) * (t >= ini)
    m = _reverb(m / (np.abs(m).max() + 1e-9), 0.6, 0.3)
    return _estereo(m, np.interp(np.arange(len(m)), [0, len(m)], [-0.5, 0.5]))


def _riser(dur, semente):
    rng = np.random.default_rng(semente)
    t = _t(dur)
    p = t / dur
    centro = 250 * (9000 / 250) ** (p ** 1.4)
    ruido = _filtro_movel(_ruido(len(t), rng), centro, 1.6)
    ruido /= np.abs(ruido).max() + 1e-9
    f = 110 * 2 ** (2 * p ** 1.2)  # duas oitavas subindo
    fase = 2 * np.pi * np.cumsum(f) / SR
    tom = 0.35 * (np.sin(fase) + 0.4 * np.sin(2 * fase + 0.3) + 0.2 * np.sin(1.5 * fase))
    tremolo = 1 + 0.25 * np.sin(2 * np.pi * np.cumsum(4 + 18 * p) / SR)
    env = p ** 2.4
    m = (ruido + tom) * env * tremolo
    m[-int(0.012 * SR):] *= np.linspace(1, 0, int(0.012 * SR))  # termina seco, no ápice
    return _estereo(m, 0.6 * np.sin(2 * np.pi * 0.7 * t))


@propria
def riser_curto():
    return _riser(1.2, 31)


@propria
def riser_longo():
    return _riser(2.5, 32)


@propria
def reverso():
    rng = np.random.default_rng(33)
    t = _t(1.0)
    prato = _filtro_movel(_ruido(len(t), rng, "branco"), np.full(len(t), 6500), 2.2) * np.exp(-t * 4.5)
    prato = _reverb(prato / (np.abs(prato).max() + 1e-9), 0.5, 0.3)[:len(t)]
    m = prato[::-1].copy()
    m[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return _estereo(m, np.linspace(-0.4, 0.4, len(m)))


@propria
def impacto_grave():
    rng = np.random.default_rng(34)
    t = _t(1.4)
    f = 38 + 110 * np.exp(-t * 22)  # queda de afinação (808)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    sub = np.tanh(sub * 1.8) / np.tanh(1.8)
    clique = _filtro_movel(_ruido(len(t), rng, "branco"), np.full(len(t), 2500), 2.5) * np.exp(-t * 90)
    corpo = _filtro_movel(_ruido(len(t), rng), np.full(len(t), 160), 1.5) * np.exp(-t * 9)
    m = sub + 0.5 * clique / (np.abs(clique).max() + 1e-9) + 0.5 * corpo / (np.abs(corpo).max() + 1e-9)
    m = _reverb(m, 1.0, 0.18)[:len(t)]
    return _estereo(m, 0.0)


@propria
def glitch():
    rng = np.random.default_rng(35)
    t = _t(0.42)
    m = np.zeros(len(t))
    pos = 0
    while pos < len(t) - int(0.02 * SR):
        n = int(rng.uniform(0.015, 0.045) * SR)
        tt = np.arange(n) / SR
        if rng.random() < 0.5:  # pedaço de tom quadrado "quebrado"
            pedaco = np.sign(np.sin(2 * np.pi * rng.choice([180, 330, 660, 1320, 2640]) * tt))
        else:  # rajada de ruído com taxa reduzida (bitcrush)
            passo = int(rng.integers(6, 40))
            pedaco = np.repeat(rng.standard_normal(n // passo + 1), passo)[:n]
        m[pos:pos + n] = pedaco * rng.uniform(0.4, 1.0) * (rng.random() > 0.2)
        pos += n + int(rng.uniform(0, 0.012) * SR)
    m = np.round(m * 6) / 6 * np.exp(-t * 2.5)
    return _estereo(m, np.repeat(rng.uniform(-0.6, 0.6, len(t) // 1200 + 1), 1200)[:len(t)])


@propria
def pop_limpo():
    t = _t(0.14)
    f = 260 + 900 * np.exp(-t * 55)
    m = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 32)
    m[:int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    return _estereo(_reverb(m, 0.25, 0.12)[:len(t) + int(0.08 * SR)], 0.0)


# ───────────────────────────── processamento ─────────────────────────────

def baixar(fonte):
    arq, sha, _, _ = FONTES[fonte]
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / arq
    if not p.exists():
        req = urllib.request.Request(OGA + urllib.request.quote(arq), headers={"User-Agent": "edicao-video/2 (+biblioteca de sons)"})
        p.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    dado = p.read_bytes()
    if dado[:15].lower().startswith(b"<!doctype") or dado[:5] == b"<html":
        p.unlink()
        sys.exit(f"{fonte}: a fonte devolveu uma página, não o arquivo ({OGA + arq})")
    if sha and hashlib.sha256(dado).hexdigest() != sha:
        sys.exit(f"{fonte}: o arquivo baixado não confere com o sha256 da curadoria (a fonte mudou?)")
    return dado


def decodificar(dado):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", "-", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       input=dado, capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).astype(np.float64)


def bruto(som):
    sid, _, fonte, interno, corte = som[:5]
    if fonte == "propria":
        x = PROPRIAS[sid]()
    else:
        dado = baixar(fonte)
        if interno:
            with zipfile.ZipFile(io.BytesIO(dado)) as z:
                dado = z.read(interno)
        x = decodificar(dado)
    if corte:
        a, d = corte
        x = x[int(a * SR):int((a + d) * SR)]
    return x


def acabar(x):
    """Corta silêncio, faz fades, nivela pela janela de 50 ms mais forte (-17 dBFS RMS) e limita o pico a -1 dBFS.
    Devolve (áudio, instante do pico em s)."""
    m = np.abs(x).max(1)
    lim = m.max() * 10 ** (-50 / 20)
    ativos = np.nonzero(m > lim)[0]
    x = x[max(ativos[0] - int(0.003 * SR), 0):ativos[-1] + int(0.02 * SR)]
    fi, fo = int(0.003 * SR), min(int(0.08 * SR), len(x) // 6)
    x[:fi] *= np.linspace(0, 1, fi)[:, None]
    x[-fo:] *= np.linspace(1, 0, fo)[:, None]
    jan = int(0.05 * SR)
    energia = np.convolve((x ** 2).mean(1), np.ones(jan) / jan, "same")
    rms = np.sqrt(energia.max())
    x *= 10 ** (-17 / 20) / max(rms, 1e-9)
    pico = np.abs(x).max()
    if pico > 10 ** (-1 / 20):
        x *= 10 ** (-1 / 20) / pico
    return x, float(np.argmax(energia) / SR)


def gravar_ogg(x, destino):
    pcm = np.clip(x, -1, 1).astype(np.float32).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "libvorbis", "-q:a", "6", str(destino)], input=pcm, check=True)


def main():
    (DEST / "arquivos").mkdir(parents=True, exist_ok=True)
    itens, creditos = [], {}
    for som in CURADORIA:
        sid, cat, fonte, _, _, tags, usos, vol = som
        x, ataque = acabar(bruto(som))
        destino = DEST / "arquivos" / f"{sid}.ogg"
        gravar_ogg(x, destino)
        it = {"id": sid, "categoria": cat, "tags": tags, "usos": usos, "arquivo": f"arquivos/{sid}.ogg",
              "duracao": round(len(x) / SR, 3), "ataque": round(ataque, 3), "volume_db": vol}
        if fonte == "propria":
            it.update(fonte="Própria (ferramentas/montar_sons.py)", licenca="Própria", credito="Leonardo Pontes / edicao-video")
        else:
            arq, _, autor, pagina = FONTES[fonte]
            it.update(fonte=f"OpenGameArt: {autor}", licenca=CC0, credito=f"{autor} (CC0)", url=pagina)
            creditos.setdefault((autor, pagina), []).append(sid)
        itens.append(it)
        print(f"  {sid:18s} {it['duracao']:5.2f}s  ataque {it['ataque']:.2f}s  {it['licenca']}")
    (DEST / "catalogo.json").write_text(json.dumps({
        "versao": 1, "observacao": "Gerado por ferramentas/montar_sons.py. Arquivos em biblioteca/sons/arquivos/ (no Git).",
        "itens": itens}, ensure_ascii=False, indent=1) + "\n")
    linhas = ["# Créditos dos efeitos sonoros", "",
              "Todos livres para uso comercial. Gravações **CC0 1.0** (domínio público: crédito opcional, deixado aqui por",
              "cortesia) e efeitos **próprios**, desenhados por síntese em `ferramentas/montar_sons.py`.", "",
              "| Autor | Fonte | Sons |", "|---|---|---|"]
    for (autor, pagina), ids in sorted(creditos.items()):
        linhas.append(f"| {autor} | [{pagina.rsplit('/', 1)[-1]}]({pagina}) | {', '.join(f'`{i}`' for i in ids)} |")
    proprios = [s[0] for s in CURADORIA if s[2] == "propria"]
    linhas += ["", f"Próprios ({len(proprios)}): " + ", ".join(f"`{i}`" for i in proprios) + ".", ""]
    (DEST / "CREDITOS.md").write_text("\n".join(linhas))
    print(f"{len(itens)} sons em {DEST}")


if __name__ == "__main__":
    main()
