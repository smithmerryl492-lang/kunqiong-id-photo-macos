# -*- coding: utf-8 -*-
"""测试：GUI 启动 + 证件照结果展示/保存链（不弹窗阻塞）"""
import os
import sys
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TQDM_DISABLE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_model_dir = os.path.join(os.path.dirname(__file__), "models")
os.environ["U2NET_HOME"] = os.path.join(_model_dir, "u2net")

def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    app = QApplication(sys.argv)

    from ui.main_window import MainWindow
    from modules.id_photo import IDPhotoModule
    from ui.main_window import ModuleTab

    modules = [IDPhotoModule()]
    window = MainWindow(modules)
    # 不 show，避免弹窗
    tab = window.stacked_widget.widget(0)
    assert isinstance(tab, ModuleTab), "第一个 tab 应为 ModuleTab"
    assert tab.module.get_name() == "证件照", "应为证件照模块"

    # 找一张测试图
    for p in [os.path.join(os.path.dirname(__file__), "test.jpg"),
              os.path.join(os.path.dirname(__file__), "1.jpg"),
              r"d:\wuhengpic\1.jpg", r"d:\wuhengpic\b_20240309113322_11987.png"]:
        if os.path.isfile(p):
            tab.current_image_path = p
            break
    else:
        print("SKIP: 无测试图，仅测 get_params")
        params = tab.get_params()
        assert "bg_color" in params or "size" in params or hasattr(tab.params_widget, "bg_combo")
        print("OK: get_params 可调用，证件照参数存在")
        return 0

    # 加载预览（模拟用户导图）
    if hasattr(tab.preview_widget, "current_image_path"):
        tab.preview_widget.current_image_path = tab.current_image_path
    if hasattr(tab.preview_widget, "set_has_image"):
        tab.preview_widget.set_has_image(True)

    params = tab.get_params()
    assert "bg_color" in params, "get_params 应含 bg_color"
    assert "size" in params, "get_params 应含 size"
    assert "mode" in params, "get_params 应含 mode"
    assert "render_mode" in params, "get_params 应含 render_mode"
    assert "advanced_params" in params, "get_params 应含 advanced_params"
    assert "output_params" in params, "get_params 应含 output_params"
    assert "print_params" in params, "get_params 应含 print_params"
    print("OK: get_params 返回证件照所需参数")

    # 同步加载模型并执行一次 process，再模拟 _show_result
    tab.module.load_model()
    out = tab.module.process(tab.current_image_path, **params)
    assert os.path.isfile(out), "process 应返回有效路径"

    import cv2
    rgba = cv2.imread(out, cv2.IMREAD_UNCHANGED)
    assert rgba is not None, "结果图可读"
    tab.result_path = out
    tab.id_photo_result_widget.id_photo_module = tab.module
    tab.id_photo_result_widget.current_bg_color = params.get("bg_color", "白色")
    tab.id_photo_result_widget.current_render_mode = params.get("render_mode", "纯色")
    tab.id_photo_result_widget.set_image(out, rgba)
    print("OK: set_image(image_path, rgba) 无异常")

    # 不调用 show_fullscreen()，避免弹窗
    print("GUI flow test PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
