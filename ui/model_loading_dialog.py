"""模型加载对话框 - 简洁的转圈圈动画"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
import math


class ModelLoadingDialog(QDialog):
    """模型加载对话框 - 转圈圈加载动画"""
    
    def __init__(self, module_name="AI", parent=None):
        super().__init__(parent)
        self.setWindowTitle("加载中")
        self.setModal(True)
        self.setFixedSize(400, 200)
        # 无边框、半透明背景
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.module_name = module_name
        self._rotation = 0
        
        # 启动旋转动画
        self._timer = QTimer()
        self._timer.timeout.connect(self._rotate)
        self._timer.start(30)  # 30ms更新一次，流畅旋转
        
    def _rotate(self):
        """旋转动画"""
        self._rotation = (self._rotation + 6) % 360  # 每次旋转6度
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # 绘制圆角半透明背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 30, 55, 240))  # 深色半透明背景
        painter.drawRoundedRect(20, 20, w - 40, h - 40, 15, 15)
        
        # 绘制文字：请稍后
        painter.setPen(QColor(226, 232, 240))
        title_font = QFont("Microsoft YaHei", 14, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(0, 50, w, 30, Qt.AlignmentFlag.AlignCenter, "请稍后")
        
        # 绘制模块名称
        painter.setPen(QColor(160, 174, 192))
        msg_font = QFont("Microsoft YaHei", 11)
        painter.setFont(msg_font)
        painter.drawText(0, 75, w, 25, Qt.AlignmentFlag.AlignCenter, f"{self.module_name}大模型加载中...")
        
        # 绘制旋转的圆圈（转圈圈动画）
        center_x = w // 2
        center_y = h - 60
        radius = 20
        
        painter.translate(center_x, center_y)
        painter.rotate(self._rotation)
        
        # 绘制8个点组成的加载圆圈
        pen = QPen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        
        for i in range(8):
            angle = i * 45
            # 渐变透明度，形成追逐效果
            alpha = int(255 * (1 - i / 8))
            pen.setColor(QColor(66, 133, 244, alpha))
            painter.setPen(pen)
            
            # 计算点的位置
            x1 = radius * 0.7 * math.cos(math.radians(angle))
            y1 = radius * 0.7 * math.sin(math.radians(angle))
            x2 = radius * math.cos(math.radians(angle))
            y2 = radius * math.sin(math.radians(angle))
            
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
    
    def closeEvent(self, event):
        """关闭时停止动画"""
        self._timer.stop()
        super().closeEvent(event)
