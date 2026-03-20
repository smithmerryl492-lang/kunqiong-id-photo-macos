"""人脸检测工具 - 支持 MTCNN 和 RetinaFace"""
import numpy as np
import cv2
import os
import sys

try:
    from mtcnnruntime import MTCNN
except ImportError:
    MTCNN = None

try:
    from utils.retinaface_detector import RetinaFaceDetector
except ImportError:
    RetinaFaceDetector = None

_mtcnn_detector = None
_retinaface_detector = None


def detect_face_mtcnn(image: np.ndarray, scale: int = 2):
    if MTCNN is None:
        return None
    global _mtcnn_detector
    if _mtcnn_detector is None:
        # 打包后 mtcnnruntime 的 __file__ 可能不在 _MEIPASS，强制权重路径为 _MEIPASS/mtcnnruntime/weights
        if getattr(sys, 'frozen', False):
            _mei = getattr(sys, '_MEIPASS', '')
            if _mei:
                import mtcnnruntime.detector as _det
                _base = os.path.join(_mei, 'mtcnnruntime', 'weights')
                _det.MTCNN._MTCNN__BASE_DIR = _base
                _det.MTCNN._MTCNN__PNET = os.path.join(_base, 'pnet.onnx')
                _det.MTCNN._MTCNN__RNET = os.path.join(_base, 'rnet.onnx')
                _det.MTCNN._MTCNN__ONET = os.path.join(_base, 'onet.onnx')
        _mtcnn_detector = MTCNN()
    h, w = image.shape[:2]
    scaled_image = cv2.resize(image, (w // scale, h // scale), interpolation=cv2.INTER_AREA)
    faces, landmarks = _mtcnn_detector.detect(scaled_image, thresholds=[0.8, 0.8, 0.8])
    if len(faces) != 1:
        faces, landmarks = _mtcnn_detector.detect(image)
        scale = 1
    else:
        faces[0] = faces[0] * scale
        landmarks[0] = landmarks[0] * scale
    if len(faces) != 1:
        return None
    left, top, right, bottom = faces[0][0], faces[0][1], faces[0][2], faces[0][3]
    width = right - left + 1
    height = bottom - top + 1
    landmarks_flat = landmarks[0]
    left_eye = np.array([landmarks_flat[0], landmarks_flat[5]])
    right_eye = np.array([landmarks_flat[1], landmarks_flat[6]])
    dy = right_eye[1] - left_eye[1]
    dx = right_eye[0] - left_eye[0]
    roll_angle = np.degrees(np.arctan2(dy, dx))
    return {'rectangle': (int(left), int(top), int(width), int(height)), 'roll_angle': roll_angle, 'landmarks': landmarks_flat}


def detect_face_opencv(image: np.ndarray):
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) != 1:
        return None
    x, y, w, h = faces[0]
    return {'rectangle': (int(x), int(y), int(w), int(h)), 'roll_angle': 0.0}


def detect_face_retinaface(image: np.ndarray):
    if RetinaFaceDetector is None:
        return None
    global _retinaface_detector
    if _retinaface_detector is None:
        try:
            _retinaface_detector = RetinaFaceDetector()
        except Exception:
            return None
    try:
        detections = _retinaface_detector.detect(image, conf_threshold=0.5)
        if len(detections) == 0:
            return None
        det = detections[0]
        x, y, w, h = det['box']
        landmarks = det.get('landmarks')
        roll_angle = 0.0
        if landmarks is not None and len(landmarks) >= 2:
            left_eye = np.array(landmarks[0])
            right_eye = np.array(landmarks[1])
            dy = right_eye[1] - left_eye[1]
            dx = right_eye[0] - left_eye[0]
            roll_angle = np.degrees(np.arctan2(dy, dx))
        return {'rectangle': (int(x), int(y), int(w), int(h)), 'roll_angle': roll_angle, 'landmarks': landmarks}
    except Exception:
        return None


def detect_face(image: np.ndarray, method: str = 'auto'):
    if method == 'mtcnn' and MTCNN is not None:
        face_info = detect_face_mtcnn(image)
        if face_info is not None:
            face_info['method'] = 'MTCNN'
            return face_info
    elif method == 'retinaface' and RetinaFaceDetector is not None:
        face_info = detect_face_retinaface(image)
        if face_info is not None:
            face_info['method'] = 'RetinaFace'
            return face_info
    elif method == 'opencv':
        face_info = detect_face_opencv(image)
        if face_info is not None:
            face_info['method'] = 'OpenCV'
            return face_info
    elif method == 'auto':
        if MTCNN is not None:
            face_info = detect_face_mtcnn(image)
            if face_info is not None:
                face_info['method'] = 'MTCNN'
                return face_info
        if RetinaFaceDetector is not None:
            face_info = detect_face_retinaface(image)
            if face_info is not None:
                face_info['method'] = 'RetinaFace'
                return face_info
        face_info = detect_face_opencv(image)
        if face_info is not None:
            face_info['method'] = 'OpenCV'
            return face_info
    return None
