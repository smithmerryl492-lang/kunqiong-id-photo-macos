# -*- coding: utf-8 -*-
# 模拟打包环境验证模型路径（不打包直接运行）
import os
import sys

# 模拟 frozen
sys.frozen = True
sys._MEIPASS = os.path.abspath(os.path.join(os.path.dirname(__file__), 'models'))

def _get_resource_path(relative_path):
    if not relative_path or relative_path == '.':
        relative_path = 'models'
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return os.path.normpath(os.path.abspath(os.path.join(meipass, relative_path)))
    return relative_path

if __name__ == '__main__':
    # 用项目真实 models 目录模拟 _MEIPASS
    base = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base, 'models')
    rf = os.path.join(models_dir, 'retinaface', 'retinaface-resnet50.onnx')
    u2 = os.path.join(models_dir, 'u2net', 'hivision_modnet.onnx')
    print('retinaface exists:', os.path.isfile(rf), rf)
    print('hivision_modnet exists:', os.path.isfile(u2), u2)
    # 模拟 config 解析
    sys._MEIPASS = base
    models_res = _get_resource_path('models')
    print('_get_resource_path("models") =', models_res)
    rf_path = os.path.abspath(os.path.join(models_res, 'retinaface', 'retinaface-resnet50.onnx'))
    print('retinaface path =', rf_path, 'exists:', os.path.isfile(rf_path))
