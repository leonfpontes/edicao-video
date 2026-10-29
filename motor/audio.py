"""Áudio: efeitos sonoros (da biblioteca ou gerados), loudnorm em duas passadas e medição EBU R128."""
import json
import subprocess

from .marca import CFG
from .util import sh

# Sons padrão quando a marca usa a biblioteca de sons ("sons": {"modo": "biblioteca"} no marca.json).
# Listas alternam a cada uso (whoosh repetido cansa o ouvido); a marca pode sobrescrever qualquer chave.
SONS_PADRAO = {
    "transicoes": {
        "push": ["whoosh-ar", "whoosh-suave", "whoosh-vento"],
        "whip": ["whoosh-rapido", "whoosh-curto"],
        "zoom": ["whoosh-profundo"],
        "slide": ["deslizar"],
        "flash": ["reverso"],
        "dissolve": ["whoosh-sopro"],
        "fade": ["whoosh-sopro"],
        "giro": ["whoosh-giro"],
        "rasgo": ["papel-rasgo", "pagina"],
        "vidro": ["vidro-shimmer"],
        "luz": ["whoosh-sopro", "whoosh-lento"],
    },
    "elementos": {"titulo": "whoosh-curto", "destaque": "pop-limpo", "objeto3d": "pop-bolha", "leo": "ui-sobe",
                  "imagem": "deslizar"},
    "vinheta": {"abertura": "whoosh-suave", "ponto": "toque-vidro", "mergulho": "whoosh-profundo"},
    "cta": "whoosh-profundo",
}


def modo_sons():
    """"biblioteca" (sons gravados e desenhados de biblioteca/sons/) ou "gerado" (o whoosh e o pop sintéticos de antes)."""
    return (CFG.get("sons") or {}).get("modo", "gerado")


def som_padrao(grupo, chave=None, n=0):
    """Id do som padrão de um papel (ex.: grupo "transicoes", chave "push"), com a variação n."""
    cfg = dict(SONS_PADRAO)
    for g, v in (CFG.get("sons") or {}).items():
        cfg[g] = dict(cfg.get(g, {}), **v) if isinstance(v, dict) and isinstance(cfg.get(g), dict) else v
    v = cfg.get(grupo)
    if chave is not None:
        v = v.get(chave) if isinstance(v, dict) else None
    if isinstance(v, list):
        return v[n % len(v)] if v else None
    return v


def mixar_eventos(eventos, idx0):
    """Monta o trecho do filter_complex que posiciona os sons. eventos: [(início em s, caminho, ganho em dB)].
    idx0: índice da primeira entrada "-i" dos sons. Devolve (entradas, filtro, rótulos)."""
    por_arq = {}
    for ini, cam, g in eventos:
        por_arq.setdefault(str(cam), []).append((ini, g))
    ins, fc, rot = [], "", []
    for k, (cam, evs) in enumerate(por_arq.items()):
        idx = idx0 + k
        ins += ["-i", cam]
        fc += f";[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,asplit={len(evs)}" + "".join(f"[s{k}_{i}]" for i in range(len(evs)))
        for i, (ini, g) in enumerate(evs):
            ms = int(max(ini, 0) * 1000)
            fc += f";[s{k}_{i}]volume={g:.1f}dB,adelay={ms}|{ms}[sd{k}_{i}]"
            rot.append(f"[sd{k}_{i}]")
    return ins, fc, rot


def gerar_sfx(pasta):
    wh, pop = pasta / "_whoosh.wav", pasta / "_pop.wav"
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.45:c=pink:a=0.6:r=48000",
        "-af", "highpass=f=250,lowpass=f=6000,afade=t=in:d=0.25:curve=exp,afade=t=out:st=0.25:d=0.2,volume=0.16",
        "-ac", "1", str(wh)])
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc='0.5*sin(2*PI*(260+900*exp(-40*t))*t)*exp(-28*t)':d=0.16:s=48000",
        "-af", "volume=0.18", "-ac", "1", str(pop)])
    return wh, pop


def medir_loudnorm(arq, alvo, tp):
    """1ª passada do loudnorm. Devolve None se o áudio for silêncio (nada a normalizar)."""
    med = subprocess.run(["ffmpeg", "-i", str(arq), "-af", f"loudnorm=I={alvo}:TP={tp}:LRA=11:print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(med[med.rindex("{"):med.rindex("}") + 1])
    return m if float(m["input_i"]) > -60 else None


def loudnorm_2a(m, alvo, tp):
    """2ª passada (linear, com a medida da 1ª): sobe ou desce o volume sem comprimir."""
    return (f"loudnorm=I={alvo}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def medir_audio(video):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    resumo = r[r.rfind("Summary:"):]
    num = lambda chave: float(resumo.split(chave)[1].split()[0])
    return num("I:"), num("Peak:")

