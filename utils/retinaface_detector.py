"""RetinaFace 人脸检测器（基于ONNX）"""
import cv2
import numpy as np
import os
from utils.config import get_retinaface_onnx_path


class RetinaFaceDetector:
    def __init__(self, model_path=None):
        import sys
        if model_path is None:
            model_path = get_retinaface_onnx_path()
        model_path = os.path.abspath(os.path.normpath(model_path))
        # 打包后禁止传入目录或 _MEIPASS，强制使用 .onnx 文件路径
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', '')
            if not model_path.endswith('.onnx') or model_path.rstrip(os.sep) == meipass.rstrip(os.sep) or not os.path.isfile(model_path):
                model_path = get_retinaface_onnx_path()
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"RetinaFace 模型文件不存在: {model_path}")
        import onnxruntime as ort
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = (640, 640)

    def detect(self, image, conf_threshold=0.5):
        img_h, img_w = image.shape[:2]
        blob = self._preprocess(image)
        outputs = self.session.run(None, {self.input_name: blob})
        return self._postprocess(outputs, img_w, img_h, conf_threshold)

    def _preprocess(self, image):
        if image.ndim == 3 and image.shape[2] == 4:
            image = image[:, :, :3]
        resized = cv2.resize(image, self.input_size)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32)
        blob = (blob - 127.5) / 128.0
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return blob

    def _postprocess(self, outputs, img_w, img_h, conf_threshold):
        detections = []
        try:
            if len(outputs) >= 2:
                # bbox [1,N,4], confidence [1,N,2]（第0列背景第1列人脸）
                boxes = np.asarray(outputs[0][0])
                raw_scores = np.asarray(outputs[1][0])
                if raw_scores.ndim == 2:
                    scores = raw_scores[:, 1]
                else:
                    scores = raw_scores.ravel()
                valid_idx = scores > conf_threshold
                boxes = boxes[valid_idx]
                scores = scores[valid_idx]
                if len(boxes) > 0:
                    best_idx = np.argmax(scores)
                    box = boxes[best_idx]
                    score = float(scores[best_idx])
                    scale_x = img_w / self.input_size[0]
                    scale_y = img_h / self.input_size[1]
                    x1 = int(box[0] * scale_x)
                    y1 = int(box[1] * scale_y)
                    x2 = int(box[2] * scale_x)
                    y2 = int(box[3] * scale_y)
                    x1, x2 = min(x1, x2), max(x1, x2)
                    y1, y2 = min(y1, y2), max(y1, y2)
                    w = max(1, x2 - x1)
                    h = max(1, y2 - y1)
                    detections.append({'box': (x1, y1, w, h), 'confidence': score, 'landmarks': None})
        except Exception:
            pass
        return detections
