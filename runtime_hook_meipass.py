# -*- coding: utf-8 -*-
# PyInstaller 运行时钩子：在 main.py 之前执行，确保打包后模型路径正确
# 在任意模块导入前设置 U2NET_HOME，避免 rembg 等库用错路径
import os
import sys

if getattr(sys, 'frozen', False):
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        models_base = os.path.join(meipass, 'models')
        u2net_home = os.path.join(models_base, 'u2net')
        os.environ['U2NET_HOME'] = u2net_home
