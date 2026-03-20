"""自定义控件 - 解决PyQt6样式表箭头不显示问题"""
from PyQt6.QtWidgets import (
    QComboBox, QSpinBox, QDoubleSpinBox, QStyle, QStyleOptionComboBox, QStyleOptionSpinBox,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QFont, QMouseEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QTimer


class StyledMessageBox(QDialog):
    """美化的消息提示框"""
    
    # 消息类型
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    
    # 类型对应的图标和颜色
    TYPE_CONFIG = {
        "info": {
            "icon": "ℹ️",
            "color": "hsl(221.2, 83.2%, 53.3%)",  # 蓝色
            "bg": "hsl(221.2, 83.2%, 53.3%, 0.1)",
        },
        "success": {
            "icon": "✅",
            "color": "hsl(142.1, 76.2%, 46.3%)",  # 绿色
            "bg": "hsl(142.1, 76.2%, 46.3%, 0.1)",
        },
        "warning": {
            "icon": "⚠️",
            "color": "hsl(38, 92%, 50%)",  # 黄色
            "bg": "hsl(38, 92%, 50%, 0.1)",
        },
        "error": {
            "icon": "❌",
            "color": "hsl(0, 84.2%, 60.2%)",  # 红色
            "bg": "hsl(0, 84.2%, 60.2%, 0.1)",
        },
    }
    
    def __init__(self, parent=None, title="提示", message="", msg_type="info", auto_close=0):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setMaximumWidth(500)
        
        # 无边框窗口
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        config = self.TYPE_CONFIG.get(msg_type, self.TYPE_CONFIG["info"])
        
        # 主容器
        self.container = QLabel(self)
        self.container.setStyleSheet(f"""
            QLabel {{
                background-color: hsl(222.2, 84%, 4.9%);
            }}
        """)
        
        # 添加阴影效果（优化为更轻的阴影）
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.container.setGraphicsEffect(shadow)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(32, 24, 32, 24)
        container_layout.setSpacing(18)
        
        # 标题行（图标 + 标题）
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 图标
        icon_label = QLabel(config["icon"])
        icon_label.setStyleSheet("font-size: 22px; background: transparent;")
        title_layout.addWidget(icon_label)
        
        # 标题文字
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {config["color"]};
            background: transparent;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: hsl(215, 20.2%, 65.1%);
                font-size: 18px;
            }
            QPushButton:hover {
                background: hsl(217.2, 32.6%, 17.5%);
                color: white;
            }
        """)
        close_btn.clicked.connect(self.accept)
        title_layout.addWidget(close_btn)
        
        container_layout.addLayout(title_layout)
        
        # 消息内容
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("""
            font-size: 13px;
            color: hsl(215, 20.2%, 75%);
            background: transparent;
            line-height: 1.6;
            padding: 0px;
        """)
        container_layout.addWidget(msg_label)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.setFixedSize(90, 38)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config["color"]};
                border: none;
                color: white;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {config["color"]};
                opacity: 0.9;
            }}
            QPushButton:pressed {{
                background-color: {config["color"]};
                opacity: 0.8;
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        container_layout.addLayout(btn_layout)
        main_layout.addWidget(self.container)
        
        # 自动关闭
        if auto_close > 0:
            QTimer.singleShot(auto_close, self.accept)
    
    def mousePressEvent(self, event):
        """支持拖拽移动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """拖拽移动窗口"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    @staticmethod
    def information(parent, title, message, auto_close=0):
        """显示信息提示框"""
        dialog = StyledMessageBox(parent, title, message, StyledMessageBox.INFO, auto_close)
        dialog.exec()
    
    @staticmethod
    def success(parent, title, message, auto_close=0):
        """显示成功提示框"""
        dialog = StyledMessageBox(parent, title, message, StyledMessageBox.SUCCESS, auto_close)
        dialog.exec()
    
    @staticmethod
    def warning(parent, title, message, auto_close=0):
        """显示警告提示框"""
        dialog = StyledMessageBox(parent, title, message, StyledMessageBox.WARNING, auto_close)
        dialog.exec()
    
    @staticmethod
    def critical(parent, title, message, auto_close=0):
        """显示错误提示框"""
        dialog = StyledMessageBox(parent, title, message, StyledMessageBox.ERROR, auto_close)
        dialog.exec()


class StyledComboBox(QComboBox):
    """自定义ComboBox - 手动绘制下拉箭头"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow_color = QColor(148, 163, 184)  # #94a3b8
        self._arrow_hover_color = QColor(255, 255, 255)
        self._is_hovered = False
        self.setMouseTracking(True)
        
        # 强制设置下拉菜单样式，确保不透明
        self.setStyleSheet("""
            QComboBox::drop-down {
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #1e2329;
                border: 1px solid #4a90e2;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #4a90e2;
                selection-color: white;
                color: #e4e6eb;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 12px;
                background-color: transparent;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #2f3643;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #4a90e2;
                color: white;
            }
        """)
        
    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        # 在下拉按钮区域绘制箭头
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 计算箭头位置 (右侧25px区域的中心)
        arrow_width = 8
        arrow_height = 5
        rect = self.rect()
        x = rect.right() - 17
        y = rect.center().y() - arrow_height // 2
        
        # 绘制三角形箭头
        color = self._arrow_hover_color if self._is_hovered else self._arrow_color
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        path = QPainterPath()
        path.moveTo(x, y)
        path.lineTo(x + arrow_width, y)
        path.lineTo(x + arrow_width / 2, y + arrow_height)
        path.closeSubpath()
        
        painter.drawPath(path)
        painter.end()


class StyledSpinBox(QSpinBox):
    """自定义SpinBox - 手动绘制上下箭头，确保按钮区域可点击"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow_color = QColor(148, 163, 184)  # #94a3b8
        # 设置按钮样式：上下垂直排列
        self.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        # 确保键盘输入后回车生效
        self.setKeyboardTracking(False)
        
        # 设置样式，确保按钮区域可见且可点击
        self.setStyleSheet("""
            QSpinBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px 10px;
                padding-right: 28px;
                color: hsl(213, 31%, 91%);
                font-size: 14px;
            }
            QSpinBox:focus {
                border: 2px solid hsl(221.2, 83.2%, 53.3%);
            }
            QSpinBox:hover {
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 22px;
                height: 50%;
                border: none;
                border-top-right-radius: 5px;
                border-bottom: 1px solid hsl(217.2, 32.6%, 12%);
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
            QSpinBox::up-button:hover {
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 22px;
                height: 50%;
                border: none;
                border-bottom-right-radius: 5px;
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
            QSpinBox::down-button:hover {
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border: none;
            }
        """)
        
    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 箭头参数
        arrow_width = 6
        arrow_height = 4
        rect = self.rect()
        btn_width = 22
        h = rect.height()
        
        # 箭头水平位置（右侧按钮区域中心）
        arrow_x = rect.right() - btn_width // 2 - arrow_width // 2
        
        # 上箭头在上半部分中心，下箭头在下半部分中心
        up_y = h // 4 - arrow_height // 2 + 1
        down_y = h * 3 // 4 - arrow_height // 2 - 1
        
        painter.setBrush(QBrush(self._arrow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # 绘制上箭头 (向上的三角形)
        up_path = QPainterPath()
        up_path.moveTo(arrow_x + arrow_width / 2, up_y)
        up_path.lineTo(arrow_x, up_y + arrow_height)
        up_path.lineTo(arrow_x + arrow_width, up_y + arrow_height)
        up_path.closeSubpath()
        painter.drawPath(up_path)
        
        # 绘制下箭头 (向下的三角形)
        down_path = QPainterPath()
        down_path.moveTo(arrow_x, down_y)
        down_path.lineTo(arrow_x + arrow_width, down_y)
        down_path.lineTo(arrow_x + arrow_width / 2, down_y + arrow_height)
        down_path.closeSubpath()
        painter.drawPath(down_path)
        
        painter.end()
    
    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标点击，确保上下按钮正确响应"""
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.rect()
            btn_width = 22
            # PyQt6使用pos()方法获取坐标
            click_pos = event.pos()
            click_x = click_pos.x()
            click_y = click_pos.y()
            h = rect.height()
            
            # 检查是否点击在按钮区域内（右侧22px区域）
            if rect.right() - btn_width <= click_x <= rect.right():
                # 上半部分 = 上按钮
                if click_y < h / 2:
                    self.stepUp()
                    event.accept()
                    return
                # 下半部分 = 下按钮
                else:
                    self.stepDown()
                    event.accept()
                    return
        
        # 其他情况调用父类处理
        super().mousePressEvent(event)


class StyledDoubleSpinBox(QDoubleSpinBox):
    """自定义DoubleSpinBox - 手动绘制上下箭头，确保按钮区域可点击"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow_color = QColor(148, 163, 184)  # #94a3b8
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        self.setKeyboardTracking(False)
        
        # 设置样式，确保按钮区域可见且可点击
        self.setStyleSheet("""
            QDoubleSpinBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px 10px;
                padding-right: 28px;
                color: hsl(213, 31%, 91%);
                font-size: 14px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid hsl(221.2, 83.2%, 53.3%);
            }
            QDoubleSpinBox:hover {
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 22px;
                height: 50%;
                border: none;
                border-top-right-radius: 5px;
                border-bottom: 1px solid hsl(217.2, 32.6%, 12%);
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
            QDoubleSpinBox::up-button:hover {
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 22px;
                height: 50%;
                border: none;
                border-bottom-right-radius: 5px;
                background-color: hsl(217.2, 32.6%, 17.5%);
            }
            QDoubleSpinBox::down-button:hover {
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border: none;
            }
        """)
        
    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        arrow_width = 6
        arrow_height = 4
        rect = self.rect()
        btn_width = 22
        h = rect.height()
        
        arrow_x = rect.right() - btn_width // 2 - arrow_width // 2
        
        up_y = h // 4 - arrow_height // 2 + 1
        down_y = h * 3 // 4 - arrow_height // 2 - 1
        
        painter.setBrush(QBrush(self._arrow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # 上箭头
        up_path = QPainterPath()
        up_path.moveTo(arrow_x + arrow_width / 2, up_y)
        up_path.lineTo(arrow_x, up_y + arrow_height)
        up_path.lineTo(arrow_x + arrow_width, up_y + arrow_height)
        up_path.closeSubpath()
        painter.drawPath(up_path)
        
        # 下箭头
        down_path = QPainterPath()
        down_path.moveTo(arrow_x, down_y)
        down_path.lineTo(arrow_x + arrow_width, down_y)
        down_path.lineTo(arrow_x + arrow_width / 2, down_y + arrow_height)
        down_path.closeSubpath()
        painter.drawPath(down_path)
        
        painter.end()
    
    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标点击，确保上下按钮正确响应"""
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.rect()
            btn_width = 22
            # PyQt6使用pos()方法获取坐标
            click_pos = event.pos()
            click_x = click_pos.x()
            click_y = click_pos.y()
            h = rect.height()
            
            # 检查是否点击在按钮区域内（右侧22px区域）
            if rect.right() - btn_width <= click_x <= rect.right():
                # 上半部分 = 上按钮
                if click_y < h / 2:
                    self.stepUp()
                    event.accept()
                    return
                # 下半部分 = 下按钮
                else:
                    self.stepDown()
                    event.accept()
                    return
        
        # 其他情况调用父类处理
        super().mousePressEvent(event)


class ImageResizeDialog(QDialog):
    """图片缩放选择对话框 - 当图片过大时提示用户选择缩放比例"""
    
    # 最大允许的像素数（约5000万像素，如 7071x7071）
    MAX_PIXELS = 50_000_000
    # 最大单边尺寸
    MAX_DIMENSION = 8192
    
    def __init__(self, parent, width, height, file_path=""):
        super().__init__(parent)
        self.original_width = width
        self.original_height = height
        self.selected_scale = 1.0  # 缩放比例（如0.5表示缩小到50%）
        self.result_action = None  # "resize", "cancel", "original"
        
        self.setWindowTitle("图片尺寸过大")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMaximumWidth(550)
        
        # 无边框窗口
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._setup_ui(file_path)
    
    def _setup_ui(self, file_path):
        # 主容器
        self.container = QLabel(self)
        self.container.setStyleSheet("""
            QLabel {
                background-color: hsl(222.2, 84%, 4.9%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 12px;
            }
        """)
        
        # 阴影
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(24, 20, 24, 24)
        container_layout.setSpacing(16)
        
        # 标题行
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        
        icon_label = QLabel("")
        icon_label.setStyleSheet("font-size: 24px; background: transparent;")
        title_layout.addWidget(icon_label)
        
        title_label = QLabel("图片尺寸过大")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: hsl(38, 92%, 50%);
            background: transparent;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: hsl(215, 20.2%, 65.1%);
                font-size: 20px;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: hsl(217.2, 32.6%, 17.5%);
                color: white;
            }
        """)
        close_btn.clicked.connect(self._on_cancel)
        title_layout.addWidget(close_btn)
        
        container_layout.addLayout(title_layout)
        
        # 图片信息
        pixels = self.original_width * self.original_height
        pixels_str = f"{pixels / 1_000_000:.1f}" if pixels >= 1_000_000 else f"{pixels / 1_000:.1f}K"
        
        info_text = f"""当前图片分辨率为 <b>{self.original_width} × {self.original_height}</b>（{pixels_str}百万像素），
超出软件处理能力，可能导致内存不足或处理失败。<br><br>
建议缩小图片后再进行处理。请选择缩放比例："""
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            font-size: 13px;
            color: hsl(213, 31%, 91%);
            background: transparent;
            line-height: 1.6;
        """)
        container_layout.addWidget(info_label)
        
        # 缩放选项区域
        from PyQt6.QtWidgets import QButtonGroup, QRadioButton
        
        self.scale_group = QButtonGroup(self)
        scales_layout = QVBoxLayout()
        scales_layout.setSpacing(8)
        
        # 计算推荐的缩放比例
        recommended_scales = self._calculate_scales()
        
        for i, (scale, is_recommended) in enumerate(recommended_scales):
            new_w = int(self.original_width * scale)
            new_h = int(self.original_height * scale)
            new_pixels = new_w * new_h
            
            if new_pixels >= 1_000_000:
                pixels_text = f"{new_pixels / 1_000_000:.1f}M"
            else:
                pixels_text = f"{new_pixels / 1_000:.0f}K"
            
            percent = int(scale * 100)
            label_text = f"缩小到 {percent}%  →  {new_w} × {new_h}（{pixels_text}像素）"
            if is_recommended:
                label_text += "  ⭐ 推荐"
            
            radio = QRadioButton(label_text)
            radio.setStyleSheet("""
                QRadioButton {
                    font-size: 13px;
                    color: hsl(213, 31%, 91%);
                    background: transparent;
                    padding: 8px 12px;
                    border-radius: 6px;
                }
                QRadioButton:hover {
                    background: hsl(217.2, 32.6%, 12%);
                }
                QRadioButton::indicator {
                    width: 16px;
                    height: 16px;
                }
                QRadioButton::indicator:unchecked {
                    border: 2px solid hsl(215, 20.2%, 45%);
                    border-radius: 8px;
                    background: transparent;
                }
                QRadioButton::indicator:checked {
                    border: 2px solid hsl(221.2, 83.2%, 53.3%);
                    border-radius: 8px;
                    background: hsl(221.2, 83.2%, 53.3%);
                }
            """)
            radio.scale_value = scale
            self.scale_group.addButton(radio, i)
            scales_layout.addWidget(radio)
            
            if is_recommended:
                radio.setChecked(True)
                self.selected_scale = scale
        
        self.scale_group.buttonClicked.connect(self._on_scale_selected)
        container_layout.addLayout(scales_layout)
        
        # 预览分辨率显示
        self.preview_label = QLabel()
        self._update_preview()
        self.preview_label.setStyleSheet("""
            font-size: 12px;
            color: hsl(215, 20.2%, 65.1%);
            background: hsl(217.2, 32.6%, 12%);
            padding: 10px 14px;
            border-radius: 6px;
            margin-top: 8px;
        """)
        container_layout.addWidget(self.preview_label)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # 取消按钮
        cancel_btn = QPushButton("取消导入")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border: 1px solid hsl(217.2, 32.6%, 25%);
                border-radius: 8px;
                color: hsl(213, 31%, 91%);
                font-size: 13px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 22%);
            }
        """)
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(cancel_btn)
        
        btn_layout.addStretch()
        
        # 强制原图按钮（小字提示风险）
        force_btn = QPushButton("强制原图导入")
        force_btn.setFixedHeight(38)
        force_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        force_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid hsl(0, 60%, 40%);
                border-radius: 8px;
                color: hsl(0, 70%, 60%);
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: hsl(0, 60%, 20%);
                border-color: hsl(0, 70%, 50%);
            }
        """)
        force_btn.setToolTip("可能导致内存不足或软件崩溃")
        force_btn.clicked.connect(self._on_force_original)
        btn_layout.addWidget(force_btn)
        
        # 确认缩放按钮
        confirm_btn = QPushButton("缩放并导入")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 13px;
                font-weight: 500;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)
        
        container_layout.addLayout(btn_layout)
        main_layout.addWidget(self.container)
    
    def _calculate_scales(self):
        """计算推荐的缩放比例列表"""
        scales = []
        w, h = self.original_width, self.original_height
        
        # 生成常见缩放比例
        possible_scales = [0.75, 0.5, 0.4, 0.33, 0.25, 0.2, 0.1]
        
        recommended_found = False
        for scale in possible_scales:
            new_w = int(w * scale)
            new_h = int(h * scale)
            new_pixels = new_w * new_h
            
            # 跳过太小的
            if new_w < 500 or new_h < 500:
                continue
            
            # 判断是否推荐（像素数在合理范围内）
            is_recommended = False
            if not recommended_found and new_pixels <= self.MAX_PIXELS and max(new_w, new_h) <= self.MAX_DIMENSION:
                is_recommended = True
                recommended_found = True
            
            scales.append((scale, is_recommended))
            
            # 最多显示5个选项
            if len(scales) >= 5:
                break
        
        # 如果没有找到推荐项，将第一个设为推荐
        if scales and not recommended_found:
            scales[0] = (scales[0][0], True)
        
        return scales
    
    def _on_scale_selected(self, button):
        """选择缩放比例"""
        self.selected_scale = button.scale_value
        self._update_preview()
    
    def _update_preview(self):
        """更新预览分辨率显示"""
        new_w = int(self.original_width * self.selected_scale)
        new_h = int(self.original_height * self.selected_scale)
        new_pixels = new_w * new_h
        
        if new_pixels >= 1_000_000:
            pixels_text = f"{new_pixels / 1_000_000:.2f} 百万像素"
        else:
            pixels_text = f"{new_pixels / 1_000:.0f} 千像素"
        
        self.preview_label.setText(
            f"缩放后分辨率：{new_w} × {new_h}（{pixels_text}）\n"
            f"预计内存占用：约 {new_pixels * 3 / 1024 / 1024:.1f} MB"
        )
    
    def _on_confirm(self):
        """确认缩放"""
        self.result_action = "resize"
        self.accept()
    
    def _on_cancel(self):
        """取消"""
        self.result_action = "cancel"
        self.reject()
    
    def _on_force_original(self):
        """强制原图"""
        self.result_action = "original"
        self.accept()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    @staticmethod
    def check_and_resize(parent, image_path):
        """
        检查图片大小，如果过大则弹出对话框让用户选择。
        
        返回: (action, scale) 
            - action: "ok" (无需缩放), "resize" (需要缩放), "cancel" (取消), "original" (强制原图)
            - scale: 缩放比例（仅当action为"resize"时有效）
        """
        import cv2
        import numpy as np
        
        # 读取图片获取尺寸（支持中文路径）
        try:
            # 尝试只读取图片头部获取尺寸
            from utils.image_utils import cv2_imread
            img = cv2_imread(image_path, cv2.IMREAD_UNCHANGED)
            
            if img is None:
                return ("ok", 1.0)  # 无法读取，让后续流程处理
            
            h, w = img.shape[:2]
            del img  # 释放内存
            
        except Exception:
            return ("ok", 1.0)
        
        pixels = w * h
        
        # 检查是否超限
        if pixels <= ImageResizeDialog.MAX_PIXELS and max(w, h) <= ImageResizeDialog.MAX_DIMENSION:
            return ("ok", 1.0)
        
        # 弹出对话框
        dialog = ImageResizeDialog(parent, w, h, image_path)
        dialog.exec()
        
        if dialog.result_action == "resize":
            return ("resize", dialog.selected_scale)
        elif dialog.result_action == "original":
            return ("original", 1.0)
        else:
            return ("cancel", 1.0)
