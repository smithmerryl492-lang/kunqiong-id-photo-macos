"""配置文件"""
import os
import sys

# 打包后模型在 _MEIPASS 下的固定相对路径（与 spec datas 一致，勿改）
_FROZEN_RETINAFACE_ONNX = "models/retinaface/retinaface-resnet50.onnx"
_FROZEN_HIVISION_ONNX = "models/u2net/hivision_modnet.onnx"


def _get_resource_path(relative_path):
    """获取资源的绝对路径（兼容打包环境：onefile 用 _MEIPASS，onedir 用 _internal）"""
    if not relative_path or relative_path.strip() == "":
        relative_path = "models"
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            meipass_path = os.path.normpath(os.path.join(meipass, relative_path))
            return os.path.abspath(meipass_path)
        internal_path = os.path.normpath(os.path.join(exe_dir, "_internal", relative_path))
        if os.path.exists(internal_path):
            return internal_path
        exe_path = os.path.normpath(os.path.join(exe_dir, relative_path))
        if os.path.exists(exe_path):
            return exe_path
        return internal_path
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.normpath(os.path.abspath(os.path.join(base_path, relative_path)))


def get_retinaface_onnx_path():
    """返回 RetinaFace ONNX 文件绝对路径（打包时仅用 _MEIPASS + models/retinaface/...，绝不返回目录）"""
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            p = os.path.normpath(os.path.join(os.path.abspath(meipass), "models", "retinaface", "retinaface-resnet50.onnx"))
            return p
    return os.path.abspath(os.path.join(_get_resource_path("models"), "retinaface", "retinaface-resnet50.onnx"))


def get_hivision_modnet_onnx_path():
    """返回 hivision_modnet ONNX 文件绝对路径（打包时仅用 _MEIPASS + models/u2net/...，绝不返回目录）"""
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            p = os.path.normpath(os.path.join(os.path.abspath(meipass), "models", "u2net", "hivision_modnet.onnx"))
            return p
    return os.path.abspath(os.path.join(_get_resource_path("models"), "u2net", "hivision_modnet.onnx"))


# 模型配置
MODEL_DIR = _get_resource_path("models")
MODELS_DIR = MODEL_DIR
U2NET_MODEL_DIR = os.path.join(MODEL_DIR, "u2net")

# 默认参数
DEFAULT_BRUSH_SIZE = 20
DEFAULT_SCALE = 2
DEFAULT_FEATHER = 3

# 支持的图片格式
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']

# CPU模式配置
FORCE_CPU = True
CUDA_VISIBLE_DEVICES = "-1"

# 临时文件配置
TEMP_DIR = "temp"
CLEANUP_TEMP_FILES = True

# 授权码配置
SOFT_NUMBER = '10037'  # 软件编号，用于授权码验证

# UI配置(证件照独立版)
VERSION = "V1.0"  # 版本号
WINDOW_TITLE = f"鲲穹AI证件照 {VERSION}"
# 窗口最小尺寸限制
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 650
# 窗口默认尺寸(将根据屏幕分辨率自适应调整)
WINDOW_DEFAULT_WIDTH = 1380
WINDOW_DEFAULT_HEIGHT = 900
