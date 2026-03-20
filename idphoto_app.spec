# -*- mode: python ; coding: utf-8 -*-
# 证件照 EXE 打包：单文件、无控制台
# 目标：全新电脑、无网络、无 Python 环境，复制 EXE 即可离线运行
# 打包内容：所有模型（retinaface + u2net/hivision_modnet）+ logo/图标 + 运行依赖

block_cipher = None

import os
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# 资源：图标与 logo（解压到运行目录根）
datas = [
    (os.path.join(spec_dir, 'logo.png'), '.'),
    (os.path.join(spec_dir, 'logo.ico'), '.'),
    (os.path.join(spec_dir, 'biglogo.png'), '.'),
    (os.path.join(spec_dir, 'kunqiong.ico'), '.'),  # 授权码弹框图标
]
# 模型：整个 models 目录递归打包，保持 models/retinaface、models/u2net 结构
models_root = os.path.join(spec_dir, 'models')
if os.path.isdir(models_root):
    for root, dirs, files in os.walk(models_root):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, spec_dir)
            dest_dir = os.path.dirname(rel)
            datas.append((src, dest_dir))

# MTCNN 权重：打包后 detector 用 __file__ 解析到 _MEIPASS/mtcnnruntime/weights/，须把权重打进该路径
try:
    import mtcnnruntime
    _mtcnn_weights = os.path.join(os.path.dirname(mtcnnruntime.__file__), 'weights')
    if os.path.isdir(_mtcnn_weights):
        for f in os.listdir(_mtcnn_weights):
            src = os.path.join(_mtcnn_weights, f)
            if os.path.isfile(src):
                datas.append((src, 'mtcnnruntime/weights'))
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[spec_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'ui', 'ui.__init__', 'ui.main_window', 'ui.components_v2', 'ui.components', 'ui.custom_widgets',
        'ui.model_loading_dialog', 'ui.styles_tailwind', 'ui.logo_base64',
        'modules', 'modules.__init__', 'modules.id_photo', 'modules.base_module',
        'utils', 'utils.__init__', 'utils.config', 'utils.error_log', 'utils.image_utils', 'utils.modnet_matting',
        'utils.face_detector', 'utils.retinaface_detector',
        'PIL', 'PIL.Image', 'PIL.ImageFont', 'PIL.ImageDraw',
        'cv2', 'numpy',
        'onnxruntime', 'onnxruntime.capi', 'onnxruntime.capi._pybind_state',
        'mtcnnruntime', 'mtcnnruntime.detector',
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.QtSvg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, 'runtime_hook_meipass.py')],
    excludes=['torch', 'torchvision', 'torchaudio', 'rembg'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='鲲穹AI证件照',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(spec_dir, 'logo.ico'),
)
