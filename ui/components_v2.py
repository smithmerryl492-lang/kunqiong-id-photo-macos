"""通用UI组件"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog, QSlider, QColorDialog,
    QFrame, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem,
    QSizePolicy
)
from ui.custom_widgets import StyledMessageBox, ImageResizeDialog
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QRect, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QWheelEvent, QIcon, QBrush, QMouseEvent
import os
import cv2
import numpy as np
from utils.image_utils import cv2_imread


class ImageLabelWithBackground(QLabel):
    """带有10%透明度背景图的QLabel"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.bg_pixmap = None
        self.bg_opacity = 0.1  # 10%透明度
        self._has_image = False  # 标记是否显示了图片
        self._load_bg_image()
    
    def _load_bg_image(self):
        """加载背景图"""
        from utils.image_utils import get_resource_path
        biglogo_path = get_resource_path("biglogo.png")
        if os.path.exists(biglogo_path):
            self.bg_pixmap = QPixmap(biglogo_path)
    
    def set_bg_visible(self, visible: bool):
        """设置背景图是否可见"""
        self._show_bg = visible
        self.update()

    def set_has_image(self, has_image: bool):
        """设置是否有图片内容"""
        self._has_image = has_image
        self.update()
    
    def paintEvent(self, event):
        """重绘事件，绘制带透明度的背景图"""
        if self._has_image:
            # 有图片时，不显示背景图
            super().paintEvent(event)
        else:
            # 没有图片时，显示带透明度的背景图
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 绘制背景图（10%透明度，完整显示 LOGO）
            if self.bg_pixmap and not self.bg_pixmap.isNull():
                label_rect = self.rect()
                pixmap_size = self.bg_pixmap.size()
                
                # 使用较小缩放比例，保证整张 LOGO 都在区域内可见
                scale_x = label_rect.width() / pixmap_size.width()
                scale_y = label_rect.height() / pixmap_size.height()
                scale = min(scale_x, scale_y)
                
                scaled_width = int(pixmap_size.width() * scale)
                scaled_height = int(pixmap_size.height() * scale)
                
                x = (label_rect.width() - scaled_width) // 2
                y = (label_rect.height() - scaled_height) // 2
                
                painter.setOpacity(self.bg_opacity)
                painter.drawPixmap(x, y, scaled_width, scaled_height, self.bg_pixmap)
                painter.setOpacity(1.0)
            
            # 绘制文字（如果有）
            if self.text():
                painter.setPen(QColor(148, 163, 184))  # 浅灰色文字
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
            
            painter.end()


class ImagePreviewWidgetV2(QWidget):
    """Tailwind风格的图片预览组件，工具栏在图片上方"""

    # 信号：当mask更新时发出
    mask_updated = pyqtSignal(str)  # 发出mask文件路径
    # 信号：当图片加载时发出
    image_loaded = pyqtSignal(str)  # 发出图片文件路径
    # 适应框/实际大小：图片大于显示区时显示切换按钮
    fit_button_visible = pyqtSignal(bool)
    fit_mode_changed = pyqtSignal(bool)  # True=适应框, False=实际大小
    
    def __init__(self, parent=None, params_widget=None, module_name="", module_description="", module=None):
        super().__init__(parent)
        self.original_image = None
        self.display_image = None
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 3.0  # 限制最大缩放防止内存溢出
        self._display_fit_mode = True   # True=适应框(等比例缩放到可见), False=实际大小(100%)
        self._fit_scale = 1.0           # 适应框时的缩放比（图片大于框时计算）
        self.drawing = False
        self.panning = False
        self.mode = 'brush'  # 'brush' 或 'pan'
        self.last_point = None
        self.pan_start_point = None
        self.brush_size = 10  # 默认笔刷大小
        self.brush_color = QColor(255, 0, 0)  # 默认红色
        self.brush_alpha = 128  # 透明度 0-255
        self.mask = None
        self.mask_path = None
        self.current_image_path = None  # 当前加载的图片路径
        self._is_wheel_zoom = False  # 标记是否正在滚轮缩放
        self.params_widget = params_widget  # 模块参数组件
        self.module_name = module_name
        self.module_description = module_description
        self.module = module  # 模块对象，用于获取配置要求

        self.init_ui()
    
    def init_ui(self):
        """初始化UI - Tailwind风格"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)  # 统一外边距，确保工具栏和图片区域对齐
        layout.setSpacing(12)  # 工具栏和图片区域之间的间距
        
        # 工具栏（Tailwind风格）
        toolbar = QWidget()
        toolbar.setProperty("class", "toolbar")
        toolbar.setStyleSheet("""
            QWidget[class="toolbar"] {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 10)  # 统一边距，与图片区域对齐
        toolbar_layout.setSpacing(12)
        
        # 导入图片按钮
        self.btn_load = QPushButton("📁 导入图片")
        self.btn_load.setProperty("class", "secondary")
        self.btn_load.setStyleSheet("""
            QPushButton[class="secondary"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton[class="secondary"]:hover {
                background-color: hsl(215, 27.9%, 16.9%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
        """)
        self.btn_load.clicked.connect(self.load_image_dialog)
        toolbar_layout.addWidget(self.btn_load)
        
        # 分隔线
        separator = QFrame()
        separator.setProperty("class", "separator-vertical")
        separator.setStyleSheet("""
            QFrame[class="separator-vertical"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                min-width: 1px;
                max-width: 1px;
            }
        """)
        toolbar_layout.addWidget(separator)
        
        # 笔刷功能区容器（带背景色块）- 靠左排列
        brush_container = QWidget()
        brush_container.setProperty("class", "brush-container")
        brush_container.setStyleSheet("""
            QWidget[class="brush-container"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        brush_container_layout = QHBoxLayout(brush_container)
        brush_container_layout.setContentsMargins(10, 6, 10, 6)
        # 根据是否有参数调整间距
        spacing = 6 if self.params_widget else 12
        brush_container_layout.setSpacing(spacing)
        
        # 笔刷/移动模式切换按钮
        self.btn_brush = QPushButton("🖌️ 笔刷")
        self.btn_brush.setCheckable(True)
        self.btn_brush.setChecked(True)
        self.btn_brush.setToolTip("笔刷模式：涂抹标记区域（当前模式）")
        self.btn_brush.setProperty("class", "icon-button")
        self.btn_brush.setStyleSheet("""
            QPushButton[class="icon-button"] {
                background-color: transparent;
                color: hsl(215, 20.2%, 65.1%);
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px;
                min-width: 36px;
                min-height: 36px;
            }
            QPushButton[class="icon-button"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border-color: hsl(217.2, 32.6%, 17.5%);
            }
            QPushButton[class="icon-button"]:checked {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
            }
            QPushButton[class="icon-button"]:checked:hover {
                background-color: hsl(217.2, 91.2%, 59.8%);
            }
        """)
        self.btn_brush.clicked.connect(self.set_brush_mode)
        brush_container_layout.addWidget(self.btn_brush)
        
        self.btn_pan = QPushButton("✋ 移动")
        self.btn_pan.setCheckable(True)
        self.btn_pan.setChecked(False)
        self.btn_pan.setToolTip("移动模式：拖拽图片")
        self.btn_pan.setProperty("class", "icon-button")
        self.btn_pan.setStyleSheet("""
            QPushButton[class="icon-button"] {
                background-color: transparent;
                color: hsl(215, 20.2%, 65.1%);
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px;
                min-width: 36px;
                min-height: 36px;
            }
            QPushButton[class="icon-button"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border-color: hsl(217.2, 32.6%, 17.5%);
            }
            QPushButton[class="icon-button"]:checked {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
            }
            QPushButton[class="icon-button"]:checked:hover {
                background-color: hsl(217.2, 91.2%, 59.8%);
            }
        """)
        self.btn_pan.clicked.connect(self.set_pan_mode)
        brush_container_layout.addWidget(self.btn_pan)
        
        # 分隔线
        separator2 = QFrame()
        separator2.setProperty("class", "separator-vertical")
        separator2.setStyleSheet("""
            QFrame[class="separator-vertical"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                min-width: 1px;
                max-width: 1px;
            }
        """)
        brush_container_layout.addWidget(separator2)
        
        # 颜色选择按钮
        self.btn_color = QPushButton("🎨")
        self.btn_color.setToolTip("选择笔刷颜色")
        self.btn_color.setProperty("class", "icon-button")
        self.btn_color.setStyleSheet("""
            QPushButton[class="icon-button"] {
                background-color: transparent;
                color: hsl(215, 20.2%, 65.1%);
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px;
                min-width: 36px;
                min-height: 36px;
            }
            QPushButton[class="icon-button"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border-color: hsl(217.2, 32.6%, 17.5%);
            }
        """)
        self.btn_color.clicked.connect(self.choose_brush_color)
        brush_container_layout.addWidget(self.btn_color)
        
        # 透明度滑块
        alpha_layout = QHBoxLayout()
        alpha_layout.setSpacing(8)
        alpha_label = QLabel("透明度:")
        alpha_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none;")
        alpha_layout.addWidget(alpha_label)
        
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.alpha_slider.setMinimum(0)
        self.alpha_slider.setMaximum(255)
        self.alpha_slider.setValue(self.brush_alpha)
        self.alpha_slider.setMinimumWidth(100)
        self.alpha_slider.valueChanged.connect(self.on_alpha_changed)
        alpha_layout.addWidget(self.alpha_slider)
        
        self.alpha_value_label = QLabel(f"{int(self.brush_alpha / 255 * 100)}%")
        self.alpha_value_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none;")
        self.alpha_value_label.setMinimumWidth(40)
        alpha_layout.addWidget(self.alpha_value_label)
        brush_container_layout.addLayout(alpha_layout)
        
        # 笔刷大小
        brush_layout = QHBoxLayout()
        brush_layout.setSpacing(8)
        brush_label = QLabel("笔刷:")
        brush_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none;")
        brush_layout.addWidget(brush_label)
        
        self.brush_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_slider.setMinimum(5)
        self.brush_slider.setMaximum(100)
        self.brush_slider.setValue(self.brush_size)
        self.brush_slider.setMinimumWidth(120)
        self.brush_slider.valueChanged.connect(self.on_brush_size_changed)
        brush_layout.addWidget(self.brush_slider)
        
        self.brush_size_label = QLabel(f"{self.brush_size}px")
        self.brush_size_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none;")
        self.brush_size_label.setMinimumWidth(50)
        brush_layout.addWidget(self.brush_size_label)
        brush_container_layout.addLayout(brush_layout)
        
        # 橡皮擦按钮
        self.eraser_mode = False
        eraser_btn_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 91.2%, 59.8%);
            }
            QPushButton:checked {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(215, 20.2%, 65.1%);
            }
            QPushButton:checked:hover {
                background-color: hsl(215, 27.9%, 22%);
            }
        """
        self.btn_eraser = QPushButton("🧹 橡皮擦")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.setChecked(False)
        self.btn_eraser.setToolTip("点击切换橡皮擦模式")
        self.btn_eraser.setStyleSheet(eraser_btn_style)
        self.btn_eraser.clicked.connect(self.toggle_eraser_mode)
        brush_container_layout.addWidget(self.btn_eraser)
        
        toolbar_layout.addWidget(brush_container)
        
        # 如果有参数组件，紧跟在导入按钮后面
        if self.params_widget:
            # 分隔线
            separator = QFrame()
            separator.setProperty("class", "separator-vertical")
            separator.setStyleSheet("""
                QFrame[class="separator-vertical"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    min-width: 1px;
                    max-width: 1px;
                }
            """)
            toolbar_layout.addWidget(separator)
            toolbar_layout.addWidget(self.params_widget)
        
        toolbar_layout.addStretch()
        
        # 全屏按钮
        self.btn_fullscreen = QPushButton("⛶ 全屏")
        self.btn_fullscreen.setProperty("class", "outline")
        self.btn_fullscreen.setStyleSheet("""
            QPushButton[class="outline"] {
                background-color: transparent;
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton[class="outline"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
        """)
        self.btn_fullscreen.setEnabled(False)  # 初始禁用，加载图片后启用
        toolbar_layout.addWidget(self.btn_fullscreen)
        
        layout.addWidget(toolbar)
        
        # 图片显示区域
        self.image_container = QWidget()
        self.image_container.setProperty("class", "card")
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: hsl(222.2, 47.4%, 11.2%);
                border: none;
            }
        """)
        
        # 滚动区域内的widget
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图片标签
        self.image_label = ImageLabelWithBackground("点击上方\"导入图片\"或点击此处选择图片")
        if self.module_description:
            hint_text = f"点击上方\"导入图片\"或点击此处选择图片\n\n📋 功能说明：{self.module_description}"
            # 添加配置要求
            if self.module:
                try:
                    req = self.module.get_system_requirements()
                    hint_text += "\n\n💻 电脑配置要求："
                    hint_text += f"\n\u3000最低配置：CPU {req['min_cpu']} + 内存 {req['min_ram']}"
                    hint_text += f"\n\u3000推荐配置：CPU {req['rec_cpu']} + 内存 {req['rec_ram']}"
                except:
                    pass
            self.image_label.setText(hint_text)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                border: 2px dashed hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                font-size: 14px;
                padding: 20px;
            }
        """)
        self.default_label_style = self.image_label.styleSheet()
        self.image_label.setScaledContents(False)
        # 设置大小策略：初始状态扩展填满，有图片后固定大小
        from PyQt6.QtWidgets import QSizePolicy
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 设置默认光标为手型（没有图片时可以点击导入）
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)

        # 鼠标事件
        self.image_label.mousePressEvent = self.on_mouse_press
        self.image_label.mouseMoveEvent = self.on_mouse_move
        self.image_label.mouseReleaseEvent = self.on_mouse_release
        self.image_label.wheelEvent = self.on_wheel

        self.scroll_layout.addWidget(self.image_label)
        self.scroll_area.setWidget(self.scroll_widget)
        container_layout.addWidget(self.scroll_area)
        layout.addWidget(self.image_container, stretch=1)
    
    def load_image_dialog(self):
        """打开文件对话框选择图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, image_path: str):
        """加载图片"""
        if not os.path.exists(image_path):
            StyledMessageBox.warning(self, "错误", "图片文件不存在")
            return False

        try:
            # 检查图片大小，超大图弹出缩放对话框
            action, scale = ImageResizeDialog.check_and_resize(self, image_path)
            
            if action == "cancel":
                return False  # 用户取消
            
            img = cv2_imread(image_path)
            if img is None:
                StyledMessageBox.warning(self, "错误", "无法读取图片")
                return False
            
            # 如果需要缩放
            if action == "resize" and scale < 1.0:
                h, w = img.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            self.current_image_path = image_path
            self.original_image = img.copy()
            self.scale_factor = 1.0
            self.offset_x = 0
            self.offset_y = 0
            
            # 初始化mask
            h, w = img.shape[:2]
            self.mask = np.zeros((h, w, 4), dtype=np.uint8)
            
            # 更新显示
            self.update_display()
            
            # 更新UI状态
            self.image_label.set_has_image(True)
            # 有图片后，根据模式设置光标（笔刷模式用默认光标，平移模式用手型）
            if self.mode == 'pan':
                self.image_label.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
            # 启用全屏按钮（如果存在）
            if hasattr(self, 'btn_fullscreen'):
                self.btn_fullscreen.setEnabled(True)
            # 初始化缩放滑块（如果启用缩放）
            if self.enable_zoom and hasattr(self, 'zoom_slider'):
                self.zoom_slider.setValue(100)
                self.scale_factor = 1.0
                if hasattr(self, 'zoom_value_label'):
                    self.zoom_value_label.setText("100%")
            self.image_loaded.emit(image_path)
            # 延迟检查：等布局完成后 viewport 才有正确尺寸，再决定是否显示“适应框/实际大小”按钮
            QTimer.singleShot(150, self._update_fit_button_visibility)
            return True
        except Exception as e:
            StyledMessageBox.warning(self, "错误", f"加载图片失败: {str(e)}")
            return False
    
    def update_display(self):
        """更新显示"""
        if self.original_image is None:
            return
        
        # 计算缩放后的尺寸
        h, w = self.original_image.shape[:2]
        scaled_width = int(w * self.scale_factor)
        scaled_height = int(h * self.scale_factor)
        
        # 缩放图片
        if scaled_width > 0 and scaled_height > 0:
            display = cv2.resize(self.original_image, (scaled_width, scaled_height), interpolation=cv2.INTER_LANCZOS4)
        else:
            display = self.original_image.copy()
        
        # 将mask叠加到图片上
        if self.mask is not None and self.mask.sum() > 0:
            # 缩放mask到显示尺寸
            mask_scaled = cv2.resize(self.mask, (scaled_width, scaled_height), interpolation=cv2.INTER_NEAREST)
            # 红色半透明mask
            mask_colored = np.zeros_like(display)
            mask_colored[:, :, 2] = mask_scaled[:, :, 3]  # 红色通道
            display = cv2.addWeighted(display, 0.7, mask_colored, 0.3, 0)
        
        # 转换为QPixmap
        h_display, w_display = display.shape[:2]
        if len(display.shape) == 3:
            bytes_per_line = 3 * w_display
            q_image = QImage(display.data, w_display, h_display, bytes_per_line, QImage.Format.Format_BGR888)
        else:
            bytes_per_line = w_display
            q_image = QImage(display.data, w_display, h_display, bytes_per_line, QImage.Format.Format_Grayscale8)
        
        pixmap = QPixmap.fromImage(q_image)
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(scaled_width, scaled_height)
    
    def _update_fit_button_visibility(self):
        """图片加载后：若大于显示区则显示“适应框/实际大小”按钮并默认适应框"""
        if self.original_image is None or not hasattr(self, 'scroll_area'):
            self.fit_button_visible.emit(False)
            return
        h, w = self.original_image.shape[:2]
        vp = self.scroll_area.viewport().size()
        vw, vh = vp.width(), vp.height()
        # viewport 尚未布局好时可能为 0，用最小有效尺寸判断
        if vw < 100 or vh < 100:
            vw, vh = max(vw, 400), max(vh, 300)
        if w <= vw and h <= vh:
            self.fit_button_visible.emit(False)
            return
        self._fit_scale = min(vw / w, vh / h)
        self._display_fit_mode = True
        self.scale_factor = self._fit_scale
        self.update_display()
        self.fit_button_visible.emit(True)
        self.fit_mode_changed.emit(True)
    
    def set_display_fit(self, fit: bool):
        """设置显示模式：True=适应框，False=实际大小"""
        self._display_fit_mode = fit
        self.scale_factor = self._fit_scale if fit else 1.0
        self.update_display()
        self.fit_mode_changed.emit(fit)
    
    def toggle_fit_actual(self):
        """切换 适应框 / 实际大小"""
        self.set_display_fit(not self._display_fit_mode)
    
    def get_display_fit_mode(self) -> bool:
        """当前是否为适应框模式"""
        return self._display_fit_mode
    
    def screen_to_image_coords(self, screen_pos):
        """将屏幕坐标转换为图片坐标"""
        if self.original_image is None:
            return 0, 0
        
        # 获取label的位置和大小
        label_rect = self.image_label.geometry()
        
        # 计算相对于label的坐标
        rel_x = screen_pos.x() - label_rect.x()
        rel_y = screen_pos.y() - label_rect.y()
        
        # 转换为图片坐标（考虑缩放）
        img_x = rel_x / self.scale_factor
        img_y = rel_y / self.scale_factor
        
        return img_x, img_y
    
    def set_brush_mode(self):
        """设置笔刷模式"""
        self.mode = 'brush'
        self.btn_brush.setChecked(True)
        self.btn_pan.setChecked(False)
        self.btn_brush.setToolTip("笔刷模式：涂抹标记区域（当前模式）")
        self.btn_pan.setToolTip("移动模式：拖拽图片")
    
    def set_pan_mode(self):
        """设置移动模式"""
        self.mode = 'pan'
        self.btn_brush.setChecked(False)
        self.btn_pan.setChecked(True)
        self.btn_brush.setToolTip("笔刷模式：涂抹标记区域")
        self.btn_pan.setToolTip("移动模式：拖拽图片（当前模式）")
    
    def choose_brush_color(self):
        """选择笔刷颜色"""
        color = QColorDialog.getColor(self.brush_color, self, "选择笔刷颜色")
        if color.isValid():
            self.brush_color = color
            # 如果已有mask，更新颜色
            if self.mask is not None and self.mask.sum() > 0:
                mask_alpha = self.mask[:, :, 3]
                self.mask[:, :, 0] = self.brush_color.blue()
                self.mask[:, :, 1] = self.brush_color.green()
                self.mask[:, :, 2] = self.brush_color.red()
                self.mask[:, :, 3] = mask_alpha
                self.update_display()
    
    def on_alpha_changed(self, value):
        """透明度改变"""
        self.brush_alpha = value
        self.alpha_value_label.setText(f"{int(value / 255 * 100)}%")
    
    def on_brush_size_changed(self, value):
        """笔刷大小改变"""
        self.brush_size = value
        self.brush_size_label.setText(f"{value}px")
    
    def toggle_eraser_mode(self):
        """切换橡皮擦模式"""
        self.eraser_mode = self.btn_eraser.isChecked()
    
    def on_mouse_press(self, event):
        """鼠标按下"""
        # 如果没有图片，点击图片框导入图片
        if self.original_image is None:
            # 确保光标是手型
            self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
            if event.button() == Qt.MouseButton.LeftButton:
                self.load_image_dialog()
            return
        
        needs_pan = (event.modifiers() & Qt.KeyboardModifier.ControlModifier) or self.mode == 'pan'
        
        if needs_pan and event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.pan_start_point = event.position()
        elif self.mode == 'brush' and event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.position()
            self.draw_mask(event.position())
    
    def on_mouse_move(self, event):
        """鼠标移动"""
        if self.panning and self.pan_start_point:
            # 平移图片
            delta_x = event.position().x() - self.pan_start_point.x()
            delta_y = event.position().y() - self.pan_start_point.y()
            
            scroll_bar_h = self.scroll_area.horizontalScrollBar()
            scroll_bar_v = self.scroll_area.verticalScrollBar()
            
            if scroll_bar_h:
                scroll_bar_h.setValue(scroll_bar_h.value() - int(delta_x))
            if scroll_bar_v:
                scroll_bar_v.setValue(scroll_bar_v.value() - int(delta_y))
            
            self.pan_start_point = event.position()
        elif self.drawing and self.last_point:
            self.draw_mask(event.position())
            self.last_point = event.position()
    
    def on_mouse_release(self, event):
        """鼠标释放"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            self.panning = False
            self.last_point = None
            self.pan_start_point = None
            if self.mask is not None:
                self.save_mask()
    
    def on_wheel(self, event: QWheelEvent):
        """鼠标滚轮 - 缩放"""
        if self.original_image is None:
            return
        
        # 获取鼠标位置（相对于label）
        mouse_pos = event.position()
        
        # 获取当前滚动位置
        scroll_bar_h = self.scroll_area.horizontalScrollBar()
        scroll_bar_v = self.scroll_area.verticalScrollBar()
        scroll_x = scroll_bar_h.value() if scroll_bar_h else 0
        scroll_y = scroll_bar_v.value() if scroll_bar_v else 0
        
        # 计算缩放前的图片坐标（考虑滚动位置）
        old_img_x = (mouse_pos.x() + scroll_x) / self.scale_factor
        old_img_y = (mouse_pos.y() + scroll_y) / self.scale_factor
        
        # 缩放
        delta = event.angleDelta().y()
        old_scale = self.scale_factor
        if delta > 0:
            self.scale_factor = min(self.scale_factor * 1.15, self.max_scale)
        else:
            self.scale_factor = max(self.scale_factor / 1.15, self.min_scale)
        
        # 计算缩放后的滚动位置，使鼠标位置对应的图片点保持不变
        new_scroll_x = old_img_x * self.scale_factor - mouse_pos.x()
        new_scroll_y = old_img_y * self.scale_factor - mouse_pos.y()
        
        # 更新显示
        self.update_display()
        
        # 调整滚动位置
        if scroll_bar_h:
            scroll_bar_h.setValue(int(new_scroll_x))
        if scroll_bar_v:
            scroll_bar_v.setValue(int(new_scroll_y))
    
    def zoom_in(self):
        """放大"""
        if self.original_image is None:
            return
        self.scale_factor = min(self.scale_factor * 1.2, self.max_scale)
        self.update_display()
    
    def zoom_out(self):
        """缩小"""
        if self.original_image is None:
            return
        self.scale_factor = max(self.scale_factor / 1.2, self.min_scale)
        self.update_display()
    
    def zoom_fit(self):
        """适应窗口"""
        if self.original_image is None:
            return
        
        # 获取可用空间
        scroll_area_size = self.scroll_area.size()
        available_width = scroll_area_size.width() - 40
        available_height = scroll_area_size.height() - 40
        
        # 计算合适的缩放比例
        h, w = self.original_image.shape[:2]
        scale_x = available_width / w
        scale_y = available_height / h
        self.scale_factor = min(scale_x, scale_y, 1.0)  # 不超过100%
        
        self.update_display()
    
    def draw_mask(self, pos):
        """在mask上绘制"""
        if self.original_image is None or self.mask is None:
            return
        
        img_x, img_y = self.screen_to_image_coords(pos)
        img_x = int(img_x)
        img_y = int(img_y)
        
        h, w = self.original_image.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            brush_size = max(1, int(self.brush_size / self.scale_factor))
            
            if self.eraser_mode:
                # 橡皮擦模式：将mask设为透明（全0）
                color = [0, 0, 0, 0]
            else:
                # 笔刷模式：绘制到RGBA mask
                color = [
                    self.brush_color.blue(),
                    self.brush_color.green(),
                    self.brush_color.red(),
                    self.brush_alpha
                ]
            
            cv2.circle(self.mask, (img_x, img_y), brush_size, color, -1)
            
            if self.last_point:
                last_img_x, last_img_y = self.screen_to_image_coords(self.last_point)
                last_img_x = int(last_img_x)
                last_img_y = int(last_img_y)
                if 0 <= last_img_x < self.original_image.shape[1] and 0 <= last_img_y < self.original_image.shape[0]:
                    cv2.line(self.mask, (last_img_x, last_img_y), (img_x, img_y), color, brush_size * 2)
            
            self.update_display()
    
    def clear_mask(self):
        """清除mask"""
        if self.original_image is not None:
            h, w = self.original_image.shape[:2]
            self.mask = np.zeros((h, w, 4), dtype=np.uint8)
            self.update_display()
            self.save_mask()
            # 发出信号，通知主界面关闭结果面板
            self.mask_updated.emit(None)
    
    def save_mask(self):
        """保存mask到临时文件（转换为灰度图用于处理）"""
        if self.mask is None or self.mask.sum() == 0:
            self.mask_path = None
            return
        
        try:
            import tempfile
            fd, self.mask_path = tempfile.mkstemp(suffix='.png', prefix='mask_')
            os.close(fd)
            # 转换为灰度mask（使用alpha通道）
            gray_mask = self.mask[:, :, 3]  # 使用alpha通道作为mask
            cv2.imwrite(self.mask_path, gray_mask)
            self.mask_updated.emit(self.mask_path)
        except Exception as e:
            StyledMessageBox.warning(self, "警告", f"保存mask失败: {str(e)}")
    
    def get_mask_path(self) -> str:
        """获取mask文件路径"""
        # 确保mask已保存
        if self.mask is not None and self.mask.sum() > 0 and self.mask_path is None:
            self.save_mask()
        return self.mask_path
    
    def has_mask(self) -> bool:
        """检查是否有mask"""
        return self.mask is not None and self.mask.sum() > 0
    
    def set_fullscreen_callback(self, callback):
        """设置全屏按钮回调"""
        self.btn_fullscreen.clicked.connect(callback)


from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem
from PyQt6.QtCore import QRectF, QPointF, QTimer


class ResizableRect(QGraphicsRectItem):
    """可调整大小的矩形框"""
    def __init__(self, rect):
        super().__init__(rect)
        self.setPen(QPen(QColor("red"), 2))
        self.setBrush(QBrush(QColor(255, 0, 0, 50)))
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.resize_dir = None
        self.mouse_press_scene_pos = None
        self.rect_at_press = None
        self.pos_at_press = None
        
        # 8个调整手柄
        self.handles = []
        for _ in range(8):
            h = QGraphicsRectItem(-4, -4, 8, 8, self)
            h.setBrush(QBrush(QColor("blue")))
            h.setPen(QPen(Qt.GlobalColor.white, 1))
            h.hide()
            self.handles.append(h)

    def update_handles(self):
        """更新手柄位置"""
        visible = self.isSelected()
        for h in self.handles:
            h.setVisible(visible)
        if not visible:
            return
            
        r = self.rect()
        pos = [
            r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight(),
            QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()),
            QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y())
        ]
        for h, p in zip(self.handles, pos):
            h.setPos(p)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedChange:
            QTimer.singleShot(0, self.update_handles)
        return super().itemChange(change, value)

    def get_resize_dir(self, pos):
        """获取调整方向"""
        r = self.rect()
        margin = 10
        d = ""
        if abs(pos.y() - r.top()) < margin: d += "T"
        elif abs(pos.y() - r.bottom()) < margin: d += "B"
        if abs(pos.x() - r.left()) < margin: d += "L"
        elif abs(pos.x() - r.right()) < margin: d += "R"
        
        if d: return d
        if r.contains(pos): return "MOVE"
        return None

    def hoverMoveEvent(self, event):
        d = self.get_resize_dir(event.pos())
        if d == "MOVE":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif d:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resize_dir = self.get_resize_dir(event.pos())
            self.mouse_press_scene_pos = event.scenePos()
            self.rect_at_press = self.rect()
            self.pos_at_press = self.pos()
            self.setSelected(True)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_dir:
            delta = event.scenePos() - self.mouse_press_scene_pos
            if self.resize_dir == "MOVE":
                self.setPos(self.pos_at_press + delta)
            else:
                r = QRectF(self.rect_at_press)
                dx, dy = delta.x(), delta.y()
                
                if "T" in self.resize_dir: r.setTop(self.rect_at_press.top() + dy)
                elif "B" in self.resize_dir: r.setBottom(self.rect_at_press.bottom() + dy)
                
                if "L" in self.resize_dir: r.setLeft(self.rect_at_press.left() + dx)
                elif "R" in self.resize_dir: r.setRight(self.rect_at_press.right() + dx)
                
                self.setRect(r.normalized())
                self.update_handles()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.resize_dir = None
        super().mouseReleaseEvent(event)


class MaskGraphicsView(QGraphicsView):
    """支持多矩形选择的图形视图"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.pixmap_item = None
        self.rects = []
        self.current_rect = None
        self.start_pos = None
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background-color: hsl(224, 71.4%, 4.1%); border: none;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def set_image(self, pixmap, existing_rects=None):
        """设置图片 - 100%原图大小显示"""
        self.scene.clear()
        self.rects = []
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(QRectF(pixmap.rect()))
        
        # 重置缩放为100%原图大小
        self.resetTransform()
        
        if existing_rects:
            for r in existing_rects:
                new_rect_item = ResizableRect(QRectF(0, 0, r.width(), r.height()))
                self.scene.addItem(new_rect_item)
                new_rect_item.setPos(r.topLeft())
                self.rects.append(new_rect_item)
                new_rect_item.update_handles()

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if isinstance(item, ResizableRect):
                self.scene.clearSelection()
                item.setSelected(True)
                super().mousePressEvent(event)
            elif item == self.pixmap_item or item is None:
                self.scene.clearSelection()
                self.start_pos = self.mapToScene(event.pos())
                self.current_rect = ResizableRect(QRectF(self.start_pos, self.start_pos))
                self.scene.addItem(self.current_rect)
                self.rects.append(self.current_rect)
                self.current_rect.setSelected(True)
                self.setFocus()
            else:
                super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键删除
            if isinstance(item, ResizableRect):
                self.scene.removeItem(item)
                if item in self.rects:
                    self.rects.remove(item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_pos and self.current_rect:
            curr_pos = self.mapToScene(event.pos())
            self.current_rect.setRect(QRectF(self.start_pos, curr_pos).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_rect:
            r = self.current_rect.rect()
            if r.width() < 5 or r.height() < 5:
                self.scene.removeItem(self.current_rect)
                if self.current_rect in self.rects:
                    self.rects.remove(self.current_rect)
            else:
                self.current_rect.update_handles()
        
        self.start_pos = None
        self.current_rect = None
        super().mouseReleaseEvent(event)

    def get_mask_rects(self):
        """获取所有矩形的场景坐标"""
        return [r.rect().translated(r.pos()) for r in self.rects]

    def keyPressEvent(self, event):
        """键盘事件：方向键微调，Delete删除"""
        selected_items = self.scene.selectedItems()
        target_rect = None
        for item in selected_items:
            if isinstance(item, ResizableRect):
                target_rect = item
                break
        
        if not target_rect:
            super().keyPressEvent(event)
            return

        step = 1
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = 10

        if event.key() == Qt.Key.Key_Left:
            target_rect.moveBy(-step, 0)
        elif event.key() == Qt.Key.Key_Right:
            target_rect.moveBy(step, 0)
        elif event.key() == Qt.Key.Key_Up:
            target_rect.moveBy(0, -step)
        elif event.key() == Qt.Key.Key_Down:
            target_rect.moveBy(0, step)
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.scene.removeItem(target_rect)
            if target_rect in self.rects:
                self.rects.remove(target_rect)
        else:
            super().keyPressEvent(event)

    def clear_all_rects(self):
        """清除所有矩形"""
        for rect in self.rects[:]:
            self.scene.removeItem(rect)
        self.rects.clear()


class ImagePreviewWidgetRect(QWidget):
    """矩形选择模式的图片预览组件，支持多矩形"""

    mask_updated = pyqtSignal(str)
    image_loaded = pyqtSignal(str)
    
    def __init__(self, parent=None, params_widget=None, module_name="", module_description="", module=None):
        super().__init__(parent)
        self.current_image_path = None
        self.original_image = None
        self.params_widget = params_widget
        self.module_name = module_name
        self.module_description = module_description
        self.module = module
        self.mask_path = None
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 工具栏
        toolbar = QWidget()
        toolbar.setProperty("class", "toolbar")
        toolbar.setStyleSheet("""
            QWidget[class="toolbar"] {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)
        
        # 导入按钮
        self.btn_import = QPushButton("📁 导入图片")
        self.btn_import.setProperty("class", "secondary")
        self.btn_import.setStyleSheet("""
            QPushButton[class="secondary"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton[class="secondary"]:hover {
                background-color: hsl(215, 27.9%, 16.9%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
        """)
        self.btn_import.clicked.connect(self.import_image)
        toolbar_layout.addWidget(self.btn_import)
        
        # 如果有参数组件，紧跟在导入按钮后面
        if self.params_widget:
            # 分隔线
            separator = QFrame()
            separator.setProperty("class", "separator-vertical")
            separator.setStyleSheet("""
                QFrame[class="separator-vertical"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    min-width: 1px;
                    max-width: 1px;
                }
            """)
            toolbar_layout.addWidget(separator)
            toolbar_layout.addWidget(self.params_widget)
        
        toolbar_layout.addStretch()
        
        # 清除按钮
        self.btn_clear = QPushButton("🗑️ 清除全部")
        self.btn_clear.setProperty("class", "outline")
        self.btn_clear.setStyleSheet("""
            QPushButton[class="outline"] {
                background-color: transparent;
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton[class="outline"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
        """)
        self.btn_clear.clicked.connect(self.clear_rect)
        toolbar_layout.addWidget(self.btn_clear)
        
        # 全屏按钮
        self.btn_fullscreen = QPushButton("⛶ 全屏")
        self.btn_fullscreen.setProperty("class", "outline")
        self.btn_fullscreen.setStyleSheet("""
            QPushButton[class="outline"] {
                background-color: transparent;
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton[class="outline"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
        """)
        self.btn_fullscreen.setEnabled(False)  # 初始禁用，加载图片后启用
        toolbar_layout.addWidget(self.btn_fullscreen)
        
        layout.addWidget(toolbar)
        
        # 图形视图
        self.graphics_view = MaskGraphicsView()
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.graphics_view, stretch=1)
        
        # 显示提示文本的标签（图片未加载时）- 与ImagePreviewWidgetV2格式一致
        hint_text = "点击上方\"导入图片\"或点击此处选择图片"
        if self.module_description:
            hint_text += f"\n\n📋 功能说明：{self.module_description}"
        
        # 添加配置要求
        if self.module:
            try:
                req = self.module.get_system_requirements()
                hint_text += "\n\n💻 电脑配置要求："
                hint_text += f"\n\u3000最低配置：CPU {req['min_cpu']} + 内存 {req['min_ram']}"
                hint_text += f"\n\u3000推荐配置：CPU {req['rec_cpu']} + 内存 {req['rec_ram']}"
            except:
                pass
        
        hint_text += "\n\n💡 操作提示：左键拖拽绘制 | 右键/Delete删除 | 方向键微调"
        self.hint_label = ImageLabelWithBackground(hint_text)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                font-size: 14px;
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                padding: 20px;
            }
        """)
        self.hint_label.setWordWrap(True)
        self.hint_label.setCursor(Qt.CursorShape.PointingHandCursor)
        # 点击导入
        self.hint_label.mousePressEvent = self._on_hint_clicked
        layout.addWidget(self.hint_label, stretch=1)
        
        # 支持拖拽
        self.setAcceptDrops(True)
        
        # 初始状态：显示提示，隐藏图形视图
        self.graphics_view.hide()
        self.hint_label.show()
    
    def _on_hint_clicked(self, event):
        """点击提示区域导入图片"""
        # 只有在没有图片时才允许导入
        if self.current_image_path is None or self.original_image is None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.import_image()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    self.load_image(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def import_image(self):
        """导入图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, image_path: str) -> bool:
        """加载图片"""
        if not os.path.exists(image_path):
            return False
        
        try:
            # 检查图片大小，超大图弹出缩放对话框
            action, scale = ImageResizeDialog.check_and_resize(self, image_path)
            
            if action == "cancel":
                return False  # 用户取消
            
            img = cv2_imread(image_path)
            if img is None:
                return False
            
            # 如果需要缩放
            if action == "resize" and scale < 1.0:
                h, w = img.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            self.current_image_path = image_path
            self.original_image = img
            self.mask_path = None
            
            # 将cv2图像转换为QPixmap
            h, w = img.shape[:2]
            if len(img.shape) == 3:
                bytes_per_line = 3 * w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
            else:
                bytes_per_line = w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image)
            
            # 切换显示
            self.hint_label.hide()
            self.graphics_view.show()
            
            self.graphics_view.set_image(pixmap)
            self.btn_fullscreen.setEnabled(True)  # 启用全屏按钮
            self.image_loaded.emit(image_path)
            return True
        except Exception as e:
            StyledMessageBox.warning(self, "错误", f"加载图片失败: {str(e)}")
            return False
    
    def clear_rect(self):
        """清除所有选区"""
        self.graphics_view.clear_all_rects()
        self.mask_path = None
        self.mask_updated.emit(None)
    
    def save_mask(self):
        """保存mask到临时文件"""
        rects = self.graphics_view.get_mask_rects()
        if not rects or self.original_image is None:
            self.mask_path = None
            return
        
        try:
            import tempfile
            fd, self.mask_path = tempfile.mkstemp(suffix='.png', prefix='mask_rect_')
            os.close(fd)
            
            h, w = self.original_image.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            
            for rect in rects:
                left = max(0, int(rect.left()))
                top = max(0, int(rect.top()))
                right = min(w, int(rect.right()))
                bottom = min(h, int(rect.bottom()))
                mask[top:bottom, left:right] = 255
            
            cv2.imwrite(self.mask_path, mask)
            self.mask_updated.emit(self.mask_path)
        except Exception as e:
            StyledMessageBox.warning(self, "警告", f"保存mask失败: {str(e)}")
    
    def get_mask_path(self) -> str:
        """获取mask文件路径"""
        # 实时保存mask
        self.save_mask()
        return self.mask_path
    
    def has_mask(self) -> bool:
        """检查是否有mask"""
        return len(self.graphics_view.rects) > 0
    
    def set_fullscreen_callback(self, callback):
        """设置全屏按钮回调"""
        self.btn_fullscreen.clicked.connect(callback)
    
    def get_rects(self):
        """获取所有矩形"""
        return self.graphics_view.get_mask_rects()
    
    def set_rects(self, rects):
        """设置矩形（从全屏编辑器返回）"""
        if self.current_image_path:
            pixmap = QPixmap(self.current_image_path)
            self.graphics_view.set_image(pixmap, rects)
            self.save_mask()


class ImagePreviewWidgetCrop(QWidget):
    """裁剪模式的图片预览组件，支持单个可拖拽裁剪框"""
    
    crop_updated = pyqtSignal(int, int, int, int)  # 发出裁剪框坐标 (x, y, w, h)
    image_loaded = pyqtSignal(str)
    fullscreen_requested = pyqtSignal()  # 请求打开全屏功能窗口
    
    def __init__(self, parent=None, params_widget=None, module_name="", module_description="", module=None):
        super().__init__(parent)
        self.current_image_path = None
        self.original_image = None
        self.params_widget = params_widget
        self.module_name = module_name
        self.module_description = module_description
        self.module = module
        self.crop_rect = None  # 当前裁剪框 (QRectF)
        self._updating_from_spinbox = False  # 防止循环更新
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 工具栏
        toolbar = QWidget()
        toolbar.setProperty("class", "toolbar")
        toolbar.setStyleSheet("""
            QWidget[class="toolbar"] {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)
        
        # 导入按钮
        self.btn_import = QPushButton("📁 导入图片")
        self.btn_import.setProperty("class", "secondary")
        self.btn_import.setStyleSheet("""
            QPushButton[class="secondary"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton[class="secondary"]:hover {
                background-color: hsl(215, 27.9%, 16.9%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
        """)
        self.btn_import.clicked.connect(self.import_image)
        toolbar_layout.addWidget(self.btn_import)
        
        # 如果有参数组件，紧跟在导入按钮后面
        if self.params_widget:
            # 分隔线
            separator = QFrame()
            separator.setProperty("class", "separator-vertical")
            separator.setStyleSheet("""
                QFrame[class="separator-vertical"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    min-width: 1px;
                    max-width: 1px;
                }
            """)
            toolbar_layout.addWidget(separator)
            toolbar_layout.addWidget(self.params_widget)
        
        toolbar_layout.addStretch()
        
        # 如果是基础编辑模块，添加全屏按钮
        module_name = self.module.get_name() if self.module else ""
        if module_name == "基础编辑":
            self.btn_fullscreen = QPushButton("⛶ 全屏")
            self.btn_fullscreen.setProperty("class", "outline")
            self.btn_fullscreen.setStyleSheet("""
                QPushButton[class="outline"] {
                    background-color: transparent;
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 6px;
                    padding: 8px 16px;
                }
                QPushButton[class="outline"]:hover {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                }
            """)
            self.btn_fullscreen.setEnabled(False)  # 初始禁用，加载图片后启用
            self.btn_fullscreen.clicked.connect(lambda: self.fullscreen_requested.emit())
            toolbar_layout.addWidget(self.btn_fullscreen)
        
        layout.addWidget(toolbar)
        
        # 图形视图（单个裁剪框）
        self.graphics_view = CropGraphicsView()
        self.graphics_view.crop_rect_changed.connect(self._on_crop_rect_changed)
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.graphics_view, stretch=1)
        
        # 提示标签
        hint_text = "点击上方\"导入图片\"或点击此处选择图片"
        if self.module_description:
            hint_text += f"\n\n📋 功能说明：{self.module_description}"
        
        if self.module:
            try:
                req = self.module.get_system_requirements()
                hint_text += "\n\n💻 电脑配置要求："
                hint_text += f"\n\u3000最低配置：CPU {req['min_cpu']} + 内存 {req['min_ram']}"
                hint_text += f"\n\u3000推荐配置：CPU {req['rec_cpu']} + 内存 {req['rec_ram']}"
            except:
                pass
        
        hint_text += "\n\n💡 操作提示：左键拖拽绘制裁剪框 | 拖拽四个角和边缘调整大小 | 拖拽框内移动位置"
        self.hint_label = ImageLabelWithBackground(hint_text)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                font-size: 14px;
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                padding: 20px;
            }
        """)
        self.hint_label.setWordWrap(True)
        self.hint_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hint_label.mousePressEvent = self._on_hint_clicked
        layout.addWidget(self.hint_label, stretch=1)
        
        # 支持拖拽
        self.setAcceptDrops(True)
        
        # 初始状态：显示提示，隐藏图形视图
        self.graphics_view.hide()
        self.hint_label.show()
    
    def _on_hint_clicked(self, event):
        """点击提示区域导入图片"""
        # 只有在没有图片时才允许导入
        if self.current_image_path is None or self.original_image is None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.import_image()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    self.load_image(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def import_image(self):
        """导入图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, image_path: str) -> bool:
        """加载图片"""
        if not os.path.exists(image_path):
            return False
        
        try:
            # 检查图片大小，超大图弹出缩放对话框
            action, scale = ImageResizeDialog.check_and_resize(self, image_path)
            
            if action == "cancel":
                return False
            
            img = cv2_imread(image_path)
            if img is None:
                return False
            
            # 如果需要缩放
            if action == "resize" and scale < 1.0:
                h, w = img.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            self.current_image_path = image_path
            self.original_image = img
            
            # 将cv2图像转换为QPixmap
            h, w = img.shape[:2]
            if len(img.shape) == 3:
                bytes_per_line = 3 * w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
            else:
                bytes_per_line = w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image)
            
            # 切换显示
            self.hint_label.hide()
            self.graphics_view.show()
            
            # 设置图片，并初始化裁剪框（默认覆盖整个图片）
            self.graphics_view.set_image(pixmap)
            # 启用全屏按钮
            if hasattr(self, 'btn_fullscreen'):
                self.btn_fullscreen.setEnabled(True)
            self.image_loaded.emit(image_path)
            return True
        except Exception as e:
            StyledMessageBox.warning(self, "错误", f"加载图片失败: {str(e)}")
            return False
    
    def _on_crop_rect_changed(self, rect: QRectF):
        """裁剪框改变回调"""
        if self._updating_from_spinbox:
            return
        
        # 如果矩形为空（没有裁剪框），不发出信号
        if rect.isEmpty() or rect.isNull():
            self.crop_rect = None
            return
        
        self.crop_rect = rect
        x = int(rect.left())
        y = int(rect.top())
        w = int(rect.width())
        h = int(rect.height())
        
        # 发出信号，通知参数组件更新
        self.crop_updated.emit(x, y, w, h)
    
    def set_crop_rect(self, x: int, y: int, w: int, h: int):
        """从SpinBox设置裁剪框（防止循环更新）"""
        self._updating_from_spinbox = True
        try:
            if self.graphics_view.pixmap_item:
                rect = QRectF(x, y, w, h)
                self.graphics_view.set_crop_rect(rect)
        finally:
            self._updating_from_spinbox = False
    
    def get_crop_rect(self) -> tuple:
        """获取裁剪框坐标 (x, y, w, h)"""
        if self.crop_rect:
            return (int(self.crop_rect.left()), int(self.crop_rect.top()),
                    int(self.crop_rect.width()), int(self.crop_rect.height()))
        return (0, 0, 0, 0)
    
    def has_mask(self) -> bool:
        """检查是否有mask（裁剪框不需要mask）"""
        return False
    
    def get_mask_path(self) -> str:
        """获取mask文件路径（裁剪框不需要mask）"""
        return None
    
    def set_crop_box_visible(self, visible: bool):
        """设置裁剪框是否可见"""
        if self.graphics_view.crop_rect_item:
            self.graphics_view.crop_rect_item.setVisible(visible)
            if visible:
                self.graphics_view.crop_rect_item.setSelected(True)
                self.graphics_view.crop_rect_item.update_handles()


class CropResizableRect(ResizableRect):
    """裁剪专用的可调整矩形框，发出变化信号"""
    
    def __init__(self, rect, parent_view=None):
        super().__init__(rect)
        self.parent_view = parent_view
        # 裁剪框的手柄始终可见
        self.setSelected(True)
        self.update_handles()
    
    def update_handles(self):
        """更新手柄位置 - 裁剪框的手柄始终可见"""
        # 对于裁剪框，手柄始终显示
        for h in self.handles:
            h.setVisible(True)
            
        r = self.rect()
        pos = [
            r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight(),
            QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()),
            QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y())
        ]
        for h, p in zip(self.handles, pos):
            h.setPos(p)
    
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # 拖拽时发出信号
        if self.resize_dir and self.parent_view:
            self.parent_view._emit_crop_changed()
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # 释放时发出信号
        if self.parent_view:
            self.parent_view._emit_crop_changed()


class CropGraphicsView(QGraphicsView):
    """支持单个裁剪框的图形视图"""
    
    crop_rect_changed = pyqtSignal(QRectF)  # 裁剪框改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.pixmap_item = None
        self.crop_rect_item = None  # 单个裁剪框
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background-color: hsl(224, 71.4%, 4.1%); border: none;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        self.start_pos = None
        self.current_rect = None
    
    def set_image(self, pixmap):
        """设置图片"""
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.resetTransform()
        
        # 默认不创建裁剪框，需要用户鼠标拖拽创建
        self.crop_rect_item = None
    
    def set_crop_rect(self, rect: QRectF):
        """设置裁剪框"""
        if self.crop_rect_item:
            self.crop_rect_item.setRect(rect.normalized())
            self.crop_rect_item.update_handles()
            self._emit_crop_changed()
    
    def _emit_crop_changed(self):
        """发出裁剪框改变信号"""
        if self.crop_rect_item:
            rect = self.crop_rect_item.rect()
            self.crop_rect_changed.emit(rect)
        else:
            # 没有裁剪框时，发出空矩形
            self.crop_rect_changed.emit(QRectF())
    
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if isinstance(item, CropResizableRect):
                # 点击裁剪框，选中它
                self.crop_rect_item.setSelected(True)
                super().mousePressEvent(event)
            elif item == self.pixmap_item or item is None:
                # 点击图片，创建新裁剪框（替换旧的）
                if self.crop_rect_item:
                    self.scene.removeItem(self.crop_rect_item)
                    self.crop_rect_item = None
                
                self.start_pos = self.mapToScene(event.pos())
                self.current_rect = CropResizableRect(QRectF(self.start_pos, self.start_pos), parent_view=self)
                self.scene.addItem(self.current_rect)
                self.crop_rect_item = self.current_rect
                self.crop_rect_item.setSelected(True)
                self.setFocus()
            else:
                super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键删除裁剪框
            if isinstance(item, CropResizableRect):
                self.scene.removeItem(item)
                self.crop_rect_item = None
                self._emit_crop_changed()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.start_pos and self.current_rect:
            curr_pos = self.mapToScene(event.pos())
            self.current_rect.setRect(QRectF(self.start_pos, curr_pos).normalized())
            # 实时更新手柄位置
            self.current_rect.update_handles()
            self._emit_crop_changed()
        super().mouseMoveEvent(event)
        # 拖拽裁剪框后也需要发出信号（在super().mouseMoveEvent之后，因为ResizableRect的mouseMoveEvent会更新rect）
        if self.crop_rect_item and self.crop_rect_item.resize_dir:
            self._emit_crop_changed()
    
    def mouseReleaseEvent(self, event):
        if self.current_rect:
            r = self.current_rect.rect()
            if r.width() < 5 or r.height() < 5:
                # 太小，删除裁剪框
                self.scene.removeItem(self.current_rect)
                self.crop_rect_item = None
                self._emit_crop_changed()
            else:
                self.current_rect.update_handles()
                self._emit_crop_changed()
        
        self.start_pos = None
        self.current_rect = None
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """键盘事件：方向键微调，Delete/Backspace删除"""
        if not self.crop_rect_item:
            super().keyPressEvent(event)
            return
        
        step = 1
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = 10
        
        if event.key() == Qt.Key.Key_Left:
            self.crop_rect_item.moveBy(-step, 0)
            self._emit_crop_changed()
        elif event.key() == Qt.Key.Key_Right:
            self.crop_rect_item.moveBy(step, 0)
            self._emit_crop_changed()
        elif event.key() == Qt.Key.Key_Up:
            self.crop_rect_item.moveBy(0, -step)
            self._emit_crop_changed()
        elif event.key() == Qt.Key.Key_Down:
            self.crop_rect_item.moveBy(0, step)
            self._emit_crop_changed()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # 删除裁剪框
            self.scene.removeItem(self.crop_rect_item)
            self.crop_rect_item = None
            self._emit_crop_changed()
        else:
            super().keyPressEvent(event)
    
    def wheelEvent(self, event):
        """滚轮缩放"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        self.scale(factor, factor)


class ImagePreviewWidgetSimple(QWidget):
    """简单的图片预览组件 - 用于不需要笔刷/选区的模块（含证件照）"""

    image_loaded = pyqtSignal(str)
    fullscreen_requested = pyqtSignal()  # 请求打开全屏功能窗口
    # 适应框/实际大小（证件照等：大图时显示切换按钮）
    fit_button_visible = pyqtSignal(bool)
    fit_mode_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None, params_widget=None, module_name="", module_description="", enable_zoom=False, module=None):
        super().__init__(parent)
        self.current_image_path = None
        self.original_pixmap = None  # 保存原图用于重新缩放
        self.params_widget = params_widget
        self.module_name = module_name
        self.module_description = module_description
        self.enable_zoom = enable_zoom  # 是否启用缩放功能
        self.module = module
        
        # 缩放和拖动相关（仅在enable_zoom=True时使用）
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 5.0  # 最大500%
        self.panning = False
        self.pan_start_point = None
        self._is_wheel_zoom = False
        # 适应框/实际大小
        self._display_fit_mode = True
        self._fit_scale = 1.0
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 工具栏
        toolbar = QWidget()
        toolbar.setProperty("class", "toolbar")
        toolbar.setStyleSheet("""
            QWidget[class="toolbar"] {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)
        
        # 导入按钮
        self.btn_import = QPushButton("📁 导入图片")
        self.btn_import.setProperty("class", "secondary")
        self.btn_import.setStyleSheet("""
            QPushButton[class="secondary"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton[class="secondary"]:hover {
                background-color: hsl(215, 27.9%, 16.9%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
        """)
        self.btn_import.clicked.connect(self.import_image)
        toolbar_layout.addWidget(self.btn_import)
        
        # 如果有参数组件，紧跟在导入按钮后面
        if self.params_widget:
            # 分隔线
            separator = QFrame()
            separator.setProperty("class", "separator-vertical")
            separator.setStyleSheet("""
                QFrame[class="separator-vertical"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    min-width: 1px;
                    max-width: 1px;
                }
            """)
            toolbar_layout.addWidget(separator)
            toolbar_layout.addWidget(self.params_widget)
        
        toolbar_layout.addStretch()
        
        # 如果启用缩放功能，添加缩放控制
        if self.enable_zoom:
            # 缩放控制区域
            zoom_label = QLabel("缩放:")
            zoom_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none; font-size: 13px;")
            toolbar_layout.addWidget(zoom_label)
            
            self.btn_zoom_out = QPushButton("-")
            self.btn_zoom_out.setProperty("class", "icon-button")
            self.btn_zoom_out.setToolTip("缩小")
            self.btn_zoom_out.setFixedSize(24, 24)
            self.btn_zoom_out.setStyleSheet("""
                QPushButton[class="icon-button"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton[class="icon-button"]:hover {
                    background-color: hsl(215, 27.9%, 16.9%);
                    border-color: hsl(215, 20.2%, 65.1%);
                }
            """)
            self.btn_zoom_out.clicked.connect(self.zoom_out)
            toolbar_layout.addWidget(self.btn_zoom_out)
            
            self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
            self.zoom_slider.setMinimum(10)
            self.zoom_slider.setMaximum(500)
            self.zoom_slider.setValue(100)
            self.zoom_slider.setMinimumWidth(150)
            self.zoom_slider.setMaximumWidth(200)
            self.zoom_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    height: 4px;
                    background: hsl(224, 71.4%, 4.1%);
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: hsl(221.2, 83.2%, 53.3%);
                    border: none;
                    width: 12px;
                    height: 12px;
                    margin: -4px 0;
                    border-radius: 6px;
                }
                QSlider::handle:horizontal:hover {
                    background: hsl(221.2, 83.2%, 60%);
                }
                QSlider::sub-page:horizontal {
                    background: hsl(221.2, 83.2%, 53.3%);
                    border-radius: 2px;
                }
            """)
            self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
            toolbar_layout.addWidget(self.zoom_slider)
            
            self.btn_zoom_in = QPushButton("+")
            self.btn_zoom_in.setProperty("class", "icon-button")
            self.btn_zoom_in.setToolTip("放大")
            self.btn_zoom_in.setFixedSize(24, 24)
            self.btn_zoom_in.setStyleSheet("""
                QPushButton[class="icon-button"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton[class="icon-button"]:hover {
                    background-color: hsl(215, 27.9%, 16.9%);
                    border-color: hsl(215, 20.2%, 65.1%);
                }
            """)
            self.btn_zoom_in.clicked.connect(self.zoom_in)
            toolbar_layout.addWidget(self.btn_zoom_in)
            
            self.zoom_value_label = QLabel("100%")
            self.zoom_value_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none; font-size: 13px;")
            self.zoom_value_label.setMinimumWidth(50)
            self.zoom_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            toolbar_layout.addWidget(self.zoom_value_label)
        
        # 如果是图片放大、图片加水印或基础编辑模块，添加全屏按钮
        module_name = self.module.get_name() if self.module else ""
        enable_fullscreen = (self.enable_zoom or 
                            module_name == "图片加水印" or 
                            module_name == "基础编辑")
        if enable_fullscreen:
            self.btn_fullscreen = QPushButton("⛶ 全屏")
            self.btn_fullscreen.setProperty("class", "outline")
            self.btn_fullscreen.setStyleSheet("""
                QPushButton[class="outline"] {
                    background-color: transparent;
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 6px;
                    padding: 8px 16px;
                }
                QPushButton[class="outline"]:hover {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                }
            """)
            self.btn_fullscreen.setEnabled(False)
            self.btn_fullscreen.clicked.connect(lambda: self.fullscreen_requested.emit())
            toolbar_layout.addWidget(self.btn_fullscreen)
        
        layout.addWidget(toolbar)
        
        # 图片显示区域
        self.image_container = QWidget()
        self.image_container.setProperty("class", "card")
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: hsl(222.2, 47.4%, 11.2%);
                border: none;
            }
        """)
        
        # 滚动区域内的widget
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图片标签
        hint_text = "点击上方\"导入图片\"或点击此处选择图片"
        if self.module_description:
            hint_text += f"\n\n📋 功能说明：{self.module_description}"
        
        if self.module:
            try:
                req = self.module.get_system_requirements()
                hint_text += "\n\n💻 电脑配置要求："
                hint_text += f"\n\u3000最低配置：CPU {req['min_cpu']} + 内存 {req['min_ram']}"
                hint_text += f"\n\u3000推荐配置：CPU {req['rec_cpu']} + 内存 {req['rec_ram']}"
            except:
                pass
        
        self.image_label = ImageLabelWithBackground(hint_text)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                border: 2px dashed hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                font-size: 14px;
                padding: 20px;
            }
        """)
        self.image_label.setScaledContents(False)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 如果启用缩放，添加鼠标事件（用于平移和缩放）
        if self.enable_zoom:
            self.image_label.wheelEvent = self.on_wheel
            self.image_label.mousePressEvent = self.on_mouse_press
            self.image_label.mouseMoveEvent = self.on_mouse_move
            self.image_label.mouseReleaseEvent = self.on_mouse_release
        else:
            # 未启用缩放时，点击提示区域导入图片
            self.image_label.mousePressEvent = self._on_hint_clicked
        
        self.scroll_layout.addWidget(self.image_label)
        self.scroll_area.setWidget(self.scroll_widget)
        container_layout.addWidget(self.scroll_area)
        layout.addWidget(self.image_container, stretch=1)
        
        # 支持拖拽
        self.setAcceptDrops(True)
    
    def _on_hint_clicked(self, event):
        """点击提示区域导入图片"""
        # 只有在没有图片时才允许导入（ImagePreviewWidgetSimple 使用 original_pixmap）
        if self.current_image_path is None or self.original_pixmap is None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.import_image()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    self.load_image(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def import_image(self):
        """导入图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, image_path: str) -> bool:
        """加载图片"""
        if not os.path.exists(image_path):
            return False
        
        try:
            # 检查图片大小，超大图弹出缩放对话框
            action, scale = ImageResizeDialog.check_and_resize(self, image_path)
            
            if action == "cancel":
                return False
            
            img = cv2_imread(image_path)
            if img is None:
                return False
            
            # 如果需要缩放
            if action == "resize" and scale < 1.0:
                h, w = img.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            self.current_image_path = image_path
            
            # 将cv2图像转换为QPixmap
            h, w = img.shape[:2]
            if len(img.shape) == 3:
                bytes_per_line = 3 * w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
            else:
                bytes_per_line = w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image)
            
            # 保存原图用于重新缩放
            self.original_pixmap = pixmap
            
            # 更新显示
            self.update_display()
            
            # 更新UI状态
            self.image_label.set_has_image(True)
            # 启用全屏按钮（如果存在）
            if hasattr(self, 'btn_fullscreen'):
                self.btn_fullscreen.setEnabled(True)
            
            self.image_loaded.emit(image_path)
            # 证件照等：大图时延迟检查，显示“适应框/实际大小”按钮并默认适应框
            QTimer.singleShot(150, self._update_fit_button_visibility)
            return True
        except Exception as e:
            StyledMessageBox.warning(self, "错误", f"加载图片失败: {str(e)}")
            return False
    
    def _update_fit_button_visibility(self):
        """图片加载后：若大于显示区则显示“适应框/实际大小”按钮并默认适应框"""
        if self.original_pixmap is None or not hasattr(self, 'scroll_area'):
            self.fit_button_visible.emit(False)
            return
        w = self.original_pixmap.width()
        h = self.original_pixmap.height()
        vp = self.scroll_area.viewport().size()
        vw, vh = vp.width(), vp.height()
        if vw < 100 or vh < 100:
            vw, vh = max(vw, 400), max(vh, 300)
        if w <= vw and h <= vh:
            self.fit_button_visible.emit(False)
            return
        self._fit_scale = min(vw / w, vh / h)
        self._display_fit_mode = True
        self.scale_factor = self._fit_scale
        self.update_display()
        self.fit_button_visible.emit(True)
        self.fit_mode_changed.emit(True)
    
    def set_display_fit(self, fit: bool):
        """设置显示模式：True=适应框，False=实际大小"""
        self._display_fit_mode = fit
        self.scale_factor = self._fit_scale if fit else 1.0
        self.update_display()
        self.fit_mode_changed.emit(fit)
    
    def toggle_fit_actual(self):
        """切换 适应框 / 实际大小"""
        self.set_display_fit(not self._display_fit_mode)
    
    def get_display_fit_mode(self) -> bool:
        """当前是否为适应框模式"""
        return self._display_fit_mode
    
    def update_display(self):
        """更新显示"""
        if self.original_pixmap is None:
            return
        
        # 计算缩放后的尺寸
        scaled_pixmap = self.original_pixmap.scaled(
            int(self.original_pixmap.width() * self.scale_factor),
            int(self.original_pixmap.height() * self.scale_factor),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.width(), scaled_pixmap.height())
    
    def on_mouse_press(self, event):
        """鼠标按下（仅在enable_zoom=True时使用）"""
        if self.enable_zoom:
            if event.button() == Qt.MouseButton.LeftButton:
                # 如果没有图片，点击导入
                if self.original_pixmap is None or self.current_image_path is None:
                    self.import_image()
                    return
                # 如果有图片，启用平移
                self.panning = True
                self.pan_start_point = event.position()
            else:
                # 右键或其他按钮，调用提示点击处理（用于导入图片）
                self._on_hint_clicked(event)
        else:
            # 未启用缩放时，调用提示点击处理
            self._on_hint_clicked(event)
    
    def on_mouse_move(self, event):
        """鼠标移动（仅在enable_zoom=True时使用）"""
        if self.enable_zoom and self.panning and self.pan_start_point:
            delta_x = event.position().x() - self.pan_start_point.x()
            delta_y = event.position().y() - self.pan_start_point.y()
            
            scroll_bar_h = self.scroll_area.horizontalScrollBar()
            scroll_bar_v = self.scroll_area.verticalScrollBar()
            
            if scroll_bar_h:
                scroll_bar_h.setValue(scroll_bar_h.value() - int(delta_x))
            if scroll_bar_v:
                scroll_bar_v.setValue(scroll_bar_v.value() - int(delta_y))
            
            self.pan_start_point = event.position()
    
    def on_mouse_release(self, event):
        """鼠标释放（仅在enable_zoom=True时使用）"""
        if self.enable_zoom:
            self.panning = False
            self.pan_start_point = None
    
    def on_wheel(self, event: QWheelEvent):
        """鼠标滚轮 - 缩放（仅在enable_zoom=True时使用）"""
        if not self.enable_zoom or self.original_pixmap is None:
            return
        
        # 获取鼠标位置（相对于label）
        mouse_pos = event.position()
        
        # 获取当前滚动位置
        scroll_bar_h = self.scroll_area.horizontalScrollBar()
        scroll_bar_v = self.scroll_area.verticalScrollBar()
        scroll_x = scroll_bar_h.value() if scroll_bar_h else 0
        scroll_y = scroll_bar_v.value() if scroll_bar_v else 0
        
        # 计算缩放前的图片坐标（考虑滚动位置）
        old_img_x = (mouse_pos.x() + scroll_x) / self.scale_factor
        old_img_y = (mouse_pos.y() + scroll_y) / self.scale_factor
        
        # 缩放
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale_factor = min(self.scale_factor * 1.15, self.max_scale)
        else:
            self.scale_factor = max(self.scale_factor / 1.15, self.min_scale)
        
        # 计算缩放后的滚动位置，使鼠标位置对应的图片点保持不变
        new_scroll_x = old_img_x * self.scale_factor - mouse_pos.x()
        new_scroll_y = old_img_y * self.scale_factor - mouse_pos.y()
        
        # 更新显示
        self.update_display()
        
        # 调整滚动位置
        if scroll_bar_h:
            scroll_bar_h.setValue(int(new_scroll_x))
        if scroll_bar_v:
            scroll_bar_v.setValue(int(new_scroll_y))
    
    def on_zoom_slider_changed(self, value):
        """缩放滑块值变化"""
        if not self.enable_zoom or self.original_pixmap is None:
            return
        
        # 更新缩放比例（滑块值是百分比）
        self.scale_factor = value / 100.0
        self.scale_factor = max(self.min_scale, min(self.max_scale, self.scale_factor))
        
        # 更新百分比显示
        if hasattr(self, 'zoom_value_label'):
            self.zoom_value_label.setText(f"{value}%")
        
        # 更新显示
        self.update_display()
    
    def zoom_in(self):
        """放大"""
        if not self.enable_zoom or not hasattr(self, 'zoom_slider'):
            return
        new_value = min(self.zoom_slider.value() + 10, 500)
        self.zoom_slider.setValue(new_value)
    
    def zoom_out(self):
        """缩小"""
        if not self.enable_zoom or not hasattr(self, 'zoom_slider'):
            return
        new_value = max(self.zoom_slider.value() - 10, 10)
        self.zoom_slider.setValue(new_value)
    
    def get_zoom_scale(self) -> float:
        """获取当前缩放比例（用于图片放大模块）"""
        return self.scale_factor
    
    def has_mask(self) -> bool:
        """不需要mask，始终返回True表示可以处理"""
        return True
    
    def get_mask_path(self) -> str:
        """不需要mask"""
        return None


class WatermarkResizableRect(ResizableRect):
    """水印专用的可调整矩形框，显示水印内容"""
    
    def __init__(self, rect, watermark_data, parent_view=None):
        """初始化水印矩形框
        
        Args:
            rect: 矩形区域
            watermark_data: 水印数据字典
            parent_view: 父视图
        """
        super().__init__(rect)
        self.watermark_data = watermark_data
        self.parent_view = parent_view
        
        # 设置样式（透明边框，不填充）
        self.setPen(QPen(QColor(66, 133, 244), 2))  # 蓝色边框
        self.setBrush(QBrush(QColor(0, 0, 0, 0)))  # 透明填充
        
        # 水印内容缓存
        self._text_pixmap = None
        self._image_pixmap = None
        self._update_content_cache()
    
    def _update_content_cache(self):
        """更新水印内容缓存"""
        self._text_pixmap = None
        self._image_pixmap = None
        
        if self.watermark_data.get('type') == 'text':
            # 渲染文字水印
            text = self.watermark_data.get('text', '')
            if text:
                from PyQt6.QtGui import QFont
                font_family = self.watermark_data.get('font_family', '微软雅黑')
                font_size = self.watermark_data.get('size', 20)
                color = QColor(self.watermark_data.get('color', '#8B8B1B'))
                opacity = self.watermark_data.get('opacity', 0.15)
                
                # 创建临时pixmap用于测量文字大小
                temp_pixmap = QPixmap(1000, 1000)
                temp_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(temp_pixmap)
                font = QFont(font_family, font_size)
                painter.setFont(font)
                painter.setPen(QPen(color))
                painter.setOpacity(opacity)
                
                # 测量文字大小
                metrics = painter.fontMetrics()
                text_rect = metrics.boundingRect(text)
                
                # 创建实际大小的pixmap
                self._text_pixmap = QPixmap(text_rect.width() + 20, text_rect.height() + 20)
                self._text_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(self._text_pixmap)
                painter.setFont(font)
                painter.setPen(QPen(color))
                painter.setOpacity(opacity)
                painter.drawText(10, 10 + text_rect.height(), text)
                painter.end()
        else:
            # 加载图片水印
            image_path = self.watermark_data.get('image_path')
            if image_path and os.path.exists(image_path):
                self._image_pixmap = QPixmap(image_path)
                if not self._image_pixmap.isNull():
                    # 应用缩放
                    scale = self.watermark_data.get('image_scale', 0.1)
                    if scale > 0:
                        new_size = self._image_pixmap.size() * scale
                        self._image_pixmap = self._image_pixmap.scaled(
                            int(new_size.width()), int(new_size.height()),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
    
    def paint(self, painter, option, widget=None):
        """绘制水印内容"""
        # 先绘制矩形框（如果选中）
        super().paint(painter, option, widget)
        
        # 绘制水印内容
        rect = self.rect()
        if self._text_pixmap and not self._text_pixmap.isNull():
            # 绘制文字水印
            scaled_pixmap = self._text_pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(rect.topLeft(), scaled_pixmap)
        elif self._image_pixmap and not self._image_pixmap.isNull():
            # 绘制图片水印
            opacity = self.watermark_data.get('image_opacity', 0.3)
            painter.setOpacity(opacity)
            scaled_pixmap = self._image_pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(rect.topLeft(), scaled_pixmap)
            painter.setOpacity(1.0)
    
    def update_watermark_data(self, watermark_data):
        """更新水印数据"""
        self.watermark_data = watermark_data
        self._update_content_cache()
        self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 限制在图片边界内"""
        super().mouseMoveEvent(event)
        if self.resize_dir and self.parent_view and self.parent_view.pixmap_item:
            # 限制在图片边界内
            rect = self.rect()
            pos = self.pos()
            pixmap = self.parent_view.pixmap_item.pixmap()
            img_w = pixmap.width()
            img_h = pixmap.height()
            
            # 确保不超出图片边界
            new_x = pos.x()
            new_y = pos.y()
            new_width = rect.width()
            new_height = rect.height()
            
            if new_x < 0:
                new_x = 0
            if new_y < 0:
                new_y = 0
            if new_x + new_width > img_w:
                new_x = img_w - new_width
            if new_y + new_height > img_h:
                new_y = img_h - new_height
            
            # 如果位置改变了，更新位置
            if new_x != pos.x() or new_y != pos.y():
                self.setPos(new_x, new_y)
            
            # 如果大小改变了，限制大小
            if new_width > img_w:
                new_width = img_w
            if new_height > img_h:
                new_height = img_h
            if rect.width() != new_width or rect.height() != new_height:
                self.setRect(QRectF(new_x, new_y, new_width, new_height))
                self.update_handles()
            
            # 发出位置变化信号
            self.parent_view._emit_watermark_changed(self)


class WatermarkGraphicsView(QGraphicsView):
    """支持多水印的图形视图"""
    
    watermark_selected = pyqtSignal(int)  # 水印被选中，发出索引
    watermark_moved = pyqtSignal(int, float, float)  # 水印位置变化
    watermark_resized = pyqtSignal(int, float, float)  # 水印大小变化
    watermark_deleted = pyqtSignal(int)  # 水印被删除
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.pixmap_item = None
        self.watermark_items = []  # 水印矩形框列表
        self.selected_watermark_index = None
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background-color: hsl(224, 71.4%, 4.1%); border: none;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # 复制粘贴相关
        self._copied_watermark = None
    
    def set_image(self, pixmap):
        """设置图片"""
        self.scene.clear()
        self.watermark_items = []
        self.selected_watermark_index = None
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.resetTransform()
    
    def set_watermarks(self, watermarks, image_size):
        """设置水印列表
        
        Args:
            watermarks: 水印对象列表
            image_size: 图片大小 (width, height)
        """
        # 清除旧的水印
        for item in self.watermark_items:
            self.scene.removeItem(item)
        self.watermark_items = []
        self.selected_watermark_index = None
        
        if not self.pixmap_item:
            return
        
        img_w, img_h = image_size
        
        # 添加新水印
        for i, wm in enumerate(watermarks):
            if wm.get('position') == 'free':
                # 任意位置：使用归一化坐标转换为像素坐标
                x = wm.get('x', 0.5) * img_w
                y = wm.get('y', 0.5) * img_h
                width = wm.get('width', 0.2) * img_w
                height = wm.get('height', 0.1) * img_h
                
                # rect 的坐标应该是相对于 item 的本地坐标，所以从 (0,0) 开始
                # 实际位置通过 setPos 设置
                rect = QRectF(0, 0, width, height)
                wm_item = WatermarkResizableRect(rect, wm, parent_view=self)
                wm_item.setPos(x, y)  # 设置水印在场景中的位置
                wm_item.watermark_index = i  # 保存索引
                self.scene.addItem(wm_item)
                self.watermark_items.append(wm_item)
    
    def select_watermark(self, index):
        """选中指定索引的水印"""
        # 清除所有选中
        for item in self.watermark_items:
            item.setSelected(False)
        
        self.selected_watermark_index = index
        if index is not None and 0 <= index < len(self.watermark_items):
            self.watermark_items[index].setSelected(True)
            self.watermark_selected.emit(index)
    
    def _emit_watermark_changed(self, wm_item):
        """发出水印变化信号"""
        if hasattr(wm_item, 'watermark_index'):
            index = wm_item.watermark_index
            rect = wm_item.rect()
            pos = wm_item.pos()
            
            # 转换为归一化坐标（相对于图片）
            # rect 的坐标是相对于 item 的本地坐标，pos 是 item 在场景中的位置
            # 所以水印的实际位置是 pos，大小是 rect 的宽高
            if self.pixmap_item:
                img_w = self.pixmap_item.pixmap().width()
                img_h = self.pixmap_item.pixmap().height()
                if img_w > 0 and img_h > 0:
                    x = pos.x() / img_w
                    y = pos.y() / img_h
                    width = rect.width() / img_w
                    height = rect.height() / img_h
                    
                    self.watermark_moved.emit(index, x, y)
                    self.watermark_resized.emit(index, width, height)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        item = self.itemAt(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if isinstance(item, WatermarkResizableRect):
                # 点击水印，选中它
                index = item.watermark_index
                self.select_watermark(index)
                super().mousePressEvent(event)
            elif item == self.pixmap_item or item is None:
                # 点击空白区域，取消选中
                self.select_watermark(None)
                super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        super().mouseMoveEvent(event)
        # 拖拽后发出信号
        if self.selected_watermark_index is not None:
            wm_item = self.watermark_items[self.selected_watermark_index]
            if wm_item.resize_dir:
                self._emit_watermark_changed(wm_item)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        super().mouseReleaseEvent(event)
        # 释放后发出信号
        if self.selected_watermark_index is not None:
            wm_item = self.watermark_items[self.selected_watermark_index]
            self._emit_watermark_changed(wm_item)
    
    def keyPressEvent(self, event):
        """键盘事件：方向键微调，Delete删除，Ctrl+C/V复制粘贴"""
        if self.selected_watermark_index is None:
            super().keyPressEvent(event)
            return
        
        wm_item = self.watermark_items[self.selected_watermark_index]
        step = 5  # 微调步长（像素）
        
        if event.key() == Qt.Key.Key_Left:
            wm_item.moveBy(-step, 0)
            self._emit_watermark_changed(wm_item)
        elif event.key() == Qt.Key.Key_Right:
            wm_item.moveBy(step, 0)
            self._emit_watermark_changed(wm_item)
        elif event.key() == Qt.Key.Key_Up:
            wm_item.moveBy(0, -step)
            self._emit_watermark_changed(wm_item)
        elif event.key() == Qt.Key.Key_Down:
            wm_item.moveBy(0, step)
            self._emit_watermark_changed(wm_item)
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # 删除水印
            index = self.selected_watermark_index
            self.scene.removeItem(wm_item)
            self.watermark_items.pop(index)
            # 更新后续项的索引
            for i in range(index, len(self.watermark_items)):
                self.watermark_items[i].watermark_index = i
            self.selected_watermark_index = None
            self.watermark_deleted.emit(index)
        elif event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 复制水印
            if 0 <= self.selected_watermark_index < len(self.watermark_items):
                wm_item = self.watermark_items[self.selected_watermark_index]
                self._copied_watermark = wm_item.watermark_data.copy()
        elif event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 粘贴水印（需要外部处理，因为需要添加到watermarks列表）
            # 这里不直接处理，由外部监听信号或通过其他机制处理
            pass
        else:
            super().keyPressEvent(event)
    
    def wheelEvent(self, event):
        """滚轮缩放"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        self.scale(factor, factor)
    
    def update_watermark_item(self, index, watermark_data):
        """更新指定索引的水印数据"""
        if 0 <= index < len(self.watermark_items):
            self.watermark_items[index].update_watermark_data(watermark_data)
            self.watermark_items[index].update()


class ImagePreviewWidgetWatermark(QWidget):
    """水印预览组件 - 支持多水印交互式编辑"""
    
    image_loaded = pyqtSignal(str)
    watermark_selected = pyqtSignal(int)  # 水印被选中
    watermark_moved = pyqtSignal(int, float, float)  # 水印位置变化
    watermark_resized = pyqtSignal(int, float, float)  # 水印大小变化
    watermark_deleted = pyqtSignal(int)  # 水印被删除
    fullscreen_requested = pyqtSignal()  # 请求打开全屏功能窗口
    
    def __init__(self, parent=None, params_widget=None, module_name="", module_description="", module=None):
        super().__init__(parent)
        self.current_image_path = None
        self.original_pixmap = None
        self.params_widget = params_widget
        self.module_name = module_name
        self.module_description = module_description
        self.module = module
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 工具栏
        toolbar = QWidget()
        toolbar.setProperty("class", "toolbar")
        toolbar.setStyleSheet("""
            QWidget[class="toolbar"] {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)
        
        # 导入按钮
        self.btn_import = QPushButton("📁 导入图片")
        self.btn_import.setProperty("class", "secondary")
        self.btn_import.setStyleSheet("""
            QPushButton[class="secondary"] {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton[class="secondary"]:hover {
                background-color: hsl(215, 27.9%, 16.9%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
        """)
        self.btn_import.clicked.connect(self.import_image)
        toolbar_layout.addWidget(self.btn_import)
        
        # 如果有参数组件，紧跟在导入按钮后面
        if self.params_widget:
            # 分隔线
            separator = QFrame()
            separator.setProperty("class", "separator-vertical")
            separator.setStyleSheet("""
                QFrame[class="separator-vertical"] {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    min-width: 1px;
                    max-width: 1px;
                }
            """)
            toolbar_layout.addWidget(separator)
            toolbar_layout.addWidget(self.params_widget)
        
        toolbar_layout.addStretch()
        
        # 全屏按钮
        self.btn_fullscreen = QPushButton("⛶ 全屏")
        self.btn_fullscreen.setProperty("class", "outline")
        self.btn_fullscreen.setStyleSheet("""
            QPushButton[class="outline"] {
                background-color: transparent;
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton[class="outline"]:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
        """)
        self.btn_fullscreen.setEnabled(False)  # 初始禁用，加载图片后启用
        self.btn_fullscreen.clicked.connect(lambda: self.fullscreen_requested.emit())
        toolbar_layout.addWidget(self.btn_fullscreen)
        
        layout.addWidget(toolbar)
        
        # 图形视图
        self.graphics_view = WatermarkGraphicsView()
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        
        # 连接信号
        self.graphics_view.watermark_selected.connect(self.watermark_selected.emit)
        self.graphics_view.watermark_moved.connect(self.watermark_moved.emit)
        self.graphics_view.watermark_resized.connect(self.watermark_resized.emit)
        self.graphics_view.watermark_deleted.connect(self.watermark_deleted.emit)
        
        layout.addWidget(self.graphics_view, stretch=1)
        
        # 提示标签
        hint_text = "点击上方\"导入图片\"或点击此处选择图片"
        if self.module_description:
            hint_text += f"\n\n📋 功能说明：{self.module_description}"
        
        if self.module:
            try:
                req = self.module.get_system_requirements()
                hint_text += "\n\n💻 电脑配置要求："
                hint_text += f"\n\u3000最低配置：CPU {req['min_cpu']} + 内存 {req['min_ram']}"
                hint_text += f"\n\u3000推荐配置：CPU {req['rec_cpu']} + 内存 {req['rec_ram']}"
            except:
                pass
        
        hint_text += "\n\n💡 操作提示：点击水印选中 | 拖拽移动位置 | 拖拽控制点调整大小 | 方向键微调 | Delete删除"
        self.hint_label = ImageLabelWithBackground(hint_text)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                font-size: 14px;
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                padding: 20px;
            }
        """)
        self.hint_label.setWordWrap(True)
        self.hint_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hint_label.mousePressEvent = self._on_hint_clicked
        layout.addWidget(self.hint_label, stretch=1)
        
        # 支持拖拽
        self.setAcceptDrops(True)
        
        # 初始状态：显示提示，隐藏图形视图
        self.graphics_view.hide()
        self.hint_label.show()
    
    def _on_hint_clicked(self, event):
        """点击提示区域导入图片"""
        # 只有在没有图片时才允许导入（ImagePreviewWidgetWatermark 使用 original_pixmap）
        if self.current_image_path is None or self.original_pixmap is None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.import_image()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    self.load_image(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def import_image(self):
        """导入图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*.*)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, image_path: str) -> bool:
        """加载图片"""
        try:
            if not os.path.exists(image_path):
                return False
            
            img = cv2_imread(image_path)
            if img is None:
                return False
            
            # 转换为QPixmap
            h, w = img.shape[:2]
            if len(img.shape) == 3:
                bytes_per_line = 3 * w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
            else:
                bytes_per_line = w
                q_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            
            pixmap = QPixmap.fromImage(q_image)
            self.original_pixmap = pixmap
            self.current_image_path = image_path
            
            # 设置图片到图形视图
            self.graphics_view.set_image(pixmap)
            
            # 更新水印显示
            self.update_watermarks()
            
            # 切换显示
            self.hint_label.hide()
            self.graphics_view.show()
            
            # 启用全屏按钮
            if hasattr(self, 'btn_fullscreen'):
                self.btn_fullscreen.setEnabled(True)
            
            self.image_loaded.emit(image_path)
            return True
        except Exception as e:
            print(f"加载图片失败: {e}")
            return False
    
    def update_watermarks(self):
        """更新水印显示"""
        if not self.module or not self.original_pixmap:
            return
        
        watermarks = self.module.watermarks
        img_size = (self.original_pixmap.width(), self.original_pixmap.height())
        self.graphics_view.set_watermarks(watermarks, img_size)
        
        # 如果有选中的水印，保持选中状态
        if self.module.selected_watermark_index is not None:
            self.graphics_view.select_watermark(self.module.selected_watermark_index)
    
    def select_watermark(self, index):
        """选中水印"""
        self.graphics_view.select_watermark(index)
    
    def has_mask(self) -> bool:
        """不需要mask"""
        return False
    
    def get_mask_path(self) -> str:
        """不需要mask"""
        return None
