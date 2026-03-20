"""
MODNet 人像抠图模块
参考 HivisionIDPhotos 的实现
"""
import cv2
import numpy as np
import onnxruntime as ort
import os
import sys


def _resolve_hivision_path(model_path):
    """打包后禁止传入目录或 _MEIPASS，强制使用 .onnx 文件路径"""
    model_path = os.path.abspath(os.path.normpath(str(model_path)))
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', '')
        if not model_path.endswith('.onnx') or model_path.rstrip(os.sep) == meipass.rstrip(os.sep) or not os.path.isfile(model_path):
            from utils.config import get_hivision_modnet_onnx_path
            model_path = get_hivision_modnet_onnx_path()
    return model_path


class MODNetMatting:
    def __init__(self, model_path):
        model_path = _resolve_hivision_path(model_path)
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"MODNet 模型文件不存在: {model_path}")
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def process(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        ref_size = 512
        im = cv2.resize(image, (ref_size, ref_size), interpolation=cv2.INTER_AREA)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        im = im.astype(np.float32) / 255.0
        mean = np.array([0.5, 0.5, 0.5]).reshape(1, 1, 3)
        std = np.array([0.5, 0.5, 0.5]).reshape(1, 1, 3)
        im = (im - mean) / std
        im = np.transpose(im, (2, 0, 1))
        im = np.expand_dims(im, 0).astype(np.float32)
        matte = self.session.run([self.output_name], {self.input_name: im})[0][0, 0]
        matte = cv2.resize(matte, (w, h), interpolation=cv2.INTER_AREA)
        matte = (matte * 255).astype(np.uint8)
        b, g, r = cv2.split(image)
        rgba = cv2.merge([b, g, r, matte])
        return rgba
