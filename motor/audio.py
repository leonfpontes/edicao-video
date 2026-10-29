"""Áudio: efeitos sonoros gerados, loudnorm em duas passadas e medição EBU R128."""
import json
import subprocess

from .util import sh


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

