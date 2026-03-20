# -*- coding: utf-8 -*-
"""无 GUI 测试：证件照 process() 核心逻辑与参数"""
import os
import sys
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TQDM_DISABLE"] = "1"

# 项目根
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置 U2NET_HOME
_model_dir = os.path.join(os.path.dirname(__file__), "models")
_u2net_dir = os.path.join(_model_dir, "u2net")
os.environ["U2NET_HOME"] = _u2net_dir

def main():
    from modules.id_photo import IDPhotoModule
    import cv2

    # 测试图：优先 idphoto_app 下，否则用 wuhengpic
    for p in [os.path.join(os.path.dirname(__file__), "test.jpg"),
              os.path.join(os.path.dirname(__file__), "1.jpg"),
              r"d:\wuhengpic\1.jpg",
              r"d:\wuhengpic\b_20240309113322_11987.png"]:
        if os.path.isfile(p):
            image_path = p
            break
    else:
        print("SKIP: 无测试图片 (test.jpg / 1.jpg 或 wuhengpic 下 1.jpg)")
        return 0

    module = IDPhotoModule()
    module.load_model()

    # 测试1: 一寸 + 白色背景 + 纯色
    out1 = module.process(
        image_path,
        bg_color="白色",
        size="一寸 (25×35mm)",
        mode="尺寸列表",
        render_mode="纯色",
        whitening=0, brightness=0, contrast=0, saturation=0, sharpen=0,
        advanced_params={"head_measure_ratio": 0.2, "top_distance_max": 0.12},
        output_params={"kb_enabled": False, "dpi_enabled": False, "dpi": 300},
        plugin_params={"face_alignment": False, "horizontal_flip": False, "layout_crop_line": True, "jpeg_format": False},
        output_types={"standard_photo": True, "hd_photo": False, "matting_standard": False, "matting_hd": False, "layout_photo": False},
        print_params={"enabled": False, "paper_size": "六寸"},
    )
    assert os.path.isfile(out1), "process 应返回存在文件"
    img = cv2.imread(out1, cv2.IMREAD_UNCHANGED)
    assert img is not None, "输出图应可读"
    assert img.ndim == 3, "应为至少 3 通道"
    # 证件照 process 返回 RGBA 临时文件
    if img.shape[2] == 4:
        print("OK: 输出为 RGBA，尺寸", img.shape[:2])
    else:
        print("OK: 输出为 BGR，尺寸", img.shape[:2])
    h, w = img.shape[:2]
    # 一寸 295x413
    assert (w, h) == (295, 413) or (w, h) == (413, 295), f"一寸应为 295x413 或 413x295，得到 {w}x{h}"
    print("TEST 1 PASS: 一寸+白色+纯色")

    # 测试2: 蓝色背景
    out2 = module.process(
        image_path,
        bg_color="蓝色",
        size="一寸 (25×35mm)",
        mode="尺寸列表",
        render_mode="纯色",
    )
    assert os.path.isfile(out2)
    print("TEST 2 PASS: 蓝色背景")

    # 测试3: 只换底（不裁剪）
    out3 = module.process(
        image_path,
        bg_color="红色",
        size="不裁剪",
        mode="尺寸列表",
        render_mode="纯色",
    )
    assert os.path.isfile(out3)
    img3 = cv2.imread(out3, cv2.IMREAD_UNCHANGED)
    assert img3 is not None
    print("TEST 3 PASS: 只换底不裁剪")

    print("ALL PROCESS TESTS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
