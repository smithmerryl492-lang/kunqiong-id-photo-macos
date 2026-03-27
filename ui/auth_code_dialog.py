"""授权码输入对话框"""
import os
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QFont, QPixmap
from i18n import tr


class AuthCodeDialog(QDialog):
    """授权码输入对话框"""
    
    def __init__(self, auth_code_url: str = None, parent=None):
        super().__init__(parent)
        self.auth_code_url = auth_code_url
        self.auth_code = None
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(tr("auth.dialog.title"))
        
        # 【终极方案】彻底禁用调整大小 + 去除最大化/最小化按钮
        # 1. 设置窗口标志：只保留关闭按钮，去除最大化和最小化
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |  # 自定义窗口提示
            Qt.WindowType.WindowTitleHint |      # 显示标题栏
            Qt.WindowType.WindowCloseButtonHint | # 只显示关闭按钮
            Qt.WindowType.MSWindowsFixedSizeDialogHint  # Windows 专用：固定大小对话框
        )
        
        # 2. 完全禁用窗口的调整大小功能
        self.setFixedSize(600, 320)
        
        # 3. 禁用 SizeGrip（右下角的调整手柄）
        self.setSizeGripEnabled(False)
        
        # 4. 设置大小策略为固定
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: hsl(222.2, 84%, 4.9%);
            }
            QLabel {
                color: hsl(213, 31%, 91%);
                background: transparent;
            }
            QLabel#title {
                color: hsl(213, 31%, 95%);
                font-size: 20px;
                font-weight: 600;
                padding: 8px 0;
            }
            QLabel#hint {
                color: hsl(215, 20.2%, 70%);
                font-size: 14px;
                line-height: 1.5;
            }
            QLabel#info {
                color: hsl(215, 20.2%, 60%);
                font-size: 12px;
                background-color: hsl(224, 71.4%, 6%);
                border: 1px solid hsl(217.2, 32.6%, 20%);
                border-radius: 6px;
                padding: 12px 16px;
                line-height: 1.6;
            }
            QLineEdit {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                padding: 12px 16px;
                color: hsl(213, 31%, 91%);
                font-size: 15px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: hsl(221.2, 83.2%, 53.3%);
                background-color: hsl(224, 71.4%, 5%);
            }
            QLineEdit:hover {
                border-color: hsl(217.2, 32.6%, 25%);
            }
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 14px;
                min-width: 80px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: hsl(215, 27.9%, 22%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
            QPushButton:pressed {
                background-color: hsl(215, 27.9%, 18%);
            }
            QPushButton#btn_confirm {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                min-width: 100px;
            }
            QPushButton#btn_confirm:hover {
                background-color: hsl(217.2, 91.2%, 59.8%);
                border-color: hsl(217.2, 91.2%, 59.8%);
            }
            QPushButton#btn_confirm:pressed {
                background-color: hsl(221.2, 83.2%, 48%);
            }
            QPushButton#btn_get_code {
                color: hsl(221.2, 83.2%, 58%);
                background: transparent;
                border: 1px dashed hsl(217.2, 32.6%, 25%);
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                min-width: 140px;
            }
            QPushButton#btn_get_code:hover {
                color: hsl(217.2, 91.2%, 65%);
                background-color: hsl(221.2, 83.2%, 8%);
                border-color: hsl(221.2, 83.2%, 40%);
                border-style: solid;
            }
            QPushButton#btn_get_code:pressed {
                background-color: hsl(221.2, 83.2%, 6%);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 35, 40, 35)  # 原始边距
        layout.setSpacing(18)  # 原始间距
        
        # 标题（带图标）
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图标
        icon_label = QLabel()
        # 获取 kunqiong.ico 的路径
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            base_path = sys._MEIPASS
        else:
            # 开发环境
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        icon_path = os.path.join(base_path, 'kunqiong.ico')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # 缩放图标到合适大小（24x24）
            scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(scaled_pixmap)
        icon_label.setStyleSheet("background: transparent;")
        title_layout.addWidget(icon_label)
        
        # 标题文字
        title = QLabel(tr("auth.dialog.header"))
        title.setObjectName("title")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("background: transparent;")
        title_layout.addWidget(title)
        
        layout.addWidget(title_container)
        
        # 提示信息
        hint = QLabel(tr("auth.dialog.hint"))
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)  # 允许自动换行
        layout.addWidget(hint)
        
        # 输入框
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText(tr("auth.dialog.placeholder"))
        self.code_input.returnPressed.connect(self.on_confirm)
        layout.addWidget(self.code_input)
        
        # 获取授权码按钮
        get_code_container = QWidget()
        get_code_container.setStyleSheet("background: transparent;")
        get_code_layout = QHBoxLayout(get_code_container)
        get_code_layout.setContentsMargins(0, 0, 0, 0)
        get_code_layout.setSpacing(0)
        
        self.btn_get_code = QPushButton(tr("auth.dialog.get_code"))
        self.btn_get_code.setObjectName("btn_get_code")
        self.btn_get_code.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_get_code.clicked.connect(self.on_get_code)
        get_code_layout.addWidget(self.btn_get_code)
        get_code_layout.addStretch()
        
        layout.addWidget(get_code_container)
        
        layout.addSpacing(10)  # 原始间距
        layout.addStretch()  # 弹性空间，消除留白
        
        # 按钮
        button_row = QWidget()
        button_row.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)
        
        btn_cancel = QPushButton(tr("common.cancel"))
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)
        
        button_layout.addStretch()
        
        self.btn_confirm = QPushButton(tr("auth.dialog.confirm"))
        self.btn_confirm.setObjectName("btn_confirm")
        self.btn_confirm.clicked.connect(self.on_confirm)
        button_layout.addWidget(self.btn_confirm)
        
        layout.addWidget(button_row)
        
        # 焦点到输入框
        self.code_input.setFocus()
    
    def on_get_code(self):
        """打开浏览器获取授权码"""
        if self.auth_code_url:
            from utils.auth_code import open_auth_code_url
            open_auth_code_url(self.auth_code_url)
    
    def on_confirm(self):
        """确认输入"""
        code = self.code_input.text().strip()
        if not code:
            from ui.custom_widgets import StyledMessageBox
            StyledMessageBox.warning(self, tr("common.tip"), tr("auth.dialog.empty_code"))
            return
        
        self.auth_code = code
        self.accept()
    
    def get_auth_code(self) -> str:
        """获取输入的授权码"""
        return self.auth_code
    

