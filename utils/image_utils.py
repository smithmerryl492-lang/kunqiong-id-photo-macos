"""图像处理工具函数"""
import os
import cv2
import numpy as np
from PIL import Image
import tempfile


def get_resource_path(relative_path: str) -> str:
    """获取资源的绝对路径，兼容开发环境和PyInstaller打包环境"""
    import sys
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', None)
        if base_path is None:
            base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    path = os.path.normpath(os.path.join(base_path, relative_path))
    if os.path.exists(path):
        return path
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        internal_path = os.path.normpath(os.path.join(exe_dir, "_internal", relative_path))
        if os.path.exists(internal_path):
            return internal_path
        exe_path = os.path.normpath(os.path.join(exe_dir, relative_path))
        if os.path.exists(exe_path):
            return exe_path
    return path


def set_dialog_icon(dialog):
    try:
        from PyQt6.QtGui import QIcon
        icon_path = get_resource_path("logo.ico")
        if os.path.exists(icon_path):
            dialog.setWindowIcon(QIcon(icon_path))
    except:
        pass


def ensure_dir(directory: str):
    os.makedirs(directory, exist_ok=True)


def save_image(image: np.ndarray, output_path: str, quality: int = 95) -> bool:
    """保存图片，支持中文路径"""
    try:
        ensure_dir(os.path.dirname(output_path))
        ext = os.path.splitext(output_path)[1].lower()
        
        # 使用 cv2.imencode + np.tofile 支持中文路径
        if ext in ['.jpg', '.jpeg']:
            encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality]
            success, encoded_image = cv2.imencode('.jpg', image, encode_param)
        elif ext == '.png':
            encode_param = [cv2.IMWRITE_PNG_COMPRESSION, 3]
            success, encoded_image = cv2.imencode('.png', image, encode_param)
        elif ext == '.webp':
            encode_param = [cv2.IMWRITE_WEBP_QUALITY, min(100, max(1, quality))]
            success, encoded_image = cv2.imencode('.webp', image, encode_param)
        elif ext == '.bmp':
            success, encoded_image = cv2.imencode('.bmp', image)
        else:
            # 默认PNG格式
            success, encoded_image = cv2.imencode('.png', image)
        
        if success:
            # 使用二进制方式写入，支持中文路径
            with open(output_path, 'wb') as f:
                f.write(encoded_image.tobytes())
            return os.path.exists(output_path)
        return False
    except Exception as e:
        print(f"保存图片失败: {e}")
        return False


def cv2_imread(image_path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    try:
        img_data = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_data, flags)
        return img
    except Exception:
        try:
            return cv2.imread(image_path, flags)
        except Exception:
            return None


def load_image(image_path: str) -> np.ndarray:
    img = cv2_imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")
    return img


def resize_image(image: np.ndarray, max_size: int = 2048) -> np.ndarray:
    h, w = image.shape[:2]
    if max(h, w) <= max_size:
        return image
    if h > w:
        new_h = max_size
        new_w = int(w * max_size / h)
    else:
        new_w = max_size
        new_h = int(h * max_size / w)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


def composite_images(foreground: np.ndarray, background: np.ndarray, mask: np.ndarray = None, feather: int = 3) -> np.ndarray:
    if background.shape[:2] != foreground.shape[:2]:
        background = cv2.resize(background, (foreground.shape[1], foreground.shape[0]))
    if foreground.shape[2] == 4:
        alpha = foreground[:, :, 3] / 255.0
        fg_rgb = foreground[:, :, :3]
    elif mask is not None:
        alpha = mask.astype(np.float32) / 255.0
        fg_rgb = foreground
    else:
        return foreground
    if feather > 0:
        alpha = cv2.GaussianBlur(alpha, (feather * 2 + 1, feather * 2 + 1), 0)
    alpha_3d = np.stack([alpha, alpha, alpha], axis=2)
    result = fg_rgb * alpha_3d + background * (1 - alpha_3d)
    return result.astype(np.uint8)


def create_temp_file(suffix: str = '.png', prefix: str = 'temp_') -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path


def cleanup_temp_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
