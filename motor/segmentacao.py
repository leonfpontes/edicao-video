"""Recorte da pessoa (Robust Video Matting, com MediaPipe como reserva)."""
import cv2
import numpy as np

from .config import MODELOS


class Segmentador:
    """Recorte da pessoa. Usa Robust Video Matting (rede recorrente feita para vídeo: cabelo e bordas
    limpos, estável entre quadros, e devolve a cor da frente sem o 'vazamento' do ambiente).
    Sem o modelo, cai para o MediaPipe."""

    def __init__(self):
        rvm = MODELOS / "rvm_mobilenetv3_fp32.onnx"
        self.rvm = None
        if rvm.exists():
            import onnxruntime as ort
            self.ort, self.rvm_path = ort, str(rvm)
            pref = [p for p in ("CoreMLExecutionProvider", "CUDAExecutionProvider") if p in ort.get_available_providers()]
            self.rvm = ort.InferenceSession(self.rvm_path, providers=pref + ["CPUExecutionProvider"])
            self.reset()
        else:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
            self.mp = mp
            self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=str(MODELOS / "selfie_segmenter.tflite")),
                running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True))
            self.ts = 0
        self.prev = None

    def reset(self):
        self.rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4

    def recortar(self, frame):
        """Devolve (alfa 0..1 float32 HxW, frente BGR uint8 sem vazamento de cor)."""
        if self.rvm is not None:
            h, w = frame.shape[:2]
            x = (cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255).transpose(2, 0, 1)[None]
            ratio = np.array([min(1.0, 512 / max(h, w))], np.float32)
            ent = {"src": x, "r1i": self.rec[0], "r2i": self.rec[1], "r3i": self.rec[2], "r4i": self.rec[3],
                   "downsample_ratio": ratio}
            try:
                fgr, pha, *self.rec = self.rvm.run(None, ent)
            except Exception:  # acelerador recusou o modelo: segue na CPU
                self.rvm = self.ort.InferenceSession(self.rvm_path, providers=["CPUExecutionProvider"])
                fgr, pha, *self.rec = self.rvm.run(None, ent)
            a = pha[0, 0]
            a = np.clip((a - 0.04) / 0.92, 0, 1)  # limpa resíduos quase transparentes do ambiente
            fg = (fgr[0].transpose(1, 2, 0)[..., ::-1] * 255).clip(0, 255).astype(np.uint8)
            return a, fg
        self.ts += 33
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        m = self.seg.segment_for_video(img, self.ts).confidence_masks[0].numpy_view().astype(np.float32)
        m = cv2.resize(m, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        m = np.clip((m - 0.3) / 0.4, 0, 1)
        m = m * m * (3 - 2 * m)
        m = cv2.GaussianBlur(m, (0, 0), 1.5)
        if self.prev is not None and self.prev.shape == m.shape:
            m = 0.55 * m + 0.45 * self.prev
        self.prev = m
        return m, frame

    def fechar(self):
        if self.rvm is None:
            self.seg.close()

