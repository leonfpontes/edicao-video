#!/usr/bin/env bash
# Instala o editor de vídeo multimarca no Mac (tudo gratuito, roda local).
# Uso: cd <pasta edicao-video> && bash setup-mac.sh
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v brew >/dev/null; then
  echo "Instale o Homebrew primeiro: https://brew.sh" && exit 1
fi
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12

PY="$(brew --prefix python@3.12)/bin/python3.12"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

mkdir -p modelos
baixa() { [ -s "modelos/$2" ] || curl -fsSL "$1" -o "modelos/$2"; }
baixa https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite selfie_segmenter.tflite
baixa https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite blaze_face_short_range.tflite
baixa https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx rvm_mobilenetv3_fp32.onnx
baixa https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn sh.rnnn

# pré-baixa o modelo do Whisper (≈ 480 MB, uma vez só)
.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

# músicas da biblioteca (≈ 230 MB, CC BY 4.0; ficam fora do Git e são conferidas por sha256)
.venv/bin/python editor.py biblioteca baixar musicas

.venv/bin/python editor.py biblioteca verificar

echo
echo "Pronto. Teste com:"
echo "  .venv/bin/python editor.py testar"
echo "  .venv/bin/python editor.py analisar ~/Movies/meu-video.mov --marca pontes_brain"
