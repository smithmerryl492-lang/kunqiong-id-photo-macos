"""主窗口"""
import os
import sys
import base64
import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QFileDialog, QProgressBar,
    QStackedWidget, QGridLayout, QFrame, QGraphicsDropShadowEffect
)
from ui.custom_widgets import StyledMessageBox, StyledComboBox
from io import BytesIO
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QColor
from ui.styles_tailwind import TAILWIND_SHADCN_STYLESHEET
from ui.components_v2 import ImagePreviewWidgetV2, ImagePreviewWidgetRect, ImagePreviewWidgetSimple, ImagePreviewWidgetCrop, ImagePreviewWidgetWatermark
from ui.components import ResultImageWidget, IDPhotoResultWidget
try:
    from ui.fullscreen_editor_v2 import FullScreenEditorV2 as FullScreenEditor, FullScreenRectEditor
    from ui.fullscreen_watermark_dialog import FullscreenWatermarkDialog
    from ui.fullscreen_basic_edit_dialog import FullscreenBasicEditDialog
except ImportError:
    FullScreenEditor = FullScreenRectEditor = FullscreenWatermarkDialog = FullscreenBasicEditDialog = None
from utils.config import (
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH,
    WINDOW_DEFAULT_HEIGHT,
    get_footer_text,
    get_window_title,
    save_locale,
)
from utils.error_log import log_error, get_error_log_tip
from i18n import tr, get_current_locale, get_supported_locales, get_locale_label, set_locale


class ProcessThread(QThread):
    """处理线程 - 使用子进程执行避免UI卡死"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, str)  # (success, message)
    
    def __init__(self, module, image_path, **kwargs):
        super().__init__()
        self.module = module
        self.image_path = image_path
        self.kwargs = kwargs
        self._cancelled = False
        self._simulated_progress = 0
        self._progress_running = False
    
    def cancel(self):
        """取消处理"""
        self._cancelled = True
        self._progress_running = False
    
    def run(self):
        import subprocess
        import json
        
        module_name = self.module.get_name()
        
        # 以下模块使用子进程（ncnn会阻塞GIL）
        # 注意：打包环境下无法使用子进程（没有独立Python解释器），直接在线程中运行
        heavy_modules = ["模糊变清晰", "图片放大"]
        
        if module_name in heavy_modules and not getattr(sys, 'frozen', False):
            # 仅开发环境使用子进程
            self._run_subprocess(module_name)
        else:
            # 打包环境或其他模块：直接在线程中运行
            self._run_direct()
    
    def _run_subprocess(self, module_name):
        """使用子进程执行（避免ncnn阻塞UI）"""
        import subprocess
        import json
        import threading
        import time
        
        self.progress.emit(10)
        
        # 准备参数
        params_json = json.dumps(self.kwargs, ensure_ascii=False)
        
        # 获取worker脚本路径（兼容打包环境）
        if getattr(sys, 'frozen', False):
            # 打包环境：worker在exe同级的utils目录下
            exe_dir = os.path.dirname(sys.executable)
            worker_path = os.path.join(exe_dir, "utils", "process_worker.py")
            cwd = exe_dir
        else:
            # 开发环境
            worker_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "process_worker.py")
            cwd = os.path.dirname(os.path.dirname(__file__))
        
        try:
            self.progress.emit(20)
            
            # 启动子进程
            # Windows下使用系统默认编码，避免UTF-8解码错误
            import locale
            system_encoding = locale.getpreferredencoding(False)
            process = subprocess.Popen(
                [sys.executable, worker_path, module_name, self.image_path, params_json],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=system_encoding,
                errors='replace',  # 遇到无法解码的字符用替换字符
                cwd=cwd
            )
            
            self.progress.emit(30)
            
            # 启动平滑进度条模拟器（在子线程中运行）
            self._simulated_progress = 30
            self._progress_running = True
            
            def update_progress():
                """in background thread, smoothly update progress from 30% to 85%"""
                while self._progress_running and self._simulated_progress < 85:
                    time.sleep(0.2)  # 200ms
                    if not self._progress_running:
                        break
                    remaining = 85 - self._simulated_progress
                    increment = max(0.3, remaining * 0.05)
                    self._simulated_progress = min(85, self._simulated_progress + increment)
                    self.progress.emit(int(self._simulated_progress))
            
            progress_thread = threading.Thread(target=update_progress, daemon=True)
            progress_thread.start()
            
            # 在子线程中等待子进程完成（不阻塞进度条更新）
            def wait_for_process():
                stdout, stderr = process.communicate()
                # 停止模拟器
                self._progress_running = False
                
                # 检查取消状态
                if self._cancelled:
                    process.terminate()
                    self.finished.emit("error", tr("process.cancelled"))
                    return
                
                self.progress.emit(90)
                
                if process.returncode != 0:
                    self.finished.emit("error", f"处理失败: {stderr or stdout}")
                    return
                
                # 解析JSON结果（只取最后一行，跳过进度输出）
                try:
                    # stdout可能包含进度百分比，只取最后一行JSON
                    lines = stdout.strip().split('\n')
                    json_line = None
                    for line in reversed(lines):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            json_line = line
                            break
                    
                    if not json_line:
                        self.finished.emit("error", f"无法找到结果: {stdout}")
                        return
                    
                    result = json.loads(json_line)
                    if result.get("status") == "success":
                        self.progress.emit(95)
                        self.finished.emit("success", result.get("result", ""))
                    else:
                        self.finished.emit("error", result.get("message", "未知错误"))
                except json.JSONDecodeError as e:
                    self.finished.emit("error", f"结果解析失败: {e}\n{stdout}")
            
            # 在子线程中等待，不阻塞主线程
            wait_thread = threading.Thread(target=wait_for_process, daemon=True)
            wait_thread.start()
                
        except Exception as e:
            # 停止模拟器
            self._progress_running = False
            import traceback
            log_error(str(e), sys.exc_info(), location="ui.main_window.ProcessThread._run_subprocess")
            self.finished.emit("error", f"启动处理失败: {str(e)}")
    
    def _run_direct(self):
        """直接在线程中执行（轻量模块）"""
        import logging
        import traceback
        import time
        import threading
        logger = logging.getLogger(__name__)
        module_name = self.module.get_name()
        
        try:
            logger.info(f"[{module_name}] 开始处理: {self.image_path}")
            logger.info(f"[{module_name}] 参数: {self.kwargs}")
            
            self.progress.emit(10)
            # 确保模型已加载
            logger.info(f"[{module_name}] 加载模型...")
            self.module.ensure_model_loaded()
            logger.info(f"[{module_name}] 模型加载完成")
            self.progress.emit(30)
            
            # 启动平滑进度条模拟器（在子线程中运行）
            self._simulated_progress = 30
            self._progress_running = True
            
            def update_progress():
                """in background thread, smoothly update progress from 30% to 85%"""
                while self._progress_running and self._simulated_progress < 85:
                    time.sleep(0.2)  # 200ms
                    if not self._progress_running:
                        break
                    # 使用对数速度曲线：初期快，后期慢
                    remaining = 85 - self._simulated_progress
                    increment = max(0.3, remaining * 0.05)
                    self._simulated_progress = min(85, self._simulated_progress + increment)
                    self.progress.emit(int(self._simulated_progress))
            
            progress_thread = threading.Thread(target=update_progress, daemon=True)
            progress_thread.start()
            
            # 处理图片（耗时操作）
            logger.info(f"[{module_name}] 执行处理...")
            result_path = self.module.process(self.image_path, **self.kwargs)
            logger.info(f"[{module_name}] 处理完成: {result_path}")
            
            # 停止模拟器，直接跳到95%
            self._progress_running = False
            progress_thread.join(timeout=0.5)
            self.progress.emit(95)
            
            if result_path and os.path.exists(result_path):
                self.finished.emit("success", result_path)
            else:
                logger.error(f"[{module_name}] 未生成输出文件")
                self.finished.emit("error", "处理失败：未生成输出文件")
        except Exception as e:
            # 停止模拟器
            self._progress_running = False
            error_msg = f"处理失败：{str(e)}"
            logger.error(f"[{module_name}] {error_msg}")
            logger.error(traceback.format_exc())
            log_error(error_msg, sys.exc_info(), location="ui.main_window.ProcessThread._run_direct")
            self.finished.emit("error", error_msg)



class ModuleTab(QWidget):
    """功能模块标签页"""
    def __init__(self, module, parent=None):
        super().__init__(parent)
        self.module = module
        self.current_image_path = None
        self.result_path = None
        self.process_thread = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)
        
        # 主内容区域容器（支持动态切换布局）
        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        
        # 左侧：图片预览区域（处理前大区域）
        self.left_panel = QWidget()
        self.left_panel_layout = QVBoxLayout(self.left_panel)
        self.left_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.left_panel_layout.setSpacing(0)
        
        # 根据模块是否需要mask选择不同的预览组件
        self.params_widget = self.module.get_ui_widget()
        self.requires_mask = getattr(self.module, 'requires_mask', lambda: False)()
        self.selection_mode = getattr(self.module, 'get_selection_mode', lambda: 'brush')()
        self.requires_crop_box = getattr(self.module, 'requires_crop_box', lambda: False)()
        self.uses_brush_preview = getattr(self.module, 'uses_brush_preview', lambda: False)()
        
        if self.requires_crop_box:
            # 基础编辑模块的裁剪模式：使用裁剪框预览组件
            self.preview_widget = ImagePreviewWidgetCrop(
                params_widget=self.params_widget,
                module_name=self.module.get_name(),
                module_description=self.module.get_description(),
                module=self.module
            )
            self.preview_widget.image_loaded.connect(self.on_image_loaded)
            self.preview_widget.crop_updated.connect(self.on_crop_updated)
            # 连接全屏功能信号（基础编辑模块）
            if self.module.get_name() == "基础编辑":
                self.preview_widget.fullscreen_requested.connect(lambda: self.open_fullscreen_basic_edit(self))
            # 连接参数组件的SpinBox更新到裁剪框
            self._connect_crop_spinboxes()
        elif self.uses_brush_preview or (self.requires_mask and self.selection_mode != 'rect'):
            # 笔刷涂抹模式（创意工具消除路人、涂抹去除、证件照等）
            self.preview_widget = ImagePreviewWidgetV2(
                params_widget=self.params_widget,
                module_name=self.module.get_name(),
                module_description=self.module.get_description(),
                module=self.module
            )
            self.preview_widget.mask_updated.connect(self.on_mask_updated)
            self.preview_widget.image_loaded.connect(self.on_image_loaded)
            self.preview_widget.set_fullscreen_callback(lambda: self.open_fullscreen_editor(self))
        elif not self.requires_mask:
            module_name = self.module.get_name()
            
            # 图片加水印模块使用专门的预览组件
            if module_name == "图片加水印":
                self.preview_widget = ImagePreviewWidgetWatermark(
                    params_widget=self.params_widget,
                    module_name=self.module.get_name(),
                    module_description=self.module.get_description(),
                    module=self.module
                )
                self.preview_widget.image_loaded.connect(self.on_image_loaded)
                # 连接水印相关信号
                self.preview_widget.watermark_selected.connect(self.on_watermark_selected)
                self.preview_widget.watermark_moved.connect(self.on_watermark_moved)
                self.preview_widget.watermark_resized.connect(self.on_watermark_resized)
                self.preview_widget.watermark_deleted.connect(self.on_watermark_deleted)
                # 连接全屏功能信号（如果有fullscreen_requested信号）
                if hasattr(self.preview_widget, 'fullscreen_requested'):
                    self.preview_widget.fullscreen_requested.connect(lambda: self.open_fullscreen_watermark(self))
                # 设置模块的水印添加回调
                self.module._on_watermark_added = lambda index: self.preview_widget.update_watermarks() if hasattr(self.preview_widget, 'update_watermarks') else None
                # 设置模块的参数变化回调
                def on_watermark_params_changed(index):
                    if hasattr(self.preview_widget, 'update_watermarks'):
                        self.preview_widget.update_watermarks()
                        # 更新指定水印的显示
                        if hasattr(self.preview_widget.graphics_view, 'update_watermark_item'):
                            if index is not None and 0 <= index < len(self.module.watermarks):
                                self.preview_widget.graphics_view.update_watermark_item(index, self.module.watermarks[index])
                self.module._on_watermark_params_changed = on_watermark_params_changed
            else:
                # 其他不需要mask的模块（抠图、背景替换、图片放大、模糊变清晰、调色与增强、创意工具）
                # 使用简单的图片预览组件
                # 以下模块需要缩放功能：图片放大、基础编辑、创意工具、调色与增强
                enable_zoom = (module_name in ["图片放大", "基础编辑", "创意工具", "调色与增强"])
                self.preview_widget = ImagePreviewWidgetSimple(
                    params_widget=self.params_widget,
                    module_name=self.module.get_name(),
                    module_description=self.module.get_description(),
                    enable_zoom=enable_zoom,
                    module=self.module
                )
                self.preview_widget.image_loaded.connect(self.on_image_loaded)
                # 连接全屏功能信号
                if module_name == "图片放大":
                    # 图片放大模块
                    self.preview_widget.fullscreen_requested.connect(lambda: self.open_fullscreen_upscale(self))
                elif module_name == "基础编辑":
                    # 基础编辑模块
                    self.preview_widget.fullscreen_requested.connect(lambda: self.open_fullscreen_basic_edit(self))
        elif self.selection_mode == 'rect':
            # 矩形选择模式（去除水印）
            self.preview_widget = ImagePreviewWidgetRect(
                params_widget=self.params_widget,
                module_name=self.module.get_name(),
                module_description=self.module.get_description(),
                module=self.module
            )
            self.preview_widget.mask_updated.connect(self.on_mask_updated)
            self.preview_widget.image_loaded.connect(self.on_image_loaded)
            self.preview_widget.set_fullscreen_callback(lambda: self.open_fullscreen_rect_editor(self))
        else:
            # 笔刷涂抹模式（无 uses_brush_preview 且 requires_mask 且非 rect 的兜底）
            self.preview_widget = ImagePreviewWidgetV2(
                params_widget=self.params_widget,
                module_name=self.module.get_name(),
                module_description=self.module.get_description(),
                module=self.module
            )
            self.preview_widget.mask_updated.connect(self.on_mask_updated)
            self.preview_widget.image_loaded.connect(self.on_image_loaded)
            self.preview_widget.set_fullscreen_callback(lambda: self.open_fullscreen_editor(self))
        
        self.left_panel_layout.addWidget(self.preview_widget, stretch=1)
        
        # 证件照：连接“适应框/实际大小”按钮的显示与文字更新，并给模块保存 tab 引用（点击时用）
        if self.module.get_name() == "证件照" and hasattr(self.preview_widget, 'fit_button_visible') and hasattr(self.module, 'set_fit_button_visible'):
            self.preview_widget.fit_button_visible.connect(self.module.set_fit_button_visible)
            self.preview_widget.fit_mode_changed.connect(self.module.update_fit_button_text)
            self.module._tab_ref = self
        # 操作按钮区域
        action_container = QWidget()
        action_layout = QVBoxLayout(action_container)
        action_layout.setSpacing(12)
        self.btn_process = QPushButton("🚀 " + tr("main.start_process"))
        self.btn_process.setObjectName("btn_process")
        self.btn_process.setStyleSheet("""
            QPushButton#btn_process {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 15px;
                min-height: 44px;
            }
            QPushButton#btn_process:hover {
                background-color: hsl(217.2, 91.2%, 59.8%);
            }
            QPushButton#btn_process:disabled {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(215, 20.2%, 65.1%);
                opacity: 0.5;
            }
        """)
        self.btn_process.clicked.connect(self.start_process)
        self.btn_process.setEnabled(False)
        action_layout.addWidget(self.btn_process)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: hsl(217.2, 32.6%, 17.5%);
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border-radius: 4px;
            }
        """)
        action_layout.addWidget(self.progress_bar)
        
        self.left_panel_layout.addWidget(action_container)
        
        self.content_layout.addWidget(self.left_panel, stretch=1)
        
        # 右侧：处理结果区域（初始隐藏）
        self.right_panel = QWidget()
        self.right_panel.setVisible(False)
        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.right_panel_layout.setSpacing(12)
        
        # 结果标题和关闭按钮
        result_label = QLabel(tr("main.result"))
        result_label.setProperty("class", "subheading")
        result_label.setStyleSheet("""
            QLabel[class="subheading"] {
                font-weight: 500;
                font-size: 16px;
                color: hsl(213, 31%, 91%);
            }
        """)
        result_header = QHBoxLayout()
        result_header.addWidget(result_label)
        result_header.addStretch()
        
        self.btn_close_result = QPushButton("✕")
        self.btn_close_result.setProperty("class", "ghost")
        self.btn_close_result.setFixedSize(32, 32)
        self.btn_close_result.setStyleSheet("""
            QPushButton[class="ghost"] {
                background-color: transparent;
                color: hsl(215, 20.2%, 65.1%);
                border: none;
                border-radius: 6px;
            }
            QPushButton[class="ghost"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
            }
        """)
        self.btn_close_result.clicked.connect(self.close_result_panel)
        result_header.addWidget(self.btn_close_result)
        
        self.right_panel_layout.addLayout(result_header)
        
        # 通用结果组件
        self.result_widget = ResultImageWidget()
        self.right_panel_layout.addWidget(self.result_widget, stretch=1)
        
        # 证件照专用结果组件（初始隐藏）
        self.id_photo_result_widget = IDPhotoResultWidget()
        self.id_photo_result_widget.setVisible(False)
        self.right_panel_layout.addWidget(self.id_photo_result_widget, stretch=1)
        self.btn_save = QPushButton("💾 " + tr("main.save_result"))
        self.btn_save.setProperty("class", "secondary")
        self.btn_save.setStyleSheet("""
            QPushButton[class="secondary"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 500;
            }
            QPushButton[class="secondary"]:hover {
                background-color: hsl(215, 27.9%, 16.9%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QPushButton[class="secondary"]:disabled {
                opacity: 0.5;
            }
        """)
        self.btn_save.clicked.connect(self.save_result)
        self.btn_save.setEnabled(False)
        self.right_panel_layout.addWidget(self.btn_save)
        
        self.content_layout.addWidget(self.right_panel, stretch=1)
        
        layout.addWidget(self.content_widget, stretch=1)
    
    def close_result_panel(self):
        """关闭结果面板，恢复处理前布局"""
        self.right_panel.setVisible(False)
        # 恢复左侧面板为全宽度
        self.content_layout.setStretchFactor(self.left_panel, 1)
        self.result_path = None
        self.result_widget.set_image(None)
        self.btn_save.setEnabled(False)
    
    def show_result_panel(self):
        """显示结果面板，切换到处理后布局"""
        if not self.right_panel.isVisible():
            self.right_panel.setVisible(True)
            # 调整布局比例：左侧缩小，右侧放大
            # 确保左侧在前，右侧在后
            self.content_layout.removeWidget(self.left_panel)
            self.content_layout.removeWidget(self.right_panel)
            self.content_layout.insertWidget(0, self.left_panel, stretch=1)
            self.content_layout.insertWidget(1, self.right_panel, stretch=2)
    
    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("main.select_image"), "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            # ????
            valid, msg = self.module.validate_input(file_path)
            if not valid:
                StyledMessageBox.warning(self, tr("common.error"), msg)
                return
            
            
            # 加载到预览组件
            if self.preview_widget.load_image(file_path):
                self.current_image_path = file_path
                self.btn_process.setEnabled(True)
                # 清空结果，关闭结果面板
                self.result_path = None
                self.result_widget.set_image(None)
                self.close_result_panel()  # 恢复到处理前布局
                self.btn_save.setEnabled(False)
    
    def on_mask_updated(self, mask_path):
        """Mask更新"""
        # 如果mask被清除（mask_path为None），关闭结果面板
        if mask_path is None:
            self.close_result_panel()

    def on_image_loaded(self, image_path):
        """图片加载完成"""
        self.current_image_path = image_path
        self.btn_process.setEnabled(True)
        # 清空结果，关闭结果面板
        self.result_path = None
        self.result_widget.set_image(None)
        self.close_result_panel()
        self.btn_save.setEnabled(False)
        
        # 如果是水印模块，更新水印显示
        if self.module.get_name() == "图片加水印" and hasattr(self.preview_widget, 'update_watermarks'):
            # 延迟更新，确保图片已加载
            QTimer.singleShot(100, self.preview_widget.update_watermarks)
        
        # 如果是裁剪模式，默认不创建裁剪框（需要用户拖拽创建）
        # 清空裁剪参数
        if self.requires_crop_box and hasattr(self.module, 'edit_params'):
            self.module.edit_params['crop_x'] = 0
            self.module.edit_params['crop_y'] = 0
            self.module.edit_params['crop_w'] = 0
            self.module.edit_params['crop_h'] = 0
            # 清空SpinBox
            if hasattr(self.module, 'crop_x_spin'):
                self.module.crop_x_spin.setValue(0)
                self.module.crop_y_spin.setValue(0)
                self.module.crop_w_spin.setValue(0)
                self.module.crop_h_spin.setValue(0)
    
    def on_watermark_selected(self, index):
        """水印被选中"""
        if self.module.get_name() == "图片加水印":
            self.module.select_watermark(index)
            # 更新参数面板状态
            if hasattr(self.module, '_update_params_widget_state'):
                self.module._update_params_widget_state()
            # 更新预览组件中的选中状态
            if hasattr(self.preview_widget, 'select_watermark'):
                self.preview_widget.select_watermark(index)
    
    def on_watermark_moved(self, index, x, y):
        """水印位置变化"""
        if self.module.get_name() == "图片加水印":
            self.module.update_watermark_position(index, x=x, y=y)
            # 不需要更新预览，因为预览组件已经显示了最新位置
    
    def on_watermark_resized(self, index, width, height):
        """水印大小变化"""
        if self.module.get_name() == "图片加水印":
            self.module.update_watermark_position(index, width=width, height=height)
            # 不需要更新预览，因为预览组件已经显示了最新大小
    
    def on_watermark_deleted(self, index):
        """水印被删除"""
        if self.module.get_name() == "图片加水印":
            self.module.delete_watermark(index)
            # 更新参数面板状态
            if hasattr(self.module, '_update_params_widget_state'):
                self.module._update_params_widget_state()
            # 更新预览
            if hasattr(self.preview_widget, 'update_watermarks'):
                self.preview_widget.update_watermarks()
    
    def on_crop_updated(self, x: int, y: int, w: int, h: int):
        """裁剪框更新回调"""
        if hasattr(self.module, 'edit_params'):
            self.module.edit_params['crop_x'] = x
            self.module.edit_params['crop_y'] = y
            self.module.edit_params['crop_w'] = w
            self.module.edit_params['crop_h'] = h
        
        # 更新SpinBox（防止循环更新）
        if hasattr(self.module, 'crop_x_spin'):
            self.module.crop_x_spin.blockSignals(True)
            self.module.crop_y_spin.blockSignals(True)
            self.module.crop_w_spin.blockSignals(True)
            self.module.crop_h_spin.blockSignals(True)
            
            self.module.crop_x_spin.setValue(x)
            self.module.crop_y_spin.setValue(y)
            self.module.crop_w_spin.setValue(w)
            self.module.crop_h_spin.setValue(h)
            
            self.module.crop_x_spin.blockSignals(False)
            self.module.crop_y_spin.blockSignals(False)
            self.module.crop_w_spin.blockSignals(False)
            self.module.crop_h_spin.blockSignals(False)
    
    def _connect_crop_spinboxes(self):
        """连接裁剪SpinBox到裁剪框"""
        if not hasattr(self.module, 'crop_x_spin'):
            return
        
        # 连接SpinBox更新到裁剪框
        def update_crop_box():
            if hasattr(self.preview_widget, 'set_crop_rect'):
                x = self.module.crop_x_spin.value()
                y = self.module.crop_y_spin.value()
                w = self.module.crop_w_spin.value()
                h = self.module.crop_h_spin.value()
                self.preview_widget.set_crop_rect(x, y, w, h)
        
        self.module.crop_x_spin.valueChanged.connect(lambda _: update_crop_box())
        self.module.crop_y_spin.valueChanged.connect(lambda _: update_crop_box())
        self.module.crop_w_spin.valueChanged.connect(lambda _: update_crop_box())
        self.module.crop_h_spin.valueChanged.connect(lambda _: update_crop_box())
        
        # 监听操作类型改变，显示/隐藏裁剪框
        if hasattr(self.module, '_on_operation_changed'):
            original_on_op_changed = self.module._on_operation_changed
            def wrapped_on_op_changed(op):
                try:
                    original_on_op_changed(op)
                except RuntimeError:
                    # widget 已被删除，跳过
                    return
                # 根据操作类型显示/隐藏裁剪框
                if hasattr(self.preview_widget, 'set_crop_box_visible'):
                    try:
                        self.preview_widget.set_crop_box_visible(op == 'crop')
                    except RuntimeError:
                        # preview_widget 已被删除，跳过
                        pass
            self.module._on_operation_changed = wrapped_on_op_changed
    
    def open_fullscreen_editor(self, module_tab):
        """打开全屏编辑器"""
        if FullScreenEditor is None:
            return
        if not module_tab.current_image_path:
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.select_image_first"))
            return
        
        # 获取当前的mask（如果有）- 转换为灰度图
        current_mask = None
        if module_tab.preview_widget.mask is not None:
            # 从RGBA mask提取alpha通道作为灰度mask
            if len(module_tab.preview_widget.mask.shape) == 3:
                current_mask = module_tab.preview_widget.mask[:, :, 3]  # 使用alpha通道
            else:
                current_mask = module_tab.preview_widget.mask

        # 创建全屏编辑器
        try:
            editor = FullScreenEditor(module_tab.current_image_path, current_mask, self)
        except Exception as e:
            log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.open_fullscreen_editor.create")
            StyledMessageBox.critical(self, "错误", f"创建全屏编辑器失败: {str(e)}")
            return
        
        # 连接mask更新信号
        def on_editor_mask_updated(mask_path):
            # 更新预览组件的mask（全屏编辑器返回的是灰度mask，需要转换为RGBA）
            if mask_path and os.path.exists(mask_path):
                import cv2
                from utils.image_utils import cv2_imread
                gray_mask = cv2_imread(mask_path, cv2.IMREAD_GRAYSCALE)
                if gray_mask is not None:
                    h, w = gray_mask.shape
                    rgba_mask = np.zeros((h, w, 4), dtype=np.uint8)
                    rgba_mask[:, :, 0] = module_tab.preview_widget.brush_color.blue()
                    rgba_mask[:, :, 1] = module_tab.preview_widget.brush_color.green()
                    rgba_mask[:, :, 2] = module_tab.preview_widget.brush_color.red()
                    rgba_mask[:, :, 3] = gray_mask
                    module_tab.preview_widget.mask = rgba_mask
                    module_tab.preview_widget.update_display()
                    module_tab.preview_widget.mask_updated.emit(mask_path)
        
        editor.mask_updated.connect(on_editor_mask_updated)
        
        # 显示全屏编辑器
        try:
            result = editor.exec()
        except Exception as e:
            log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.open_fullscreen_editor.show")
            StyledMessageBox.critical(self, "错误", f"显示全屏编辑器失败: {str(e)}")
            return
        
        # 编辑器关闭后，同步mask回预览组件
        try:
            if result == 1:  # QDialog.Accepted
                editor_mask = editor.get_mask()  # 获取灰度mask
                if editor_mask is not None:
                    # 将灰度mask转换为RGBA mask
                    h, w = editor_mask.shape
                    rgba_mask = np.zeros((h, w, 4), dtype=np.uint8)
                    rgba_mask[:, :, 0] = editor.brush_color.blue()
                    rgba_mask[:, :, 1] = editor.brush_color.green()
                    rgba_mask[:, :, 2] = editor.brush_color.red()
                    rgba_mask[:, :, 3] = editor_mask
                    module_tab.preview_widget.mask = rgba_mask
                    # 同步颜色和透明度
                    module_tab.preview_widget.brush_color = editor.brush_color
                    module_tab.preview_widget.brush_alpha = editor.brush_alpha
                    module_tab.preview_widget.update_display()
                    # 保存mask到预览组件（而不是编辑器）
                    module_tab.preview_widget.save_mask()
        except Exception as e:
            log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.open_fullscreen_editor.save")
            StyledMessageBox.warning(self, "警告", f"保存编辑结果失败: {str(e)}")
    
    def open_fullscreen_rect_editor(self, module_tab):
        """打开矩形选择全屏编辑器（支持多矩形）"""
        if not module_tab.current_image_path:
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.select_image_first"))
            return
        
        # 获取当前所有矩形
        current_rects = None
        if hasattr(module_tab.preview_widget, 'get_rects'):
            current_rects = module_tab.preview_widget.get_rects()
        
        # 创建全屏编辑器
        try:
            editor = FullScreenRectEditor(module_tab.current_image_path, current_rects, self)
        except Exception as e:
            log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.open_fullscreen_rect_editor.create")
            StyledMessageBox.critical(self, "错误", f"创建全屏编辑器失败: {str(e)}")
            return
        
        # 显示全屏编辑器
        try:
            result = editor.exec()
        except Exception as e:
            log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.open_fullscreen_rect_editor.show")
            StyledMessageBox.critical(self, "错误", f"显示全屏编辑器失败: {str(e)}")
            return
        
        # 编辑器关闭后，同步矩形回预览组件
        try:
            if result == 1:  # QDialog.Accepted
                new_rects = editor.get_rects()
                if hasattr(module_tab.preview_widget, 'set_rects'):
                    module_tab.preview_widget.set_rects(new_rects)
        except Exception as e:
            log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.open_fullscreen_rect_editor.save")
            StyledMessageBox.warning(self, "警告", f"保存编辑结果失败: {str(e)}")
    
    def open_fullscreen_upscale(self, module_tab):
        """打开图片放大的全屏功能窗口"""
        try:
            from ui.fullscreen_upscale_dialog import FullscreenUpscaleDialog
        except ImportError:
            return
        if not module_tab.current_image_path:
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.select_image_first"))
            return
        
        # 准备初始参数
        initial_params = {
            'model_index': 0,  # 默认快速放大
            'scale': 1.0
        }
        
        # 从模块读取当前参数
        if hasattr(module_tab.module, 'selected_model'):
            initial_params['model_index'] = 0 if module_tab.module.selected_model == "realcugan" else 1
        
        # 从预览组件读取缩放比例
        if hasattr(module_tab.preview_widget, 'get_zoom_scale'):
            initial_params['scale'] = module_tab.preview_widget.get_zoom_scale()
        
        # 创建全屏对话框
        dialog = FullscreenUpscaleDialog(
            module_tab.current_image_path,
            module_tab.module,
            initial_params,
            parent=self
        )
        
        # 连接参数变化信号，同步回主窗口
        def on_params_changed(params):
            # 更新模块参数
            module_tab.module.selected_model = "realcugan" if params['model_index'] == 0 else "esrgan"
            module_tab.module.target_scale = params['scale']
            
            # 更新UI
            if hasattr(module_tab, 'params_widget') and module_tab.params_widget:
                if hasattr(module_tab.params_widget, 'model_combo'):
                    module_tab.params_widget.model_combo.setCurrentIndex(params['model_index'])
            
            # 更新预览组件的缩放滑块
            if hasattr(module_tab.preview_widget, 'zoom_slider'):
                module_tab.preview_widget.zoom_slider.setValue(int(params['scale'] * 100))
        
        dialog.params_changed.connect(on_params_changed)
        
        # 显示对话框
        dialog.exec()
    
    def open_fullscreen_watermark(self, module_tab):
        """打开图片加水印的全屏功能窗口"""
        if FullscreenWatermarkDialog is None:
            return
        if not module_tab.current_image_path:
            from ui.custom_widgets import StyledMessageBox
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.select_image_first"))
            return
        
        # 创建全屏对话框
        dialog = FullscreenWatermarkDialog(
            module_tab.current_image_path,
            module_tab.module,
            self
        )
        
        dialog.exec()
    
    def open_fullscreen_basic_edit(self, module_tab):
        """打开基础编辑的全屏功能窗口"""
        if FullscreenBasicEditDialog is None:
            return
        if not module_tab.current_image_path:
            from ui.custom_widgets import StyledMessageBox
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.select_image_first"))
            return
        
        # 创建全屏对话框
        dialog = FullscreenBasicEditDialog(
            module_tab.current_image_path,
            module_tab.module,
            self
        )
        
        dialog.exec()
    
    def get_params(self):
        """获取参数设置"""
        params = {}
        # 如果有mask，添加mask路径
        if self.preview_widget.has_mask():
            params['mask_path'] = self.preview_widget.get_mask_path()
        
        # 优先从模块获取参数（模块自己知道如何读取UI控件）
        # 注意：图片放大、模糊变清晰不再需要scale参数（固定4倍）
        
        # 图片放大模块 - 从预览缩放控件读取倍数
        if self.module.get_name() == "图片放大":
            if hasattr(self.preview_widget, 'get_zoom_scale'):
                scale = self.preview_widget.get_zoom_scale()
                params['scale'] = scale
                # 同时更新模块的 target_scale
                if hasattr(self.module, 'set_scale_from_preview'):
                    self.module.set_scale_from_preview(scale)
        
        # 抠图模块 - 使用 get_selected_model() 方法获取实际模型名
        if hasattr(self.module, 'get_selected_model'):
            params['model_name'] = self.module.get_selected_model()
        
        # 从参数组件获取参数
        if self.params_widget:
            # 背景替换模块
            if hasattr(self.params_widget, 'bg_path_edit'):
                bg_path = self.params_widget.bg_path_edit.text()
                if bg_path and os.path.exists(bg_path):
                    params['background_path'] = bg_path
                elif hasattr(self.module, 'get_background_path'):
                    bg_path = self.module.get_background_path()
                    if bg_path:
                        params['background_path'] = bg_path
            
            # 人物抠图模块 - 自定义背景
            if hasattr(self.module, 'background_image_path') and self.module.background_image_path:
                params['background_image_path'] = self.module.background_image_path
            
            if hasattr(self.params_widget, 'feather_spin'):
                params['feather'] = self.params_widget.feather_spin.value()
            
            # 抠图和背景替换的Alpha Matting参数
            if hasattr(self.params_widget, 'alpha_matting_check'):
                params['alpha_matting'] = self.params_widget.alpha_matting_check.isChecked()
            elif hasattr(self.params_widget, 'alpha_matting_button'):
                params['alpha_matting'] = self.params_widget.alpha_matting_button.isChecked()
            
            if hasattr(self.params_widget, 'fg_threshold_slider'):
                params['alpha_matting_foreground_threshold'] = self.params_widget.fg_threshold_slider.value()
            
            if hasattr(self.params_widget, 'bg_threshold_slider'):
                params['alpha_matting_background_threshold'] = self.params_widget.bg_threshold_slider.value()
            
            # erode_size使用默认值10，暂不在UI中显示
            if params.get('alpha_matting'):
                params['alpha_matting_erode_size'] = 10
            
            # 证件照模块
            if hasattr(self.params_widget, 'bg_combo'):
                params['bg_color'] = self.params_widget.bg_combo.currentData()
            if hasattr(self.params_widget, 'size_combo'):
                params['size'] = self.params_widget.size_combo.currentData()
            # 证件照模式参数（官方）
            if hasattr(self.params_widget, 'mode_combo'):
                params['mode'] = self.params_widget.mode_combo.currentData()
            # 证件照渲染模式（官方）
            if hasattr(self.params_widget, 'render_combo'):
                params['render_mode'] = self.params_widget.render_combo.currentData()
            # 证件照美颜参数（使用新的 beauty_params）
            if hasattr(self.module, 'beauty_params'):
                params.update(self.module.beauty_params)
            # 证件照高级参数（官方）
            if hasattr(self.module, 'advanced_params'):
                params['advanced_params'] = self.module.advanced_params
            # 证件照自定义颜色
            if hasattr(self.module, 'custom_color'):
                params['custom_color'] = self.module.custom_color
            # 证件照输出设置（KB大小和DPI）
            if hasattr(self.module, 'output_params'):
                params['output_params'] = self.module.output_params
            # 证件照插件功能（官方）
            if hasattr(self.module, 'plugin_params'):
                params['plugin_params'] = self.module.plugin_params
            # 证件照输出类型（官方）
            if hasattr(self.module, 'output_types'):
                params['output_types'] = self.module.output_types
            # 证件照打印排版（官方）
            if hasattr(self.module, 'print_params'):
                params['print_params'] = self.module.print_params
        
        return params
    
    def start_process(self):
        """开始处理"""
        # 检查是否有图片 - 优先检查preview_widget中的图片路径
        if not self.current_image_path:
            # 尝试从 preview_widget 获取
            if hasattr(self.preview_widget, 'current_image_path') and self.preview_widget.current_image_path:
                self.current_image_path = self.preview_widget.current_image_path

        if not self.current_image_path:
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.select_image_first"))
            return
        
        # 检查是否需要mask
        if hasattr(self.module, 'requires_mask') and self.module.requires_mask():
            if not self.preview_widget.has_mask():
                StyledMessageBox.warning(self, tr("common.warning"), tr("validation.mark_area_first"))
                return
        
        # 检查模型是否已加载，如果未加载则显示加载对话框
        if not self.module.model_loaded:
            self._show_model_loading_dialog()
            return
        
        # 模型已加载，直接开始处理
        self._do_process()
    
    def _show_model_loading_dialog(self):
        """显示模型加载对话框"""
        from ui.model_loading_dialog import ModelLoadingDialog
        from PyQt6.QtCore import QThread, pyqtSignal
        import logging
        
        logger = logging.getLogger(__name__)
        module_name = self.module.get_name()
        
        # 创建加载对话框（传入模块名称）
        loading_dialog = ModelLoadingDialog(module_name=f"{module_name}AI", parent=self)
        
        # 创建后台加载线程
        class ModelLoadThread(QThread):
            finished_signal = pyqtSignal()
            error_signal = pyqtSignal(str)
            
            def __init__(self, module):
                super().__init__()
                self.module = module
            
            def run(self):
                try:
                    logger.info(f"[按需加载] 开始加载模型: {self.module.get_name()}")
                    
                    # 加载模型
                    self.module.ensure_model_loaded()
                    
                    logger.info(f"[按需加载] 模型加载完成: {self.module.get_name()}")
                    self.finished_signal.emit()
                except Exception as e:
                    logger.error(f"[按需加载] 模型加载失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    log_error(str(e), sys.exc_info(), location="ui.main_window.ModelLoadThread.run")
                    self.error_signal.emit(str(e))
        
        load_thread = ModelLoadThread(self.module)
        
        def on_finished():
            loading_dialog.close()
            # 加载完成后自动开始处理
            if self.module.model_loaded:
                self._do_process()
        
        def on_error(error_msg):
            loading_dialog.close()
            StyledMessageBox.critical(self, "错误", f"模型加载失败:\n{error_msg}")
        
        load_thread.finished_signal.connect(on_finished)
        load_thread.error_signal.connect(on_error)
        
        # 启动加载线程
        load_thread.start()
        
        # 显示对话框（模态）
        loading_dialog.exec()
    
    def _do_process(self):
        """执行实际处理逻辑"""
        # 清除结果面板（重新处理时）
        self.close_result_panel()
        
        # 预估处理时间
        estimated_time = self._estimate_process_time()
        
        self.btn_process.setText(
            tr("main.processing", estimated_time=estimated_time)
        )
        
        
        
        # 禁用按钮
        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 获取参数
        params = self.get_params()
        
        # 启动处理线程
        self.process_thread = ProcessThread(self.module, self.current_image_path, **params)
        self.process_thread.progress.connect(self.progress_bar.setValue, Qt.ConnectionType.QueuedConnection)
        self.process_thread.finished.connect(self.on_process_finished, Qt.ConnectionType.QueuedConnection)
        self.process_thread.start()
    
    def _estimate_process_time(self):
        """预估处理时间（基于图片大小和模块类型）"""
        import cv2
        import platform
        
        try:
            # 读取图片大小（支持中文路径）
            from utils.image_utils import cv2_imread
            img = cv2_imread(self.current_image_path)
            if img is None:
                return "1-3分钟"  # 默认预估
            
            height, width = img.shape[:2]
            pixels = height * width
            
            # 获取模块名称
            module_name = self.module.get_name()
            
            # 基础时间（秒）- 根据模块和像素数（纯 CPU）
            base_time = 0
            
            # 不同模块的基础时间
            if module_name == "背景移除":
                base_time = 15 if pixels < 1000000 else 30  # 1MP以下15秒，以上30秒
            elif module_name == "背景替换":
                base_time = 20 if pixels < 1000000 else 40
            elif module_name == "图片放大":
                # 放大倍数影响时间
                scale = 2.0  # 默认
                if hasattr(self.preview_widget, 'get_zoom_scale'):
                    scale = self.preview_widget.get_zoom_scale()
                base_time = int(10 * scale) if pixels < 1000000 else int(20 * scale)
            elif module_name == "证件照":
                base_time = 25 if pixels < 1000000 else 50
            else:
                base_time = 20 if pixels < 1000000 else 40
            
            # 纯 CPU 处理：保守预估
            base_time = int(base_time * 2)
            
            # 大图片额外增加时间
            if pixels > 4000000:  # 4MP以上
                base_time = int(base_time * 1.5)
            
            # 格式化输出
            if base_time < 60:
                return f"{base_time}-{base_time + 30}秒"
            else:
                minutes = base_time // 60
                seconds = base_time % 60
                max_minutes = (base_time + 30) // 60
                max_seconds = (base_time + 30) % 60
                
                if max_seconds == 0:
                    return f"{minutes}分{seconds}秒-{max_minutes}分钟"
                else:
                    return f"{minutes}分{seconds}秒-{max_minutes}分{max_seconds}秒"
                
        except Exception as e:
            # 异常情况返回默认值
            return "1-3分钟"
    
    def on_process_finished(self, status, message):
        """处理完成"""
        self.progress_bar.setValue(100)
        
        if status == "success":
            self.result_path = message
            # 使用延迟加载避免UI卡顿
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, lambda: self._show_result(message))
        else:
            self.progress_bar.setVisible(False)
            self.btn_process.setEnabled(True)
            self.btn_process.setText(tr("main.start_process"))
            StyledMessageBox.critical(self, tr("common.error"), message)
    
    def _show_result(self, image_path):
        """延迟显示结果 - 根据模块类型选择显示方式"""
        try:
            # 获取当前模块名
            current_module_name = self.module.get_name()
            
            if current_module_name == "证件照":
                # 证件照使用专用预览组件（支持切换背景色）
                # 读取带alpha通道的图片（使用 cv2_imread 支持中文路径）
                import cv2
                from utils.image_utils import cv2_imread
                rgba_img = cv2_imread(image_path, cv2.IMREAD_UNCHANGED)
                if rgba_img is not None:
                    # 获取用户选择的背景色和渲染模式
                    bg_color = 'white'
                    render_mode = 'pure_color'  # 默认纯色
                    if hasattr(self, 'params_widget') and self.params_widget:
                        if hasattr(self.params_widget, 'bg_combo'):
                            bg_color = self.params_widget.bg_combo.currentData() or 'white'
                        if hasattr(self.params_widget, 'render_combo'):
                            render_mode = self.params_widget.render_combo.currentData() or 'pure_color'
                    # 设置背景色、渲染模式和模块引用（用于渲染）
                    self.id_photo_result_widget.current_bg_color = bg_color
                    self.id_photo_result_widget.current_render_mode = render_mode
                    self.id_photo_result_widget.id_photo_module = self.module  # 传递模块引用
                    self.id_photo_result_widget.set_image(image_path, rgba_img)
                    self.id_photo_result_widget.show_fullscreen()
            else:
                # 其他模块使用通用预览
                self.result_widget.image_path = image_path
                self.result_widget.show_fullscreen_image(current_module_name)
        finally:
            self.progress_bar.setVisible(False)
            self.btn_process.setEnabled(True)
            self.btn_process.setText(tr("main.start_process"))
    
    
    def save_result(self):
        """保存结果"""
        if not self.result_path or not os.path.exists(self.result_path):
            StyledMessageBox.warning(self, tr("common.warning"), tr("validation.no_result_to_save"))
            return
        
        # 获取当前模块
        current_tab = self.stacked_widget.currentWidget()
        current_module = current_tab.module if hasattr(current_tab, 'module') else None
        file_path, _ = QFileDialog.getSaveFileName(
            self, tr("save.dialog_title"), "", "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*.*)"
        )
        if file_path:
            try:
                # ????????
                output_dir = os.path.dirname(file_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                
                
                # 如果是证件照模块，使用IDPhotoResultWidget的保存逻辑
                if current_module and current_module.get_name() == "证件照":
                    # 证件照已经在IDPhotoResultWidget中处理，这里不需要再次保存
                    # 用户应该使用全屏预览窗口的保存按钮
                    import shutil
                    shutil.copy2(self.result_path, file_path)
                    StyledMessageBox.success(self, tr("common.success"), tr("save.saved_to", file_path=file_path))
                else:
                    # 其他模块直接复制
                    import shutil
                    shutil.copy2(self.result_path, file_path)
                    StyledMessageBox.success(self, tr("common.success"), tr("save.saved_to", file_path=file_path))
            except Exception as e:
                log_error(str(e), sys.exc_info(), location="ui.main_window.ModuleTab.save_result")
                StyledMessageBox.critical(self, "错误", f"保存失败：{str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self, modules, parent=None):
        super().__init__(parent)
        self.modules = modules
        self._drag_pos = None
        self.init_ui()
        self.apply_styles()
        
        # 设置无边框窗口，透明背景以便圆角可见
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # 屏幕自适应尺寸：根据屏幕分辨率计算合适的窗口尺寸
        window_width, window_height = self._calculate_adaptive_size()
        
        # 强制设置窗口尺寸（确保生效）
        self.resize(window_width, window_height)
        
        # 窗口居中显示
        self._center_on_screen()
    
    def _calculate_adaptive_size(self):
        """根据屏幕分辨率计算自适应窗口尺寸"""
        try:
            from PyQt6.QtGui import QGuiApplication
            # 获取主屏幕尺寸
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()  # 可用区域（排除任务栏）
                screen_width = screen_geometry.width()
                screen_height = screen_geometry.height()
                
                # 计算窗口尺寸：使用屏幕的 75% 大小，但不小于最小尺寸
                adaptive_width = int(screen_width * 0.75)
                adaptive_height = int(screen_height * 0.75)
                
                # 确保不小于最小尺寸
                window_width = max(WINDOW_MIN_WIDTH, min(adaptive_width, WINDOW_DEFAULT_WIDTH))
                window_height = max(WINDOW_MIN_HEIGHT, min(adaptive_height, WINDOW_DEFAULT_HEIGHT))
                
                return window_width, window_height
        except Exception as e:
            pass
        
        # 如果获取失败，使用默认尺寸
        return WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT
    
    def _center_on_screen(self):
        """将窗口居中显示在屏幕上"""
        try:
            from PyQt6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                # 计算居中位置
                x = (screen_geometry.width() - self.width()) // 2 + screen_geometry.x()
                y = (screen_geometry.height() - self.height()) // 2 + screen_geometry.y()
                self.move(x, y)
        except Exception as e:
            pass
    
    def init_ui(self):
        self.setWindowTitle(get_window_title())
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        # 设置窗口图标
        self.setup_icon()
        
        # 创建主布局：透明 central_widget + 圆角内容框（立体感）
        central_widget = QWidget()
        central_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        central_widget.setStyleSheet("background: transparent;")
        self.setCentralWidget(central_widget)
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(0)
        
        content_frame = QFrame()
        content_frame.setObjectName("MainContentFrame")
        content_frame.setStyleSheet("""
            QFrame#MainContentFrame {
                background-color: hsl(222.2, 84%, 4.9%);
                border-radius: 16px;
                border: 1px solid hsl(217.2, 32.6%, 22%);
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        content_frame.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(content_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 右上角：最小化、最大化、关闭（贴边，和系统窗口一致）
        top_button_bar = QWidget()
        top_button_bar.setFixedHeight(36)
        top_button_bar.setStyleSheet("background: transparent;")
        top_btn_layout = QHBoxLayout(top_button_bar)
        top_btn_layout.setContentsMargins(0, 0, 0, 0)
        top_btn_layout.setSpacing(0)
        self.locale_combo = StyledComboBox()
        self.locale_combo.setMinimumWidth(148)
        self.locale_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.locale_combo.setStyleSheet("""
            QComboBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px 10px;
                padding-right: 28px;
                color: hsl(213, 31%, 91%);
                font-size: 12px;
                min-height: 28px;
            }
            QComboBox:hover {
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QComboBox::drop-down {
                border: none;
                border-left: 1px solid hsl(217.2, 32.6%, 17.5%);
                background: hsl(217.2, 32.6%, 17.5%);
                width: 24px;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                selection-background-color: hsl(221.2, 83.2%, 53.3%);
                selection-color: white;
                color: hsl(213, 31%, 91%);
            }
        """)
        self._populate_locale_combo()
        self.locale_combo.currentIndexChanged.connect(self._on_locale_changed)
        top_btn_layout.addWidget(self.locale_combo)
        top_btn_layout.addSpacing(8)
        top_btn_layout.addStretch()
        btn_style_min = """
            QPushButton {
                background: transparent;
                border: none;
                color: hsl(215, 20.2%, 65.1%);
                font-size: 18px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                padding: 2px 4px 8px 4px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: white;
            }
        """
        btn_style_max = """
            QPushButton {
                background: transparent;
                border: none;
                color: hsl(215, 20.2%, 65.1%);
                font-size: 18px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                padding: 2px 4px 6px 4px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: white;
            }
        """
        btn_style_close = """
            QPushButton {
                background: transparent;
                border: none;
                color: hsl(215, 20.2%, 65.1%);
                font-size: 18px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                padding: 2px 4px 8px 4px;
            }
            QPushButton:hover {
                background-color: hsl(0, 84.2%, 60.2%);
                color: white;
            }
        """
        # 最小化按钮
        self.btn_minimize = QPushButton("─")
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.setStyleSheet(btn_style_min)
        self.btn_minimize.clicked.connect(self._do_minimize)
        top_btn_layout.addWidget(self.btn_minimize)
        
        # 最大化/还原按钮
        self.btn_maximize = QPushButton("◻")
        self.btn_maximize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_maximize.setStyleSheet(btn_style_max)
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        top_btn_layout.addWidget(self.btn_maximize)
        
        # 关闭按钮
        self.btn_close = QPushButton("✕")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(btn_style_close)
        self.btn_close.clicked.connect(self.close)
        top_btn_layout.addWidget(self.btn_close)
        
        self._top_button_bar = top_button_bar
        layout.addWidget(top_button_bar)
        
        # 主内容区域
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        
        # 功能菜单区域（方块卡片）- 移到这里
        self.menu_widget = QWidget()
        menu_layout = QHBoxLayout(self.menu_widget)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(24)
        menu_layout.addStretch()
        
        self.module_buttons = []
        self.stacked_widget = QStackedWidget()
        
        # 为每个模块创建按钮和页面（证件照：仅 Logo + 两行文字，无图标按钮）
        for i, module in enumerate(self.modules):
            btn_container = QWidget()
            btn_layout = QVBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(8)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if module.get_name() == "证件照":
                # 证件照：第一行大、第二行小、两行完全平行，字间距拉大
                panel_block = QWidget()
                panel_block.setStyleSheet("background: transparent;")
                panel_inner = QVBoxLayout(panel_block)
                panel_inner.setContentsMargins(0, 0, 0, 0)
                panel_inner.setSpacing(6)
                name_c = QLabel(tr("app.id_photo_name"))
                name_c.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_c.setStyleSheet("color: hsl(213, 31%, 91%); font-size: 38px; font-weight: 600; letter-spacing: 8px; background: transparent;")
                panel_inner.addWidget(name_c, alignment=Qt.AlignmentFlag.AlignCenter)
                sub_c = QLabel(tr("app.id_photo_tagline"))
                sub_c.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sub_c.setStyleSheet("color: hsl(215, 20.2%, 65.1%); font-size: 14px; letter-spacing: 10px; background: transparent;")
                panel_inner.addWidget(sub_c, alignment=Qt.AlignmentFlag.AlignCenter)
                menu_layout.addWidget(panel_block, 0, Qt.AlignmentFlag.AlignCenter)
            else:
                # 其他模块：保留图标按钮 + 名称
                icon_text = module.get_icon()
                icon_size = 32
                btn = QPushButton(icon_text)
                btn.setFixedSize(80, 80)
                btn.setCheckable(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: hsl(217.2, 32.6%, 17.5%);
                        border: 2px solid hsl(217.2, 32.6%, 17.5%);
                        border-radius: 16px;
                        font-size: {icon_size}px;
                    }}
                    QPushButton:hover {{
                        background-color: hsl(215, 27.9%, 22%);
                        border-color: hsl(221.2, 83.2%, 53.3%);
                    }}
                    QPushButton:checked {{
                        background-color: hsl(221.2, 83.2%, 53.3%);
                        border-color: hsl(221.2, 83.2%, 53.3%);
                    }}
                """)
                btn_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
                name_label = QLabel(module.get_name())
                name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_label.setStyleSheet("color: hsl(213, 31%, 91%); font-size: 12px; font-weight: 500; background: transparent;")
                btn_layout.addWidget(name_label)
                btn.clicked.connect(lambda checked, idx=i: self.switch_module(idx))
                menu_layout.addWidget(btn_container)
                self.module_buttons.append(btn)
            
            # 创建模块页面
            tab = ModuleTab(module, self)
            self.stacked_widget.addWidget(tab)
        
        menu_layout.addStretch()
        self._drag_widget = self.menu_widget
        content_layout.addWidget(self.menu_widget)
        
        # 内容区域
        content_layout.addWidget(self.stacked_widget, stretch=1)
        
        # 底部：联系信息
        self.footer_label = QLabel()
        self.footer_label.setText(get_footer_text())
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                font-size: 12px;
                padding: 8px 0;
            }
        """)
        content_layout.addWidget(self.footer_label)
        
        layout.addWidget(content_area, stretch=1)
        outer_layout.addWidget(content_frame, stretch=1)
        
        # 默认选中第一个
        if self.module_buttons:
            self.module_buttons[0].setChecked(True)
    
    def switch_module(self, index):
        """切换功能模块"""
        for i, btn in enumerate(self.module_buttons):
            btn.setChecked(i == index)
        self.stacked_widget.setCurrentIndex(index)

    def _populate_locale_combo(self):
        current_locale = get_current_locale()
        self.locale_combo.blockSignals(True)
        self.locale_combo.clear()
        for locale_code in get_supported_locales():
            label = get_locale_label(locale_code, native=True)
            self.locale_combo.addItem(label, locale_code)
        index = self.locale_combo.findData(current_locale)
        self.locale_combo.setCurrentIndex(index if index >= 0 else 0)
        self.locale_combo.blockSignals(False)

    def _on_locale_changed(self, _index):
        if not hasattr(self, "locale_combo"):
            return
        locale_code = self.locale_combo.currentData()
        if not locale_code or locale_code == get_current_locale():
            return
        save_locale(locale_code)
        set_locale(locale_code)
        self._rebuild_ui()

    def _rebuild_ui(self):
        current_index = 0
        if hasattr(self, "stacked_widget") and self.stacked_widget is not None:
            current_index = self.stacked_widget.currentIndex()
        old_central = self.centralWidget()
        if old_central is not None:
            old_central.deleteLater()
        self.init_ui()
        self.apply_styles()
        self.setWindowTitle(get_window_title())
        if self.module_buttons:
            current_index = max(0, min(current_index, len(self.module_buttons) - 1))
            self.switch_module(current_index)
    
    def get_logo_pixmap(self):
        """优先从 logo.png 加载 Logo，否则用 Base64"""
        try:
            from utils.image_utils import get_resource_path
            logo_path = get_resource_path("logo.png")
            if os.path.exists(logo_path):
                return QPixmap(logo_path)
        except Exception:
            pass
        try:
            from ui.logo_base64 import LOGO_PNG_BASE64
            data = base64.b64decode(LOGO_PNG_BASE64)
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            return pixmap
        except Exception:
            return None
    
    def setup_icon(self):
        """设置窗口图标(从Base64或文件)"""
        try:
            from utils.image_utils import get_resource_path
            icon_path = get_resource_path("logo.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except:
            pass
    
    def apply_styles(self):
        """应用Tailwind CSS + Shadcn UI样式"""
        self.setStyleSheet(TAILWIND_SHADCN_STYLESHEET)
    
    def _do_minimize(self):
        """最小化窗口（无边框窗口下 setWindowState 比 showMinimized 更可靠）"""
        self.setWindowState(Qt.WindowState.WindowMinimized)
    
    def _toggle_maximize(self):
        """切换最大化/还原窗口"""
        if self.isMaximized():
            self.showNormal()
            self.btn_maximize.setText("◻")  # 还原时显示最大化图标（空心方形）
        else:
            self.showMaximized()
            self.btn_maximize.setText("▢")  # 最大化时显示还原图标（双方形）

    def _is_in_drag_widget(self, event):
        """是否点击在可拖拽区域：顶部整块（标题+副标题那一带），排除最小化/最大化/关闭按钮"""
        gp = event.globalPosition().toPoint()
        # 在“标题那一行”（menu_widget）内 → 可拖拽
        if hasattr(self, '_drag_widget') and self._drag_widget is not None:
            local = self._drag_widget.mapFromGlobal(gp)
            if self._drag_widget.rect().contains(local):
                return True
        # 在“最顶栏”（含最小化/最大化/关闭）内，但不在按钮上 → 可拖拽
        if hasattr(self, '_top_button_bar') and self._top_button_bar is not None:
            local_bar = self._top_button_bar.mapFromGlobal(gp)
            if not self._top_button_bar.rect().contains(local_bar):
                return False
            if self.btn_minimize.rect().contains(self.btn_minimize.mapFromGlobal(gp)):
                return False
            if self.btn_maximize.rect().contains(self.btn_maximize.mapFromGlobal(gp)):
                return False
            if self.btn_close.rect().contains(self.btn_close.mapFromGlobal(gp)):
                return False
            return True
        return False
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于拖拽窗口"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_in_drag_widget(event):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖拽移动窗口"""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self._drag_pos = None
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """双击第一行区域最大化/还原"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_in_drag_widget(event):
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                event.accept()
        super().mouseDoubleClickEvent(event)
