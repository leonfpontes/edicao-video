"""Chamadas ao ffmpeg/ffprobe e pequenas conversões."""
import json
import subprocess
import sys


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"Falhou: {' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r.stdout


def bgr(rgb):
    return (rgb[2], rgb[1], rgb[0])


def probe(path):
    out = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    return v, float(out["format"]["duration"])


def tem_audio(path):
    out = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)]))
    return any(s["codec_type"] == "audio" for s in out["streams"])


def duracao_audio(path):
    out = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path)]))
    return float(out["format"]["duration"])
