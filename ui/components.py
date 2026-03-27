"""通用UI组件"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog, QSlider, QSpinBox, QDialog,
    QRadioButton, QButtonGroup, QCheckBox, QLineEdit
)
from ui.custom_widgets import StyledMessageBox, ImageResizeDialog
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint, QSizeF, QRect, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QWheelEvent, QBrush, QFont
import os
import cv2
import numpy as np
import tempfile
from i18n import tr
from ui.emoji_icons import set_button_emoji_icon

# 从 id_photo 模块导入翻译函数
from modules.id_photo import translate_color_dialog_to_chinese


def save_with_size_limit(img: np.ndarray, path: str, max_kb: int = None) -> bool:
    """
    保存图片，可选限制文件大小
    
    Args:
        img: BGR格式图像
        path: 保存路径
        max_kb: 最大文件大小（KB），None表示不限制
    
    Returns:
        是否保存成功
    """
    # 确保目标目录存在
    output_dir = os.path.dirname(path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    if max_kb is None:
        # 不限制大小，直接保存（支持中文路径）
        ext = os.path.splitext(path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            success, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        elif ext == '.png':
            success, encoded = cv2.imencode('.png', img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        else:
            success, encoded = cv2.imencode('.png', img)
        
        if success:
            with open(path, 'wb') as f:
                f.write(encoded.tobytes())
            return True
        return False
    
    # 根据扩展名决定格式
    ext = os.path.splitext(path)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        # JPEG格式，通过quality参数控制大小
        max_bytes = max_kb * 1024
        
        # 二分查找合适的quality
        low, high = 5, 95
        best_quality = 95
        
        while low <= high:
            mid = (low + high) // 2
            
            # 编码测试
            encode_param = [cv2.IMWRITE_JPEG_QUALITY, mid]
            _, buf = cv2.imencode('.jpg', img, encode_param)
            size = len(buf)
            
            if size <= max_bytes:
                best_quality = mid
                low = mid + 1  # 尝试更高质量
            else:
                high = mid - 1  # 需要更低质量
        
        # 使用找到的最佳质量保存
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, best_quality]
        _, buf = cv2.imencode('.jpg', img, encode_param)
        
        # 如果仍然超过限制，尝试缩小图片
        if len(buf) > max_bytes:
            h, w = img.shape[:2]
            scale = 0.9
            while len(buf) > max_bytes and scale > 0.3:
                new_w = int(w * scale)
                new_h = int(h * scale)
                scaled_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                _, buf = cv2.imencode('.jpg', scaled_img, [cv2.IMWRITE_JPEG_QUALITY, best_quality])
                scale -= 0.1
        
        with open(path, 'wb') as f:
            f.write(buf)
        return True
        
    else:
        # PNG格式，主要通过压缩级别控制
        # PNG是无损的，大小控制有限
        encode_param = [cv2.IMWRITE_PNG_COMPRESSION, 9]  # 最大压缩
        success, encoded = cv2.imencode('.png', img, encode_param)
        if success:
            with open(path, 'wb') as f:
                f.write(encoded.tobytes())
            return True
        return False


def create_checkerboard_pixmap(width: int, height: int, cell_size: int = 10) -> QPixmap:
    """创建棋盘格背景（用于显示透明区域）"""
    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    
    light_color = QColor(255, 255, 255)  # 白色
    dark_color = QColor(204, 204, 204)   # 浅灰色
    
    for y in range(0, height, cell_size):
        for x in range(0, width, cell_size):
            if (x // cell_size + y // cell_size) % 2 == 0:
                painter.fillRect(x, y, cell_size, cell_size, light_color)
            else:
                painter.fillRect(x, y, cell_size, cell_size, dark_color)
    
    painter.end()
    return pixmap


def create_transparent_preview(image_path: str, target_size: QSize = None) -> QPixmap:
    """创建带棋盘格背景的透明图片预览"""
    # 加载原图
    original = QPixmap(image_path)
    if original.isNull():
        return original
    
    # 检查是否有alpha通道
    image = original.toImage()
    if not image.hasAlphaChannel():
        # 没有透明通道，直接返回原图
        if target_size:
            return original.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return original
    
    # 确定目标大小
    if target_size:
        scaled = original.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        w, h = scaled.width(), scaled.height()
    else:
        scaled = original
        w, h = original.width(), original.height()
    
    # 创建棋盘格背景
    checkerboard = create_checkerboard_pixmap(w, h, 10)
    
    # 在棋盘格上绘制图片
    result = QPixmap(w, h)
    painter = QPainter(result)
    painter.drawPixmap(0, 0, checkerboard)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    
    return result


class ImagePreviewWidget(QWidget):
    """图片预览组件，支持缩放、拖拽、画笔标记"""
    
    # 信号：当mask更新时发出
    mask_updated = pyqtSignal(str)  # 发出mask文件路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_image = None
        self.display_image = None
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.offset_x = 0
        self.offset_y = 0
        self.drawing = False
        self.panning = False
        self.last_point = None
        self.pan_start_point = None
        self.brush_size = 10  # 默认笔刷大小
        self.mask = None
        self.mask_path = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 图片显示区域（简单界面）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("background-color: #252b35; border: 1px solid #3d4554;")
        self.image_label.setScaledContents(True)  # 自动缩放以适应显示
        
        # 鼠标事件（简单版本，仅支持左键涂抹）
        self.image_label.mousePressEvent = self.on_mouse_press
        self.image_label.mouseMoveEvent = self.on_mouse_move
        self.image_label.mouseReleaseEvent = self.on_mouse_release
        
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)
        
        # 提示信息
        self.info_label = QLabel(tr("image.mark_instruction"))
        self.info_label.setStyleSheet("color: #707a85; font-size: 9pt; padding: 5px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
    
    def load_image(self, image_path: str):
        """加载图片"""
        if not os.path.exists(image_path):
            StyledMessageBox.warning(self, tr("common.error"), tr("image.load.file_missing"))
            return False
        
        try:
            # 检查图片大小，超大图弹出缩放对话框
            action, scale = ImageResizeDialog.check_and_resize(self, image_path)
            
            if action == "cancel":
                return False  # 用户取消
            
            # 读取图片（支持中文路径）
            from utils.image_utils import cv2_imread
            img = cv2_imread(image_path)
            if img is None:
                StyledMessageBox.warning(self, tr("common.error"), tr("image.load.read_failed"))
                return False
            
            # 如果需要缩放
            if action == "resize" and scale < 1.0:
                h, w = img.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            self.original_image = img
            self.display_image = img.copy()
            
            # 初始化mask
            h, w = img.shape[:2]
            self.mask = np.zeros((h, w), dtype=np.uint8)
            
            # 显示图片
            self.update_display()
            self.info_label.setText(tr("image.mark_instruction_ready"))
            return True
        except Exception as e:
            StyledMessageBox.critical(self, "错误", f"加载图片失败: {str(e)}")
            return False
    
    def update_display(self):
        """更新显示"""
        if self.display_image is None:
            return
        
        # 将mask叠加到图片上
        display = self.display_image.copy()
        if self.mask.sum() > 0:
            # 红色半透明mask
            mask_colored = np.zeros_like(display)
            mask_colored[:, :, 2] = self.mask  # 红色通道
            display = cv2.addWeighted(display, 0.7, mask_colored, 0.3, 0)
        
        # 转换为QPixmap显示
        height, width, channel = display.shape
        bytes_per_line = 3 * width
        q_image = QImage(display.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(q_image)
        
        # 缩放以适应显示
        label_size = self.image_label.size()
        if label_size.width() > 0 and label_size.height() > 0:
            scaled_pixmap = pixmap.scaled(
                label_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
    
    
    def on_mouse_press(self, event):
        """鼠标按下（简单版本，仅左键涂抹）"""
        if self.original_image is None:
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.position()
            self.draw_mask(event.position())
    
    def on_mouse_move(self, event):
        """鼠标移动"""
        if self.drawing and self.last_point:
            self.draw_mask(event.position())
            self.last_point = event.position()
    
    def on_mouse_release(self, event):
        """鼠标释放"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            self.last_point = None
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
    
    def fit_to_window(self):
        """适应窗口大小"""
        if self.original_image is None:
            return
        
        viewport_size = self.scroll_area.viewport().size()
        img_h, img_w = self.original_image.shape[:2]
        
        if viewport_size.width() > 0 and viewport_size.height() > 0:
            scale_w = viewport_size.width() / img_w
            scale_h = viewport_size.height() / img_h
            self.scale_factor = min(scale_w, scale_h) * 0.95  # 留一点边距
            
            # 重置滚动位置
            scroll_bar_h = self.scroll_area.horizontalScrollBar()
            scroll_bar_v = self.scroll_area.verticalScrollBar()
            if scroll_bar_h:
                scroll_bar_h.setValue(0)
            if scroll_bar_v:
                scroll_bar_v.setValue(0)
            
            self.update_display()
    
    def actual_size(self):
        """实际大小（100%）"""
        if self.original_image is None:
            return
        self.scale_factor = 1.0
        
        # 重置滚动位置
        scroll_bar_h = self.scroll_area.horizontalScrollBar()
        scroll_bar_v = self.scroll_area.verticalScrollBar()
        if scroll_bar_h:
            scroll_bar_h.setValue(0)
        if scroll_bar_v:
            scroll_bar_v.setValue(0)
        
        self.update_display()
    
    
    def screen_to_image_coords(self, screen_pos: QPoint):
        """将屏幕坐标（相对于label）转换为图片坐标"""
        if self.original_image is None:
            return 0, 0
        
        # 获取滚动位置
        scroll_bar_h = self.scroll_area.horizontalScrollBar()
        scroll_bar_v = self.scroll_area.verticalScrollBar()
        scroll_x = scroll_bar_h.value() if scroll_bar_h else 0
        scroll_y = scroll_bar_v.value() if scroll_bar_v else 0
        
        # 转换为图片坐标（考虑滚动和缩放）
        img_x = (screen_pos.x() + scroll_x) / self.scale_factor
        img_y = (screen_pos.y() + scroll_y) / self.scale_factor
        
        return img_x, img_y
    
    def draw_mask(self, pos):
        """在mask上绘制（简单版本）"""
        if self.original_image is None or self.mask is None:
            return
        
        # 获取图片在label中的实际显示位置和大小
        pixmap = self.image_label.pixmap()
        if pixmap is None:
            return
        
        label_size = self.image_label.size()
        pixmap_size = pixmap.size()
        
        # 计算在label中的偏移（居中显示）
        offset_x = (label_size.width() - pixmap_size.width()) // 2
        offset_y = (label_size.height() - pixmap_size.height()) // 2
        
        # 转换为图片坐标
        img_x = int((pos.x() - offset_x) * self.original_image.shape[1] / pixmap_size.width())
        img_y = int((pos.y() - offset_y) * self.original_image.shape[0] / pixmap_size.height())
        
        # 检查坐标是否在图片范围内
        if 0 <= img_x < self.original_image.shape[1] and 0 <= img_y < self.original_image.shape[0]:
            # 绘制圆形
            cv2.circle(self.mask, (img_x, img_y), self.brush_size, 255, -1)
            
            # 如果上次有坐标，画线连接
            if self.last_point:
                last_img_x = int((self.last_point.x() - offset_x) * self.original_image.shape[1] / pixmap_size.width())
                last_img_y = int((self.last_point.y() - offset_y) * self.original_image.shape[0] / pixmap_size.height())
                if 0 <= last_img_x < self.original_image.shape[1] and 0 <= last_img_y < self.original_image.shape[0]:
                    cv2.line(self.mask, (last_img_x, last_img_y), (img_x, img_y), 255, self.brush_size * 2)
            
            self.update_display()
    
    def clear_mask(self):
        """清除mask"""
        if self.original_image is not None:
            h, w = self.original_image.shape[:2]
            self.mask = np.zeros((h, w), dtype=np.uint8)
            self.update_display()
            self.save_mask()
    
    def save_mask(self):
        """保存mask到临时文件"""
        if self.mask is None or self.mask.sum() == 0:
            self.mask_path = None
            return
        
        try:
            import tempfile
            fd, self.mask_path = tempfile.mkstemp(suffix='.png', prefix='mask_')
            os.close(fd)
            cv2.imwrite(self.mask_path, self.mask)
            self.mask_updated.emit(self.mask_path)
        except Exception as e:
            StyledMessageBox.warning(self, "警告", f"保存mask失败: {str(e)}")
    
    def get_mask_path(self) -> str:
        """获取mask文件路径"""
        return self.mask_path
    
    def has_mask(self) -> bool:
        """检查是否有mask"""
        return self.mask is not None and self.mask.sum() > 0


class ImageCompareWidget(QWidget):
    """图片对比组件，显示处理前后对比（已废弃，保留兼容性）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 原图
        self.before_label = QLabel(tr("preview.before"))
        self.before_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.before_label.setMinimumSize(300, 300)
        self.before_label.setStyleSheet("background-color: #252b35; border: 1px solid #3d4554;")
        
        # 处理后
        self.after_label = QLabel(tr("preview.after"))
        self.after_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.after_label.setMinimumSize(300, 300)
        self.after_label.setStyleSheet("background-color: #252b35; border: 1px solid #3d4554;")
        
        layout.addWidget(self.before_label)
        layout.addWidget(self.after_label)
    
    def set_before_image(self, image_path: str):
        """设置原图"""
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.before_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.before_label.setPixmap(scaled)
    
    def set_after_image(self, image_path: str):
        """设置处理后图片"""
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.after_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.after_label.setPixmap(scaled)


class ResultImageWidget(QWidget):
    """处理结果图片组件，支持点击查看大图"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 图片显示区域
        self.image_label = QLabel(tr("preview.no_result"))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet("""
            background-color: #252b35; 
            border: 1px solid #3d4554;
            border-radius: 4px;
        """)
        self.image_label.setScaledContents(False)  # 不拉伸，保持等比例

        # 使label可点击
        self.image_label.mousePressEvent = self.on_image_clicked
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.image_label)

        # 提示信息
        self.hint_label = QLabel(tr("preview.click_to_view_large"))
        self.hint_label.setStyleSheet("color: #707a85; font-size: 9pt; padding: 5px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        # 保存原始pixmap用于resize时重新缩放
        self._original_pixmap = None

    def set_image(self, image_path: str):
        """设置图片"""
        self.image_path = image_path
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._original_pixmap = pixmap
                self._update_scaled_image()
                self.hint_label.setText(tr("preview.click_to_view_large"))
        else:
            self._original_pixmap = None
            self.image_label.clear()
            self.image_label.setText(tr("preview.no_result"))
            self.hint_label.setText("")

    def _update_scaled_image(self):
        """更新缩放后的图片显示（支持透明背景棋盘格）"""
        if self._original_pixmap is None:
            return
        
        # 检查是否有透明通道
        image = self._original_pixmap.toImage()
        if image.hasAlphaChannel():
            # 有透明通道，使用棋盘格背景预览
            preview = create_transparent_preview(self.image_path, self.image_label.size())
            self.image_label.setPixmap(preview)
        else:
            # 没有透明通道，普通缩放
            scaled = self._original_pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        """窗口大小改变时重新缩放图片"""
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self._update_scaled_image()
    
    def on_image_clicked(self, event):
        """图片点击事件"""
        if self.image_path and os.path.exists(self.image_path):
            self.show_fullscreen_image()
    
    def show_fullscreen_image(self, module_name: str = ""):
        """显示大图窗口，100%显示，支持滚轮缩放，带下载按钮
        
        Args:
            module_name: 模块名称，用于判断是否显示特定提示
        """
        if not self.image_path or not os.path.exists(self.image_path):
            return

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QPushButton, QWidget, QFileDialog
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap, QWheelEvent
        import shutil

        # 加载图片
        pixmap = QPixmap(self.image_path)
        if pixmap.isNull():
            return

        # 获取屏幕大小
        screen = self.screen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()

        # 图片原始大小
        img_width = pixmap.width()
        img_height = pixmap.height()

        # 窗口大小：90%屏幕
        max_width = int(screen_width * 0.9)
        max_height = int(screen_height * 0.9)
        window_width = max_width
        window_height = max_height

        # 创建对话框
        dialog.setWindowTitle(tr("preview.result_window_title"))
        dialog.setWindowTitle(tr("preview.result_window_title"))
        dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        dialog.setStyleSheet("background-color: hsl(222.2, 47.4%, 11.2%);")
        dialog.resize(window_width, window_height)

        # 窗口居中
        dialog.move(
            (screen_width - window_width) // 2 + screen.x(),
            (screen_height - window_height) // 2 + screen.y()
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 顶部工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet("""
            QWidget {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)

        # 下载按钮
        image_path_for_save = self.image_path
        def save_image():
            file_path, _ = QFileDialog.getSaveFileName(
                dialog, tr("save.dialog_title"), "", "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*.*)"
            )
            if file_path:
                try:
                    # 确保目标目录存在
                    output_dir = os.path.dirname(file_path)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    
                    shutil.copy2(image_path_for_save, file_path)
                    StyledMessageBox.success(dialog, tr("common.success"), tr("save.saved_to", file_path=file_path))
                except Exception as e:
                    StyledMessageBox.critical(dialog, "错误", f"保存失败：{str(e)}")

        btn_save = QPushButton(tr("common.save_image"))
        set_button_emoji_icon(btn_save, "💾")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: hsl(142.1, 76.2%, 36.3%);
                color: hsl(355.7, 100%, 97.3%);
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: hsl(142.1, 76.2%, 42%);
            }
        """)
        btn_save.clicked.connect(save_image)
        toolbar_layout.addWidget(btn_save)

        # 原图尺寸按钮
        btn_original = QPushButton(tr("common.original_size"))
        btn_original.setStyleSheet("""
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: hsl(215, 27.9%, 22%);
            }
        """)
        toolbar_layout.addWidget(btn_original)

        # 适应窗口按钮
        btn_fit = QPushButton(tr("common.fit_window"))
        btn_fit.setStyleSheet("""
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: hsl(215, 27.9%, 22%);
            }
        """)
        toolbar_layout.addWidget(btn_fit)
        
        # 缩放比例标签
        zoom_label = QLabel("100%")
        zoom_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                font-size: 12px;
                padding: 4px 8px;
                border: none;
                background: transparent;
            }
        """)
        toolbar_layout.addWidget(zoom_label)

        # 提示文字（仅对去水印和涂抹去除显示）
        if module_name in ["去除水印", "涂抹去除"]:
            tip_label = QLabel(tr("preview.selection_tip"))
            tip_label.setStyleSheet("""
                QLabel {
                    color: hsl(38, 92%, 50%);
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    background: transparent;
                    padding-left: 12px;
                }
            """)
            toolbar_layout.addWidget(tip_label)

        toolbar_layout.addStretch()

        # 图片尺寸信息
        size_label = QLabel(tr("common.size", width=img_width, height=img_height))
        size_label.setStyleSheet("""
            QLabel {
                color: hsl(215, 20.2%, 65.1%);
                font-size: 12px;
                border: none;
                background: transparent;
            }
        """)
        toolbar_layout.addWidget(size_label)

        # 关闭窗口按钮
        btn_close = QPushButton(tr("common.close_window"))
        set_button_emoji_icon(btn_close, "❌")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: hsl(0, 62.8%, 30.6%);
                border-color: hsl(0, 62.8%, 30.6%);
            }
        """)
        btn_close.clicked.connect(dialog.close)
        toolbar_layout.addWidget(btn_close)

        layout.addWidget(toolbar)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(False)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 图片居中
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea { border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 8px; background-color: hsl(224, 71.4%, 4.1%); }
            QScrollBar:vertical { background-color: hsl(217.2, 32.6%, 17.5%); width: 12px; border-radius: 6px; }
            QScrollBar::handle:vertical { background-color: hsl(215, 20.2%, 65.1%); border-radius: 6px; min-height: 30px; }
            QScrollBar:horizontal { background-color: hsl(217.2, 32.6%, 17.5%); height: 12px; border-radius: 6px; }
            QScrollBar::handle:horizontal { background-color: hsl(215, 20.2%, 65.1%); border-radius: 6px; min-width: 30px; }
        """)

        # 图片标签
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("background-color: hsl(224, 71.4%, 4.1%);")

        # 检查是否有透明通道
        has_alpha = pixmap.toImage().hasAlphaChannel()
        
        # 缩放状态 - 初始100%
        state = {
            'scale': 1.0,
            'min_scale': 0.1,
            'max_scale': 3.0,  # 限制最大缩放防止内存溢出
            'pixmap': pixmap,
            'has_alpha': has_alpha
        }

        def update_image():
            scaled_width = int(img_width * state['scale'])
            scaled_height = int(img_height * state['scale'])
            scaled_pixmap = pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            if state['has_alpha']:
                # 有透明通道，绘制棋盘格背景
                checkerboard = create_checkerboard_pixmap(scaled_width, scaled_height, 12)
                result = QPixmap(scaled_width, scaled_height)
                painter = QPainter(result)
                painter.drawPixmap(0, 0, checkerboard)
                painter.drawPixmap(0, 0, scaled_pixmap)
                painter.end()
                image_label.setPixmap(result)
            else:
                image_label.setPixmap(scaled_pixmap)
            
            image_label.setFixedSize(scaled_width, scaled_height)
            zoom_label.setText(f"{int(state['scale'] * 100)}%")

        def set_original_size():
            state['scale'] = 1.0
            update_image()

        def fit_to_window():
            viewport = scroll_area.viewport()
            vw, vh = viewport.width() - 20, viewport.height() - 20
            scale_w = vw / img_width
            scale_h = vh / img_height
            fit_scale = min(scale_w, scale_h)
            # 如果图片小于窗口，不放大，保持原始大小
            state['scale'] = min(fit_scale, 1.0)
            update_image()

        btn_original.clicked.connect(set_original_size)
        btn_fit.clicked.connect(fit_to_window)

        scroll_area.setWidget(image_label)
        layout.addWidget(scroll_area, stretch=1)

        # 滚轮缩放
        def on_wheel(event: QWheelEvent):
            delta = event.angleDelta().y()
            if delta > 0:
                state['scale'] = min(state['scale'] * 1.15, state['max_scale'])
            else:
                state['scale'] = max(state['scale'] / 1.15, state['min_scale'])
            update_image()

        scroll_area.wheelEvent = on_wheel

        # ESC键关闭
        def keyPressEvent(event):
            if event.key() == Qt.Key.Key_Escape:
                dialog.close()
            else:
                QDialog.keyPressEvent(dialog, event)

        dialog.keyPressEvent = keyPressEvent
        
        # 显示窗口后，默认适应窗口大小
        def on_shown():
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, fit_to_window)
        
        dialog.showEvent = lambda e: on_shown()
        dialog.exec()


class PrintLayoutDialog(QDialog):
    """证件照排版打印设置对话框 - 全屏，上参数下预览，无预览按钮"""
    PAPER_OPTIONS = [
        ("id_photo.paper_6inch", "6inch"),
        ("id_photo.paper_5inch", "5inch"),
        ("id_photo.paper_a4", "A4"),
        ("id_photo.paper_3r", "3R"),
        ("id_photo.paper_4r", "4R"),
    ]
    
    def __init__(self, photo_path: str, parent=None, print_params: dict = None, output_params: dict = None, output_types: dict = None):
        super().__init__(parent)
        self.photo_path = photo_path
        self.result_path = None
        self.print_params = print_params or {}
        self.output_params = output_params or {}
        self.output_types = output_types or {}
        self._layout_pixmap = None  # 原始排版图，用于缩放显示
        self._preview_timer = None
        self.setWindowTitle(tr("print_layout.title"))
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self.setStyleSheet("""
            QDialog {
                background-color: hsl(222.2, 47.4%, 11.2%);
            }
        """)
        self._init_ui()

    def _normalize_paper_size(self, paper_size: str) -> str:
        aliases = {
            "六寸": "6inch",
            "6寸": "6inch",
            "五寸": "5inch",
            "5寸": "5inch",
            "A4": "A4",
            "3R": "3R",
            "4R": "4R",
            "6inch": "6inch",
            "5inch": "5inch",
        }
        return aliases.get(paper_size, "6inch")

    def _populate_paper_combo(self):
        self.paper_combo.clear()
        for label_key, value in self.PAPER_OPTIONS:
            self.paper_combo.addItem(tr(label_key), value)

    def _set_paper_combo_value(self, paper_size: str):
        index = self.paper_combo.findData(self._normalize_paper_size(paper_size))
        self.paper_combo.setCurrentIndex(index if index >= 0 else 0)

    def _current_paper_size(self) -> str:
        return self.paper_combo.currentData() or "6inch"
    
    def _init_ui(self):
        from PyQt6.QtWidgets import QFrame
        from PyQt6.QtWidgets import QSizePolicy
        from ui.custom_widgets import StyledComboBox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # 顶部：参数 + 按钮 一行
        top_bar = QWidget()
        top_bar.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(12)

        title = QLabel(tr("print_layout.title"))
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        top_layout.addWidget(title)

        paper_label = QLabel(tr("print_layout.paper"))
        paper_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%);")
        top_layout.addWidget(paper_label)

        self.paper_combo = StyledComboBox()
        self._populate_paper_combo()
        self._set_paper_combo_value(self.print_params.get('paper_size', '6inch'))
        self.paper_combo.setStyleSheet("""
            QComboBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 4px;
                padding: 4px 8px;
                color: hsl(213, 31%, 91%);
                min-width: 72px;
            }
            QComboBox:hover { border-color: hsl(221.2, 83.2%, 53.3%); }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                selection-background-color: hsl(221.2, 83.2%, 53.3%);
                color: hsl(213, 31%, 91%);
            }
        """)
        top_layout.addWidget(self.paper_combo)

        count_label = QLabel(tr("print_layout.count"))
        count_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%);")
        top_layout.addWidget(count_label)

        self.count_group = QButtonGroup(self)
        radio_style = """
            QRadioButton {
                color: hsl(213, 31%, 91%);
                padding: 5px 12px;
                background-color: hsl(217.2, 32.6%, 17.5%);
                border: 1px solid hsl(217.2, 32.6%, 25%);
                border-radius: 4px;
                spacing: 4px;
            }
            QRadioButton:hover { background-color: hsl(217.2, 32.6%, 22%); border-color: hsl(221.2, 83.2%, 53.3%); }
            QRadioButton:checked { background-color: hsl(221.2, 83.2%, 53.3%); border-color: hsl(221.2, 83.2%, 53.3%); color: white; font-weight: 600; }
            QRadioButton::indicator { width: 12px; height: 12px; border-radius: 6px; border: 2px solid hsl(217.2, 32.6%, 40%); background: hsl(224, 71.4%, 4.1%); }
            QRadioButton::indicator:checked { background: white; border-color: white; }
        """
        self.radio_4 = QRadioButton(tr("print_layout.option_4"))
        self.radio_4.setStyleSheet(radio_style)
        self.count_group.addButton(self.radio_4, 4)
        top_layout.addWidget(self.radio_4)
        self.radio_6 = QRadioButton(tr("print_layout.option_6"))
        self.radio_6.setStyleSheet(radio_style)
        self.radio_6.setChecked(True)
        self.count_group.addButton(self.radio_6, 6)
        top_layout.addWidget(self.radio_6)
        self.radio_8 = QRadioButton(tr("print_layout.option_8"))
        self.radio_8.setStyleSheet(radio_style)
        self.count_group.addButton(self.radio_8, 8)
        top_layout.addWidget(self.radio_8)

        gap_label = QLabel(tr("print_layout.spacing"))
        gap_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%);")
        top_layout.addWidget(gap_label)
        self.gap_combo = StyledComboBox()
        gap_options = ['0 mm', '1 mm', '2 mm', '3 mm', '4 mm', '5 mm', '8 mm', '10 mm', '15 mm', '20 mm']
        self.gap_combo.addItems(gap_options)
        default_spacing = self.print_params.get('spacing', 2)
        default_text = f"{default_spacing} mm"
        self.gap_combo.setCurrentText(default_text if default_text in gap_options else '2 mm')
        self.gap_combo.setStyleSheet("""
            QComboBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 4px;
                padding: 4px 8px;
                color: hsl(213, 31%, 91%);
                min-width: 70px;
            }
            QComboBox:hover { border-color: hsl(221.2, 83.2%, 53.3%); }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                selection-background-color: hsl(221.2, 83.2%, 53.3%);
                color: hsl(213, 31%, 91%);
            }
        """)
        top_layout.addWidget(self.gap_combo)

        top_layout.addStretch()

        btn_style = "QPushButton { background-color: hsl(217.2, 32.6%, 17.5%); color: hsl(213, 31%, 91%); border: none; border-radius: 6px; padding: 8px 16px; } QPushButton:hover { background-color: hsl(215, 27.9%, 22%); }"
        btn_cancel = QPushButton(tr("common.cancel"))
        btn_cancel.setStyleSheet(btn_style)
        btn_cancel.clicked.connect(self.reject)
        top_layout.addWidget(btn_cancel)
        btn_save = QPushButton(tr("common.save"))
        set_button_emoji_icon(btn_save, "💾")
        btn_save.setStyleSheet("QPushButton { background-color: hsl(142.1, 76.2%, 36.3%); color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; } QPushButton:hover { background-color: hsl(142.1, 76.2%, 42%); }")
        btn_save.clicked.connect(self._on_save)
        top_layout.addWidget(btn_save)
        btn_print = QPushButton(tr("common.print"))
        set_button_emoji_icon(btn_print, "🖨️")
        btn_print.setStyleSheet("QPushButton { background-color: hsl(262.1, 83.3%, 57.8%); color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; } QPushButton:hover { background-color: hsl(262.1, 83.3%, 63%); }")
        btn_print.clicked.connect(self._on_print)
        top_layout.addWidget(btn_print)

        layout.addWidget(top_bar)

        # 预览区：充满剩余空间，同比例缩放显示
        preview_frame = QFrame()
        preview_frame.setStyleSheet("QFrame { background-color: hsl(217.2, 32.6%, 12%); border-radius: 6px; }")
        preview_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(200, 200)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setStyleSheet("color: hsl(215, 20.2%, 45%); font-size: 13px;")
        self.preview_label.setText(tr("print_layout.generating"))
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_frame, stretch=1)

        def _debounced_update():
            QTimer.singleShot(350, self._update_preview)

        self.paper_combo.currentIndexChanged.connect(_debounced_update)
        self.count_group.buttonToggled.connect(lambda btn, ok: _debounced_update() if ok else None)
        self.gap_combo.currentTextChanged.connect(_debounced_update)
        
    
    def _update_preview(self):
        """生成排版图并刷新预览区（参数变更时调用）"""
        paper_type = self._current_paper_size()
        count = self.count_group.checkedId()
        if count < 0:
            count = 6
        gap_text = self.gap_combo.currentText()
        gap_mm = int(gap_text.replace(' mm', '').strip())

        if not self.photo_path or not os.path.exists(self.photo_path):
            self.preview_label.setText(tr("print_layout.image_unavailable"))
            self._layout_pixmap = None
            return

        try:
            from modules.id_photo import IDPhotoModule
            module = IDPhotoModule()
            # 预览使用真实尺寸生成，UI层自动缩放显示
            result_path = module.create_print_layout(
                self.photo_path, paper_type, count, gap_mm, for_preview=False
            )
            from utils.image_utils import cv2_imread
            img = cv2_imread(result_path)
            if img is None:
                self.preview_label.setText(tr("print_layout.preview_failed"))
                self._layout_pixmap = None
                return
            h, w = img.shape[:2]
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            self._layout_pixmap = QPixmap.fromImage(qimg.copy())
            self._render_preview()
        except ValueError as e:
            # 排版失败（照片太大）
            error_msg = str(e)
            # 在预览区显示简洁提示
            lines = error_msg.split('\n')
            short_msg = lines[0] if lines else error_msg
            self.preview_label.setText(f"?? {short_msg}\n\n{tr("preview.adjust_params_retry")}")
            self._layout_pixmap = None
        except Exception as e:
            self.preview_label.setText(f"预览失败: {str(e)}")
            self._layout_pixmap = None

    def _render_preview(self):
        """将 _layout_pixmap 同比例缩放到预览区并显示；超过则缩小"""
        if not self._layout_pixmap or self._layout_pixmap.isNull():
            return
        w = self.preview_label.width()
        h = self.preview_label.height()
        if w < 10 or h < 10:
            return
        px = self._layout_pixmap
        if px.width() <= 0 or px.height() <= 0:
            return
        scale = min(w / px.width(), h / px.height())
        tw = max(1, int(px.width() * scale))
        th = max(1, int(px.height() * scale))
        scaled = px.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(50, self._update_preview)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._layout_pixmap and not self._layout_pixmap.isNull():
            self._render_preview()
    
    def _on_save(self):
        """保存排版图"""
        from PyQt6.QtWidgets import QFileDialog
        import cv2
        from PIL import Image
        import os
        
        paper_type = self._current_paper_size()
        count = self.count_group.checkedId()
        gap_text = self.gap_combo.currentText()
        gap_mm = int(gap_text.replace(' mm', ''))
        
        try:
            # 生成排版图
            from modules.id_photo import IDPhotoModule
            module = IDPhotoModule()
            
            self.result_path = module.create_print_layout(
                self.photo_path, paper_type, count, gap_mm
            )
            
            # 应用输出设置（KB大小/DPI）
            kb_enabled = self.output_params.get('kb_enabled', False)
            dpi_enabled = self.output_params.get('dpi_enabled', False)
            target_kb = self.output_params.get('target_kb', 50)
            dpi = self.output_params.get('dpi', 300)
            
            # 保存文件（默认英文文件名）
            default_filename = f"id_photo_layout_{paper_type}_{count}pcs.png"
            file_path, _ = QFileDialog.getSaveFileName(
                self, tr("print_layout.save_dialog_title"), default_filename,
                "PNG Files (*.png);;JPEG Files (*.jpg)"
            )
            
            if file_path:
                # 确保目标目录存在
                output_dir = os.path.dirname(file_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                
                # 读取排版图（支持中文路径）
                from utils.image_utils import cv2_imread
                img = cv2_imread(self.result_path)
                
                # 应用KB大小和DPI设置
                if kb_enabled:
                    try:
                        # 尝试使用官方函数
                        import sys
                        hivision_path = 'D:/HivisionIDPhotos'
                        if hivision_path not in sys.path:
                            sys.path.insert(0, hivision_path)
                        from hivision.utils import resize_image_to_kb
                        
                        resize_image_to_kb(img, file_path, target_kb, dpi if dpi_enabled else 300)
                        actual_size = os.path.getsize(file_path) / 1024
                        StyledMessageBox.success(self, tr("common.success"), 
                            tr("save.print_layout_saved_with_dpi", file_path=file_path, actual_size=actual_size, dpi=dpi if dpi_enabled else 300))
                    except ImportError:
                        # 备用方法
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(img_rgb)
                        quality = 95
                        while quality > 10:
                            import io
                            img_byte_arr = io.BytesIO()
                            pil_img.save(img_byte_arr, format='JPEG', quality=quality, 
                                       dpi=(dpi if dpi_enabled else 300, dpi if dpi_enabled else 300))
                            size_kb = len(img_byte_arr.getvalue()) / 1024
                            if size_kb <= target_kb:
                                with open(file_path, 'wb') as f:
                                    f.write(img_byte_arr.getvalue())
                                break
                            quality -= 5
                        actual_size = os.path.getsize(file_path) / 1024
                        StyledMessageBox.success(self, tr("common.success"), 
                            tr("save.print_layout_saved_with_dpi", file_path=file_path, actual_size=actual_size, dpi=dpi if dpi_enabled else 300))
                elif dpi_enabled:
                    # 只设置DPI
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(img_rgb)
                    pil_img.save(file_path, dpi=(dpi, dpi))
                    actual_size = os.path.getsize(file_path) / 1024
                    StyledMessageBox.success(self, tr("common.success"), 
                        tr("save.print_layout_saved_with_dpi", file_path=file_path, actual_size=actual_size, dpi=dpi))
                else:
                    # 默认保存
                    import shutil
                    shutil.copy2(self.result_path, file_path)
                    actual_size = os.path.getsize(file_path) / 1024
                    StyledMessageBox.success(self, tr("common.success"), 
                        tr("save.print_layout_saved", file_path=file_path, actual_size=actual_size))
                
                self.accept()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            StyledMessageBox.critical(self, "错误", f"生成排版图失败：{str(e)}")
    
    def _on_print(self):
        """打印排版图"""
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter, QImage
        import cv2
        
        paper_type = self._current_paper_size()
        count = self.count_group.checkedId()
        gap_text = self.gap_combo.currentText()
        gap_mm = int(gap_text.replace(' mm', ''))
        
        try:
            # 生成排版图
            from modules.id_photo import IDPhotoModule
            module = IDPhotoModule()
            
            result_path = module.create_print_layout(
                self.photo_path, paper_type, count, gap_mm
            )
            
            # 读取图片（支持中文路径）
            from utils.image_utils import cv2_imread
            img = cv2_imread(result_path)
            if img is None:
                StyledMessageBox.critical(self, tr("common.error"), tr("print_layout.read_failed"))
                return
            
            # 创建打印机对象
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            
            # 设置纸张大小（PyQt6 - 不设置纸张大小，让用户在打印对话框中手动选择）
            # 注意：不同版本的PyQt6 API可能不同，这里不强制设置，避免兼容性问题
            # 用户可以在打印对话框中选择正确的纸张类型
            print(f"[打印] 纸张类型: {paper_type}，请在打印对话框中选择对应的纸张大小")
            
            # 打开打印对话框
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec() == QPrintDialog.DialogCode.Accepted:
                # 转换图片为QImage
                h, w = img.shape[:2]
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                bytes_per_line = 3 * w
                q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                # 绘制到打印机
                painter = QPainter(printer)
                rect = painter.viewport()
                size = q_img.size()
                size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(q_img.rect())
                painter.drawImage(0, 0, q_img)
                painter.end()
                
                StyledMessageBox.success(self, tr("common.success"), tr("print_layout.task_sent"))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            StyledMessageBox.critical(self, "错误", f"打印失败：{str(e)}")


class IDPhotoResultWidget(QWidget):
    """证件照专用结果预览组件 - 支持实时切换背景色"""
    
    # 背景颜色选项 (BGR格式用于OpenCV处理, RGB用于UI显示)
    BG_COLORS = {
        'white': {'bgr': (255, 255, 255), 'rgb': '#FFFFFF'},
        'blue': {'bgr': (219, 142, 67), 'rgb': '#438EDB'},
        'light_blue': {'bgr': (235, 180, 120), 'rgb': '#78B4EB'},
        'dark_blue': {'bgr': (180, 100, 50), 'rgb': '#326496'},
        'red': {'bgr': (67, 67, 219), 'rgb': '#DB4343'},
        'dark_red': {'bgr': (60, 60, 180), 'rgb': '#B43C3C'},
        'gray': {'bgr': (200, 200, 200), 'rgb': '#C8C8C8'},
    }
    COLOR_LABEL_KEYS = {
        'white': 'id_photo.bg_white',
        'blue': 'id_photo.bg_blue',
        'light_blue': 'id_photo.bg_light_blue',
        'dark_blue': 'id_photo.bg_dark_blue',
        'red': 'id_photo.bg_red',
        'dark_red': 'id_photo.bg_dark_red',
        'gray': 'id_photo.bg_gray',
    }
    
    # 标准证件照尺寸映射 (像素 -> 毫米) @300dpi
    SIZE_MAP = {
        (295, 413): (25, 35),    # 一寸
        (260, 378): (22, 32),    # 小一寸
        (390, 567): (33, 48),    # 大一寸/护照
        (413, 579): (35, 49),    # 二寸
        (413, 531): (35, 45),    # 小二寸
        (358, 441): (26, 32),    # 身份证
    }
    
    def _get_size_mm(self, w, h):
        """根据像素尺寸获取毫米尺寸"""
        # 精确匹配
        if (w, h) in self.SIZE_MAP:
            return self.SIZE_MAP[(w, h)]
        # 近似匹配（允许5像素误差）
        for (pw, ph), (mw, mh) in self.SIZE_MAP.items():
            if abs(w - pw) <= 5 and abs(h - ph) <= 5:
                return (mw, mh)
        return None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None  # 原始抠图结果（带alpha通道）
        self.rgba_image = None  # numpy数组格式的RGBA图像
        self.current_bg_color = 'white'
        self.current_render_mode = 'pure_color'  # 渲染模式（官方）
        self.current_result_path = None  # 当前背景色应用后的图片路径
        self.custom_colors = {}  # 自定义颜色存储
        self.id_photo_module = None  # ID照片模块引用（用于调用渲染方法）
        self.init_ui()

    def _normalize_bg_color(self, color_name: str) -> str:
        aliases = {
            '白色': 'white',
            '蓝色': 'blue',
            '浅蓝色': 'light_blue',
            '深蓝色': 'dark_blue',
            '红色': 'red',
            '深红色': 'dark_red',
            '灰色': 'gray',
            'white': 'white',
            'blue': 'blue',
            'light_blue': 'light_blue',
            'dark_blue': 'dark_blue',
            'red': 'red',
            'dark_red': 'dark_red',
            'gray': 'gray',
        }
        return aliases.get(color_name, color_name)

    def _normalize_render_mode(self, render_mode: str) -> str:
        aliases = {
            '纯色': 'pure_color',
            '上下渐变（白色）': 'updown_gradient',
            '中心渐变（白色）': 'center_gradient',
            'pure_color': 'pure_color',
            'updown_gradient': 'updown_gradient',
            'center_gradient': 'center_gradient',
        }
        return aliases.get(render_mode, render_mode)

    def _display_color_name(self, color_name: str) -> str:
        normalized = self._normalize_bg_color(color_name)
        label_key = self.COLOR_LABEL_KEYS.get(normalized)
        return tr(label_key) if label_key else color_name
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(8)
        
        # 背景色选择区域
        color_panel = QWidget()
        color_panel.setStyleSheet("""
            QWidget {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        color_layout = QHBoxLayout(color_panel)
        color_layout.setContentsMargins(8, 4, 8, 4)
        color_layout.setSpacing(6)
        
        # 标签
        label = QLabel(tr("id_photo.background"))
        label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none; font-size: 12px;")
        color_layout.addWidget(label)
        
        # 颜色按钮（缩小尺寸）
        self.color_buttons = {}
        for name, colors in self.BG_COLORS.items():
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(self._display_color_name(name))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors['rgb']};
                    border: 2px solid hsl(217.2, 32.6%, 25%);
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }}
                QPushButton:checked {{
                    border-color: hsl(142.1, 76.2%, 46.3%);
                    border-width: 2px;
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self.on_color_selected(n))
            self.color_buttons[name] = btn
            color_layout.addWidget(btn)
        
        # 默认选中白色
        self.color_buttons['white'].setChecked(True)
        
        # 自定义颜色按钮
        self.custom_color_btn = QPushButton("+")
        self.custom_color_btn.setFixedSize(24, 24)
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.setToolTip(tr("id_photo.custom_color"))
        self.custom_color_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #FF6B6B, stop:0.25 #4ECDC4, stop:0.5 #45B7D1, stop:0.75 #96E6A1, stop:1 #DDA0DD);
                border: 2px dashed hsl(217.2, 32.6%, 35%);
                border-radius: 4px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                border-color: hsl(221.2, 83.2%, 53.3%);
                border-style: solid;
            }
        """)
        self.custom_color_btn.clicked.connect(self._on_custom_color)
        color_layout.addWidget(self.custom_color_btn)
        
        color_layout.addStretch()
        
        # 当前颜色名称
        self.color_name_label = QLabel(self._display_color_name('white'))
        self.color_name_label.setStyleSheet("color: hsl(213, 31%, 91%); background: transparent; border: none; font-size: 11px;")
        color_layout.addWidget(self.color_name_label)
        
        layout.addWidget(color_panel)
        
        # 图片预览区域（模拟照片纸效果）
        self.preview_container = QWidget()
        self.preview_container.setStyleSheet("""
            QWidget {
                background-color: hsl(217.2, 32.6%, 12%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 照片框（带阴影效果）
        self.photo_frame = QLabel()
        self.photo_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_frame.setMinimumSize(200, 280)
        self.photo_frame.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid hsl(217.2, 32.6%, 30%);
                border-radius: 4px;
            }
        """)
        self.photo_frame.setScaledContents(False)
        self.photo_frame.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_frame.mousePressEvent = self.on_photo_clicked
        preview_layout.addWidget(self.photo_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.preview_container, stretch=1)
        
        # 底部提示
        hint = QLabel(tr("id_photo.hint"))
        hint.setStyleSheet("color: hsl(215, 20.2%, 50%); font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
    
    def set_image(self, image_path: str, rgba_image: np.ndarray = None):
        """设置证件照图片（带alpha通道的抠图结果）"""
        self.image_path = image_path
        
        if rgba_image is not None:
            self.rgba_image = rgba_image
        elif image_path and os.path.exists(image_path):
            # 从文件读取（支持中文路径）
            from utils.image_utils import cv2_imread
            img = cv2_imread(image_path, cv2.IMREAD_UNCHANGED)
            if img is not None and img.shape[2] == 4:
                self.rgba_image = img
            else:
                self.rgba_image = None
        else:
            self.rgba_image = None
        
        # 应用当前背景色
        self.apply_background_color()
    
    def on_color_selected(self, color_name: str):
        """选择背景色"""
        normalized_color = self._normalize_bg_color(color_name)
        # 更新按钮状态
        for name, btn in self.color_buttons.items():
            btn.setChecked(name == normalized_color)
        
        self.current_bg_color = normalized_color
        self.color_name_label.setText(self._display_color_name(normalized_color))
        
        # 应用新背景色
        self.apply_background_color()
    
    def _on_custom_color(self):
        """打开自定义颜色选择器"""
        from PyQt6.QtWidgets import QColorDialog, QDialog
        from PyQt6.QtGui import QColor
        
        color_dialog = QColorDialog(self)
        color_dialog.setWindowTitle(tr("id_photo.background_color"))
        color_dialog.setCurrentColor(QColor(255, 255, 255))
        # 设置中文界面
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        
        # 美化样式
        color_dialog.setStyleSheet("""
            QColorDialog {
                background-color: hsl(222.2, 84%, 4.9%);
                color: hsl(213, 31%, 91%);
            }
            QLabel {
                color: hsl(213, 31%, 91%);
                font-size: 13px;
            }
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
            QSpinBox, QLineEdit {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 4px;
                padding: 6px;
                color: hsl(213, 31%, 91%);
            }
            QSpinBox:focus, QLineEdit:focus {
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """)
        
        # 翻译为中文
        translate_color_dialog_to_chinese(color_dialog)
        
        if color_dialog.exec() == QDialog.DialogCode.Accepted:
            color = color_dialog.currentColor()
            if color.isValid():
                # 生成颜色名称
                r, g, b = color.red(), color.green(), color.blue()
                color_name = f"自定义#{r:02X}{g:02X}{b:02X}"
                rgb_hex = f"#{r:02X}{g:02X}{b:02X}"
                bgr = (b, g, r)  # OpenCV BGR格式
                
                # 添加到自定义颜色和BG_COLORS
                self.custom_colors[color_name] = {'bgr': bgr, 'rgb': rgb_hex}
            
            # 如果按钮已存在则更新，否则创建
            if color_name not in self.color_buttons:
                btn = QPushButton()
                btn.setFixedSize(32, 32)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(color_name)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {rgb_hex};
                        border: 2px solid hsl(217.2, 32.6%, 25%);
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{
                        border-color: hsl(221.2, 83.2%, 53.3%);
                    }}
                    QPushButton:checked {{
                        border-color: hsl(142.1, 76.2%, 46.3%);
                        border-width: 3px;
                    }}
                """)
                btn.setCheckable(True)
                btn.clicked.connect(lambda checked, n=color_name: self.on_color_selected(n))
                self.color_buttons[color_name] = btn
                
                # 在自定义按钮之前插入
                parent_layout = self.custom_color_btn.parent().layout()
                idx = parent_layout.indexOf(self.custom_color_btn)
                parent_layout.insertWidget(idx, btn)
            
            # 选中该颜色
            self.on_color_selected(color_name)
    
    def apply_background_color(self):
        """应用背景色到图片（支持渲染模式）"""
        if self.rgba_image is None:
            self.photo_frame.setText(tr("id_photo.no_photo"))
            return

        self.current_bg_color = self._normalize_bg_color(self.current_bg_color)
        self.current_render_mode = self._normalize_render_mode(self.current_render_mode)
        
        # 优先从自定义颜色获取，然后从默认颜色获取
        color_info = self.custom_colors.get(self.current_bg_color) or \
                     self.BG_COLORS.get(self.current_bg_color, self.BG_COLORS['white'])
        bg_color = color_info['bgr']
        
        # 根据渲染模式应用背景
        if self.current_render_mode in ['updown_gradient', 'center_gradient'] and self.id_photo_module:
            # 使用模块的渐变方法（官方算法）
            result = self._apply_gradient_background(self.rgba_image, bg_color, self.current_render_mode)
        else:
            # 纯色背景
            result = self._apply_solid_background(self.rgba_image, bg_color)
        
        # 保存到临时文件
        import tempfile
        fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='id_photo_preview_')
        os.close(fd)
        cv2.imwrite(temp_path, result)
        self.current_result_path = temp_path
        
        # 更新预览
        self._update_preview(result)
    
    def _apply_solid_background(self, img_rgba: np.ndarray, color: tuple) -> np.ndarray:
        """
        应用纯色背景（完全按照 HivisionIDPhotos 官方实现）
        参考：hivision/utils.py 的 add_background 函数
        """
        height, width = img_rgba.shape[:2]
        
        # 获取 RGBA 通道
        if img_rgba.shape[2] != 4:
            return img_rgba
        
        b, g, r, a = cv2.split(img_rgba)
        
        # Alpha 通道归一化（完全按照官方）
        a_cal = a / 255
        
        # 创建背景（注意：BGR 顺序）
        b2 = np.full([height, width], color[0], dtype=int)
        g2 = np.full([height, width], color[1], dtype=int)
        r2 = np.full([height, width], color[2], dtype=int)
        
        # 官方公式：(foreground - background) * alpha + background
        # 这个公式数学上等价于：foreground * alpha + background * (1 - alpha)
        output = cv2.merge(
            ((b - b2) * a_cal + b2, (g - g2) * a_cal + g2, (r - r2) * a_cal + r2)
        )
        
        return output.astype(np.uint8)
    
    def _apply_gradient_background(self, img_rgba: np.ndarray, start_color: tuple, render_mode: str) -> np.ndarray:
        """
        应用渐变背景（完全按照 HivisionIDPhotos 官方实现）
        参考：hivision/utils.py 的 generate_gradient 和 add_background
        """
        h, w = img_rgba.shape[:2]
        
        # 分离通道
        if img_rgba.shape[2] != 4:
            return img_rgba
        
        b, g, r, a = cv2.split(img_rgba)
        a_cal = a / 255.0
        
        end_color = (255, 255, 255)  # 白色
        
        if render_mode == 'updown_gradient':
            # 上下渐变（官方算法）
            r2 = np.zeros((h, w), dtype=np.float32)
            g2 = np.zeros((h, w), dtype=np.float32)
            b2 = np.zeros((h, w), dtype=np.float32)
            
            for y in range(h):
                ratio = y / h
                r2[y, :] = ratio * end_color[0] + (1 - ratio) * start_color[2]  # BGR->RGB
                g2[y, :] = ratio * end_color[1] + (1 - ratio) * start_color[1]
                b2[y, :] = ratio * end_color[2] + (1 - ratio) * start_color[0]  # BGR->RGB
        
        else:  # '中心渐变（白色）'
            # 中心渐变（官方算法）
            img_bg = np.zeros((h, w, 3), dtype=np.uint8)
            center = (w // 2, h // 2)
            end_axes = max(h, w)
            
            for y in range(end_axes):
                axes = (end_axes - y, end_axes - y)
                ratio = y / end_axes
                # BGR格式
                color_b = int(ratio * end_color[2] + (1 - ratio) * start_color[0])
                color_g = int(ratio * end_color[1] + (1 - ratio) * start_color[1])
                color_r = int(ratio * end_color[0] + (1 - ratio) * start_color[2])
                cv2.ellipse(img_bg, center, axes, 0, 0, 360, (color_b, color_g, color_r), -1)
            
            b2, g2, r2 = cv2.split(img_bg.astype(np.float32))
        
        # 官方混合公式：(foreground - background) * alpha + background
        output = cv2.merge([
            ((b - b2) * a_cal + b2).astype(np.uint8),
            ((g - g2) * a_cal + g2).astype(np.uint8),
            ((r - r2) * a_cal + r2).astype(np.uint8)
        ])
        
        return output
    
    def _update_preview(self, img: np.ndarray):
        """更新预览显示"""
        h, w = img.shape[:2]
        
        # 计算适合预览框的大小
        frame_size = self.photo_frame.size()
        max_w = frame_size.width() - 20
        max_h = frame_size.height() - 20
        
        if max_w <= 0 or max_h <= 0:
            max_w, max_h = 180, 260
        
        # 保持宽高比缩放
        scale = min(max_w / w, max_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 转换为QPixmap
        if len(resized.shape) == 3:
            bytes_per_line = 3 * new_w
            q_image = QImage(resized.data, new_w, new_h, bytes_per_line, QImage.Format.Format_BGR888)
        else:
            bytes_per_line = new_w
            q_image = QImage(resized.data, new_w, new_h, bytes_per_line, QImage.Format.Format_Grayscale8)
        
        pixmap = QPixmap.fromImage(q_image)
        self.photo_frame.setPixmap(pixmap)
    
    def on_photo_clicked(self, event):
        """点击照片查看大图"""
        if self.current_result_path and os.path.exists(self.current_result_path):
            self.show_fullscreen()
    
    def show_fullscreen(self):
        """显示大图窗口，支持切换背景色"""
        if self.rgba_image is None:
            return
        
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QPushButton, QWidget, QFileDialog
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap, QWheelEvent
        import shutil
        
        # 获取屏幕大小
        screen = self.screen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # 窗口大小：90%屏幕
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("id_photo.preview_title"))
        dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        dialog.setStyleSheet("background-color: hsl(222.2, 47.4%, 11.2%);")
        dialog.resize(window_width, window_height)
        dialog.move(
            (screen_width - window_width) // 2 + screen.x(),
            (screen_height - window_height) // 2 + screen.y()
        )
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 顶部工具栏
        toolbar = QWidget()
        toolbar.setFixedHeight(70)
        toolbar.setStyleSheet("""
            QWidget {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 12, 16, 12)
        toolbar_layout.setSpacing(12)
        
        # 背景色按钮
        color_label = QLabel(tr("id_photo.background_color"))
        color_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none;")
        toolbar_layout.addWidget(color_label)
        
        # 状态
        state = {
            'current_color': self.current_bg_color,
            'scale': 1.0,
            'min_scale': 0.5,
            'max_scale': 3.0,
            'rgba': self.rgba_image.copy(),
            'current_path': None
        }
        
        # 图片标签
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("background-color: hsl(217.2, 32.6%, 12%);")
        
        def update_image():
            # 支持自定义颜色
            color_info = self.custom_colors.get(state['current_color']) or \
                         self.BG_COLORS.get(state['current_color'], self.BG_COLORS['white'])
            bg_color = color_info['bgr']
            
            # 根据渲染模式应用背景
            if self.current_render_mode in ['updown_gradient', 'center_gradient']:
                result = self._apply_gradient_background(state['rgba'], bg_color, self.current_render_mode)
            else:
                result = self._apply_solid_background(state['rgba'], bg_color)
            
            # 应用水印（最后一步，确保水印在最终图像上）
            if hasattr(self, 'id_photo_module') and self.id_photo_module:
                watermark_params = self.id_photo_module.watermark_params
                if watermark_params.get('enabled', False):
                    # 将BGR图像转为RGBA格式（为水印添加alpha通道）
                    result_rgba = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
                    # 应用水印
                    result_rgba = self.id_photo_module._apply_watermark(result_rgba)
                    # 转回 BGR格式
                    result = cv2.cvtColor(result_rgba, cv2.COLOR_BGRA2BGR)
            
            # 保存到临时文件（支持中文路径）
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='id_photo_full_')
            os.close(fd)
            success, encoded = cv2.imencode('.png', result, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if success:
                with open(temp_path, 'wb') as f:
                    f.write(encoded.tobytes())
            state['current_path'] = temp_path
            
            # 获取原始尺寸（像素）和对应的毫米尺寸
            h, w = result.shape[:2]
            
            # 根据像素尺寸推断证件照规格（毫米）
            size_mm = self._get_size_mm(w, h)
            
            # 缩放显示
            scaled_w = int(w * state['scale'])
            scaled_h = int(h * state['scale'])
            
            resized = cv2.resize(result, (scaled_w, scaled_h), interpolation=cv2.INTER_LANCZOS4)
            
            # 创建带标注的预览图（仿照标准证件照预览样式）
            # 边距用于放置尺寸标注
            margin_top = 30
            margin_left = 50
            margin_right = 10
            margin_bottom = 10
            
            # 总画布大小
            canvas_w = scaled_w + margin_left + margin_right
            canvas_h = scaled_h + margin_top + margin_bottom
            
            # 创建画布（深色背景，配合深色主题）
            canvas = np.full((canvas_h, canvas_w, 3), (30, 35, 42), dtype=np.uint8)
            
            # 放置照片
            photo_x = margin_left
            photo_y = margin_top
            canvas[photo_y:photo_y + scaled_h, photo_x:photo_x + scaled_w] = resized
            
            # 照片细边框（浅色）
            cv2.rectangle(canvas, 
                         (photo_x - 1, photo_y - 1),
                         (photo_x + scaled_w, photo_y + scaled_h),
                         (200, 200, 200), 1)
            
            # 尺寸文字
            if size_mm:
                width_text = f"{size_mm[0]}mm"
                height_text = f"{size_mm[1]}mm"
            else:
                width_text = f"{w}px"
                height_text = f"{h}px"
            
            # 绘制标注线（浅灰色）
            line_color = (160, 160, 160)
            
            # 顶部横线
            line_y = margin_top - 10
            cv2.line(canvas, (photo_x, line_y), (photo_x + scaled_w, line_y), line_color, 1)
            # 两端小竖线
            cv2.line(canvas, (photo_x, line_y - 4), (photo_x, line_y + 4), line_color, 1)
            cv2.line(canvas, (photo_x + scaled_w, line_y - 4), (photo_x + scaled_w, line_y + 4), line_color, 1)
            
            # 左侧竖线
            line_x = margin_left - 10
            cv2.line(canvas, (line_x, photo_y), (line_x, photo_y + scaled_h), line_color, 1)
            # 两端小横线
            cv2.line(canvas, (line_x - 4, photo_y), (line_x + 4, photo_y), line_color, 1)
            cv2.line(canvas, (line_x - 4, photo_y + scaled_h), (line_x + 4, photo_y + scaled_h), line_color, 1)
            
            # 转换为QPixmap
            bytes_per_line = 3 * canvas_w
            q_image = QImage(canvas.data, canvas_w, canvas_h, bytes_per_line, QImage.Format.Format_BGR888)
            pixmap = QPixmap.fromImage(q_image)
            
            # 使用QPainter绘制清晰文字
            from PyQt6.QtGui import QPainter, QFont, QColor
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            # 设置字体（浅色，配合深色背景）
            text_font = QFont("Microsoft YaHei", 10)
            painter.setFont(text_font)
            painter.setPen(QColor(200, 200, 200))
            
            # 顶部宽度文字（居中，在横线上方）
            text_rect = painter.fontMetrics().boundingRect(width_text)
            text_x = photo_x + (scaled_w - text_rect.width()) // 2
            text_y = margin_top - 14
            painter.drawText(text_x, text_y, width_text)
            
            # 左侧高度文字（整体旋转90度，逆时针）
            painter.save()
            text_rect = painter.fontMetrics().boundingRect(height_text)
            # 移动到左侧中间位置，然后旋转
            center_x = (margin_left - 10) // 2
            center_y = photo_y + scaled_h // 2
            painter.translate(center_x, center_y)
            painter.rotate(-90)
            # 绘制文字（居中）
            painter.drawText(-text_rect.width() // 2, text_rect.height() // 3, height_text)
            painter.restore()
            
            painter.end()
            
            image_label.setPixmap(pixmap)
            image_label.setFixedSize(canvas_w, canvas_h)
            
            zoom_label.setText(f"{int(state['scale'] * 100)}%")
            
            # 动态显示/隐藏适应窗口按钮（只在图片大于窗口时显示）
            scroll_area_size = scroll_area.viewport().size()
            need_fit = (canvas_w > scroll_area_size.width() or canvas_h > scroll_area_size.height())
            btn_fit.setVisible(need_fit)
            zoom_label.setVisible(need_fit)
            if need_fit:
                toolbar_layout.addWidget(zoom_label)
                toolbar_layout.addWidget(btn_fit)
        
        def on_color_clicked(color_name):
            state['current_color'] = color_name
            # 更新按钮样式
            all_colors = {**self.BG_COLORS, **self.custom_colors}
            for name, btn in dialog_color_buttons.items():
                original_rgb = all_colors.get(name, {'rgb': '#FFFFFF'})['rgb']
                if name == color_name:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {original_rgb};
                            border: 2px solid hsl(142.1, 76.2%, 46.3%);
                            border-radius: 4px;
                        }}
                        QPushButton:hover {{
                            border-color: hsl(221.2, 83.2%, 53.3%);
                        }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {original_rgb};
                            border: 2px solid hsl(217.2, 32.6%, 25%);
                            border-radius: 4px;
                        }}
                        QPushButton:hover {{
                            border-color: hsl(221.2, 83.2%, 53.3%);
                        }}
                    """)
            color_name_label.setText(self._display_color_name(color_name))
            update_image()
        
        dialog_color_buttons = {}
        # 添加默认颜色按钮
        all_colors = {**self.BG_COLORS, **self.custom_colors}
        for name, colors in all_colors.items():
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(self._display_color_name(name))
            is_current = (name == state['current_color'])
            border_color = 'hsl(142.1, 76.2%, 46.3%)' if is_current else 'hsl(217.2, 32.6%, 25%)'
            border_width = '2px' if is_current else '2px'
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors['rgb']};
                    border: {border_width} solid {border_color};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }}
            """)
            btn.clicked.connect(lambda checked, n=name: on_color_clicked(n))
            dialog_color_buttons[name] = btn
            toolbar_layout.addWidget(btn)
        
        # 自定义颜色按钮
        def on_dialog_custom_color():
            from PyQt6.QtWidgets import QColorDialog, QDialog
            from PyQt6.QtGui import QColor as QC
            
            color_dialog = QColorDialog(dialog)
            color_dialog.setWindowTitle(tr("id_photo.background_color"))
            color_dialog.setCurrentColor(QC(255, 255, 255))
            # 设置中文界面
            color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
            
            # 美化样式
            color_dialog.setStyleSheet("""
                QColorDialog {
                    background-color: hsl(222.2, 84%, 4.9%);
                    color: hsl(213, 31%, 91%);
                }
                QLabel {
                    color: hsl(213, 31%, 91%);
                    font-size: 13px;
                }
                QPushButton {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: hsl(221.2, 83.2%, 53.3%);
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }
                QSpinBox, QLineEdit {
                    background-color: hsl(224, 71.4%, 4.1%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 4px;
                    padding: 6px;
                    color: hsl(213, 31%, 91%);
                }
                QSpinBox:focus, QLineEdit:focus {
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }
            """)
            
            # 翻译为中文
            translate_color_dialog_to_chinese(color_dialog)
            
            if color_dialog.exec() == QDialog.DialogCode.Accepted:
                color = color_dialog.currentColor()
                if color.isValid():
                    r, g, b = color.red(), color.green(), color.blue()
                    color_name = f"自定义#{r:02X}{g:02X}{b:02X}"
                    rgb_hex = f"#{r:02X}{g:02X}{b:02X}"
                    bgr = (b, g, r)
                
                # 添加到自定义颜色
                self.custom_colors[color_name] = {'bgr': bgr, 'rgb': rgb_hex}
                
                # 创建按钮
                if color_name not in dialog_color_buttons:
                    new_btn = QPushButton()
                    new_btn.setFixedSize(24, 24)
                    new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    new_btn.setToolTip(color_name)
                    new_btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {rgb_hex};
                            border: 2px solid hsl(217.2, 32.6%, 25%);
                            border-radius: 4px;
                        }}
                        QPushButton:hover {{
                            border-color: hsl(221.2, 83.2%, 53.3%);
                        }}
                    """)
                    new_btn.clicked.connect(lambda checked, n=color_name: on_color_clicked(n))
                    dialog_color_buttons[color_name] = new_btn
                    # 在自定义按钮前插入
                    idx = toolbar_layout.indexOf(dialog_custom_btn)
                    toolbar_layout.insertWidget(idx, new_btn)
                
                on_color_clicked(color_name)
        
        dialog_custom_btn = QPushButton("+")
        dialog_custom_btn.setFixedSize(24, 24)
        dialog_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dialog_custom_btn.setToolTip(tr("id_photo.custom_color"))
        dialog_custom_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #FF6B6B, stop:0.25 #4ECDC4, stop:0.5 #45B7D1, stop:0.75 #96E6A1, stop:1 #DDA0DD);
                border: 2px dashed hsl(217.2, 32.6%, 35%);
                border-radius: 4px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                border-color: hsl(221.2, 83.2%, 53.3%);
                border-style: solid;
            }
        """)
        dialog_custom_btn.clicked.connect(on_dialog_custom_color)
        toolbar_layout.addWidget(dialog_custom_btn)
        
        color_name_label = QLabel(tr("id_photo.current_color", color=self._display_color_name(state["current_color"])))
        color_name_label.setStyleSheet("color: hsl(213, 31%, 91%); background: transparent; border: none; margin-left: 8px;")
        toolbar_layout.addWidget(color_name_label)
        
        toolbar_layout.addStretch()
        
        # 缩放控制（只在需要时显示）
        zoom_label = QLabel("100%")
        zoom_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent; border: none;")
        
        # 适应窗口按钮（只在图片大于窗口时显示）
        btn_fit = QPushButton(tr("common.fit_window"))
        btn_fit.setStyleSheet("""
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: hsl(215, 27.9%, 22%);
            }
        """)
        
        # 先隐藏，等update_image中判断是否需要显示
        btn_fit.setVisible(False)
        zoom_label.setVisible(False)
        
        # 使用局部变量引用id_photo_module，避免在dialog内部访问self
        toolbar_layout.addStretch()
        
        # 排版打印按钮
        def open_print_layout():
            # 先检查授权码
            if not self._check_auth_code(dialog):
                return
            
            if state['current_path'] and os.path.exists(state['current_path']):
                # 获取当前设置
                print_params = None
                output_params = None
                output_types = None
                
                if hasattr(self, 'id_photo_module') and self.id_photo_module:
                    print_params = self.id_photo_module.print_params
                    output_params = self.id_photo_module.output_params
                    output_types = self.id_photo_module.output_types
                
                # 传入参数创建对话框
                print_dialog = PrintLayoutDialog(
                    state['current_path'], 
                    dialog,
                    print_params=print_params,
                    output_params=output_params,
                    output_types=output_types
                )
                print_dialog.exec()
        
        btn_print = QPushButton(tr("common.print_layout"))
        set_button_emoji_icon(btn_print, "🖨️")
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        btn_print.clicked.connect(open_print_layout)
        toolbar_layout.addWidget(btn_print)
        
        # 保存按钮（带文件大小控制）
        def save_image():
            # 先检查授权码
            if not self._check_auth_code(dialog):
                return
            
            if state['current_path'] and os.path.exists(state['current_path']):
                # 创建保存选项对话框
                save_dialog = QDialog(dialog)
                save_dialog.setWindowTitle(tr("save.id_photo_dialog_title"))
                save_dialog.setFixedSize(400, 200)
                save_dialog.setStyleSheet("background-color: hsl(222.2, 47.4%, 11.2%);")
                
                dlg_layout = QVBoxLayout(save_dialog)
                dlg_layout.setContentsMargins(20, 20, 20, 20)
                dlg_layout.setSpacing(15)
                
                # 文件大小限制选项
                size_row = QWidget()
                size_row.setStyleSheet("background: transparent;")
                size_layout = QHBoxLayout(size_row)
                size_layout.setContentsMargins(0, 0, 0, 0)
                
                size_check = QCheckBox(tr("save.limit_file_size"))
                size_check.setStyleSheet("color: hsl(213, 31%, 91%);")
                size_layout.addWidget(size_check)
                
                size_edit = QLineEdit("50")
                size_edit.setFixedWidth(60)
                size_edit.setEnabled(False)
                size_edit.setStyleSheet("""
                    QLineEdit {
                        background-color: hsl(224, 71.4%, 4.1%);
                        border: 1px solid hsl(217.2, 32.6%, 17.5%);
                        border-radius: 4px;
                        padding: 4px 8px;
                        color: hsl(213, 31%, 91%);
                    }
                    QLineEdit:disabled {
                        color: hsl(215, 20.2%, 45%);
                    }
                """)
                size_layout.addWidget(size_edit)
                
                kb_label = QLabel("KB")
                kb_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%);")
                size_layout.addWidget(kb_label)
                
                size_check.toggled.connect(size_edit.setEnabled)
                
                size_layout.addStretch()
                dlg_layout.addWidget(size_row)
                
                # 常用值快捷按钮
                preset_row = QWidget()
                preset_row.setStyleSheet("background: transparent;")
                preset_layout = QHBoxLayout(preset_row)
                preset_layout.setContentsMargins(0, 0, 0, 0)
                
                preset_label = QLabel(tr("save.common_sizes"))
                preset_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%);")
                preset_layout.addWidget(preset_label)
                
                for kb_val in [20, 50, 100, 200]:
                    preset_btn = QPushButton(f"{kb_val}KB")
                    preset_btn.setStyleSheet("""
                        QPushButton {
                            background-color: hsl(217.2, 32.6%, 17.5%);
                            color: hsl(213, 31%, 91%);
                            border: none;
                            border-radius: 4px;
                            padding: 4px 8px;
                        }
                        QPushButton:hover {
                            background-color: hsl(215, 27.9%, 22%);
                        }
                    """)
                    preset_btn.clicked.connect(lambda _, v=kb_val: (size_check.setChecked(True), size_edit.setText(str(v))))
                    preset_layout.addWidget(preset_btn)
                
                preset_layout.addStretch()
                dlg_layout.addWidget(preset_row)
                
                dlg_layout.addStretch()
                
                # 按钮
                btn_row = QWidget()
                btn_row.setStyleSheet("background: transparent;")
                btn_layout_dlg = QHBoxLayout(btn_row)
                btn_layout_dlg.setContentsMargins(0, 0, 0, 0)
                
                btn_cancel_dlg = QPushButton(tr("common.cancel"))
                btn_cancel_dlg.setStyleSheet("""
                    QPushButton {
                        background-color: hsl(217.2, 32.6%, 17.5%);
                        color: hsl(213, 31%, 91%);
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                    }
                    QPushButton:hover {
                        background-color: hsl(215, 27.9%, 22%);
                    }
                """)
                btn_cancel_dlg.clicked.connect(save_dialog.reject)
                btn_layout_dlg.addWidget(btn_cancel_dlg)
                
                btn_layout_dlg.addStretch()
                
                def do_save():
                    # 根据输出设置决定默认格式与筛选器
                    output_types = self.id_photo_module.output_types if (hasattr(self, 'id_photo_module') and self.id_photo_module) else {}
                    jpeg_format = self.id_photo_module.plugin_params.get('jpeg_format', False) if (hasattr(self, 'id_photo_module') and self.id_photo_module) else False
                    is_matting = output_types.get('matting_standard') or output_types.get('matting_hd')
                    
                    current_color = state['current_color']
                    color_en = current_color if current_color in self.BG_COLORS else 'custom'
                    
                    if is_matting:
                        default_name = f"id_photo_{color_en}.png"
                        file_filter = "PNG Files (*.png);;JPEG Files (*.jpg)"
                    elif jpeg_format:
                        default_name = f"id_photo_{color_en}.jpg"
                        file_filter = "JPEG Files (*.jpg);;PNG Files (*.png)"
                    else:
                        default_name = f"id_photo_{color_en}.png"
                        file_filter = "PNG Files (*.png);;JPEG Files (*.jpg)"
                    file_path, _ = QFileDialog.getSaveFileName(
                        save_dialog, tr("save.id_photo_dialog_title"), default_name, file_filter
                    )
                    if file_path:
                        try:
                            # 确保文件路径有扩展名
                            ext = os.path.splitext(file_path)[1].lower()
                            if not ext or ext not in ('.png', '.jpg', '.jpeg'):
                                # 根据当前情况添加默认扩展名
                                if is_matting:
                                    file_path = file_path + '.png'
                                elif jpeg_format:
                                    file_path = file_path + '.jpg'
                                else:
                                    file_path = file_path + '.png'
                            
                            # 确保目标目录存在
                            output_dir = os.path.dirname(file_path)
                            if output_dir and not os.path.exists(output_dir):
                                os.makedirs(output_dir, exist_ok=True)
                            
                            # 透明照：保存 RGBA（PNG）
                            if is_matting:
                                rgba = state.get('rgba')
                                if rgba is not None and rgba.shape[2] == 4:
                                    # 透明照必须是PNG格式
                                    if not file_path.lower().endswith('.png'):
                                        file_path = os.path.splitext(file_path)[0] + '.png'
                                    # 使用 imencode 支持中文路径
                                    success, encoded = cv2.imencode('.png', rgba, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                                    if success:
                                        with open(file_path, 'wb') as f:
                                            f.write(encoded.tobytes())
                                    actual_size = os.path.getsize(file_path) / 1024
                                    StyledMessageBox.success(save_dialog, tr("common.success"),
                                        tr("save.id_photo_saved_transparent", file_path=file_path, actual_size=actual_size))
                                    save_dialog.accept()
                                    return
                                StyledMessageBox.critical(save_dialog, tr("common.error"), tr("save.transparent_requires_rgba"))
                                return
                            # 读取当前图片（带背景 BGR），支持中文路径
                            if not state['current_path'] or not os.path.exists(state['current_path']):
                                StyledMessageBox.critical(save_dialog, tr("common.error"), tr("save.temp_file_missing"))
                                return
                            
                            from utils.image_utils import cv2_imread
                            img = cv2_imread(state['current_path'])
                            if img is None:
                                StyledMessageBox.critical(save_dialog, "错误", f"读取图片失败：{state['current_path']}")
                                return
                            
                            # 检查是否启用KB大小控制和DPI设置（从模块获取）
                            if hasattr(self, 'id_photo_module') and self.id_photo_module:
                                output_params = self.id_photo_module.output_params
                                kb_enabled = output_params.get('kb_enabled', False)
                                dpi_enabled = output_params.get('dpi_enabled', False)
                                target_kb = output_params.get('target_kb', 50)
                                dpi = output_params.get('dpi', 300)
                                kb_mode = output_params.get('kb_mode', 'max')
                                
                                # 如果启用了KB大小控制，使用官方算法
                                if kb_enabled:
                                    try:
                                        # 导入官方函数
                                        import sys
                                        hivision_path = 'D:/HivisionIDPhotos'
                                        if hivision_path not in sys.path:
                                            sys.path.insert(0, hivision_path)
                                        from hivision.utils import resize_image_to_kb
                                        
                                        # 使用官方resize_image_to_kb函数
                                        resize_image_to_kb(img, file_path, target_kb, dpi if dpi_enabled else 300)
                                        
                                        # 显示实际文件大小
                                        actual_size = os.path.getsize(file_path) / 1024
                                        StyledMessageBox.success(save_dialog, tr("common.success"), 
                                            tr("save.id_photo_saved_with_dpi", file_path=file_path, actual_size=actual_size, dpi=dpi if dpi_enabled else 300))
                                    except ImportError as ie:
                                        # 如果导入失败，使用备用方法
                                        from PIL import Image
                                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                        pil_img = Image.fromarray(img_rgb)
                                        
                                        # 调整质量以控制文件大小
                                        quality = 95
                                        while quality > 10:
                                            import io
                                            img_byte_arr = io.BytesIO()
                                            pil_img.save(img_byte_arr, format='JPEG', quality=quality, dpi=(dpi if dpi_enabled else 300, dpi if dpi_enabled else 300))
                                            size_kb = len(img_byte_arr.getvalue()) / 1024
                                            if size_kb <= target_kb:
                                                with open(file_path, 'wb') as f:
                                                    f.write(img_byte_arr.getvalue())
                                                break
                                            quality -= 5
                                        
                                        actual_size = os.path.getsize(file_path) / 1024
                                        StyledMessageBox.success(save_dialog, tr("common.success"), 
                                            tr("save.id_photo_saved_with_dpi_fallback", file_path=file_path, actual_size=actual_size, dpi=dpi if dpi_enabled else 300))
                                elif dpi_enabled:
                                    # 只设置DPI，不控制KB大小
                                    from PIL import Image
                                    # 转换BGR到RGB
                                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                    pil_img = Image.fromarray(img_rgb)
                                    pil_img.save(file_path, dpi=(dpi, dpi))
                                    
                                    actual_size = os.path.getsize(file_path) / 1024
                                    StyledMessageBox.success(save_dialog, tr("common.success"), 
                                        tr("save.id_photo_saved_with_dpi", file_path=file_path, actual_size=actual_size, dpi=dpi))
                                else:
                                    # 两者都未启用，使用默认保存（支持中文路径）
                                    ext = os.path.splitext(file_path)[1].lower()
                                    if ext in ['.jpg', '.jpeg']:
                                        success, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                                    else:
                                        success, encoded = cv2.imencode('.png', img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                                    
                                    if success:
                                        with open(file_path, 'wb') as f:
                                            f.write(encoded.tobytes())
                                    actual_size = os.path.getsize(file_path) / 1024
                                    StyledMessageBox.success(save_dialog, tr("common.success"), 
                                        tr("save.id_photo_saved", file_path=file_path, actual_size=actual_size))
                            else:
                                # 旧的KB控制逻辑（对话框中的）
                                max_kb = None
                                if size_check.isChecked():
                                    try:
                                        max_kb = int(size_edit.text())
                                    except ValueError:
                                        max_kb = 50
                                
                                save_with_size_limit(img, file_path, max_kb)
                                
                                # 显示实际文件大小
                                actual_size = os.path.getsize(file_path) / 1024
                                StyledMessageBox.success(save_dialog, tr("common.success"), 
                                    tr("save.id_photo_saved", file_path=file_path, actual_size=actual_size))
                            
                            save_dialog.accept()
                        except Exception as e:
                            StyledMessageBox.critical(save_dialog, "错误", f"保存失败：{str(e)}")
                
                btn_save_dlg = QPushButton(tr("common.save"))
                btn_save_dlg.setStyleSheet("""
                    QPushButton {
                        background-color: hsl(142.1, 76.2%, 36.3%);
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: hsl(142.1, 76.2%, 42%);
                    }
                """)
                btn_save_dlg.clicked.connect(do_save)
                btn_layout_dlg.addWidget(btn_save_dlg)
                
                dlg_layout.addWidget(btn_row)
                
                save_dialog.exec()
        
        btn_save = QPushButton(tr("common.save"))
        set_button_emoji_icon(btn_save, "💾")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: hsl(142.1, 76.2%, 36.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: hsl(142.1, 76.2%, 42%);
            }
        """)
        btn_save.clicked.connect(save_image)
        toolbar_layout.addWidget(btn_save)
        
        btn_close = QPushButton(tr("common.close"))
        set_button_emoji_icon(btn_close, "❌")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: hsl(0, 62.8%, 30.6%);
            }
        """)
        btn_close.clicked.connect(dialog.close)
        toolbar_layout.addWidget(btn_close)
        
        layout.addWidget(toolbar)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(False)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_area.setStyleSheet("""
            QScrollArea { border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 8px; background-color: hsl(217.2, 32.6%, 12%); }
            QScrollBar:vertical { background-color: hsl(217.2, 32.6%, 17.5%); width: 12px; border-radius: 6px; }
            QScrollBar::handle:vertical { background-color: hsl(215, 20.2%, 65.1%); border-radius: 6px; min-height: 30px; }
            QScrollBar:horizontal { background-color: hsl(217.2, 32.6%, 17.5%); height: 12px; border-radius: 6px; }
            QScrollBar::handle:horizontal { background-color: hsl(215, 20.2%, 65.1%); border-radius: 6px; min-width: 30px; }
        """)
        scroll_area.setWidget(image_label)
        layout.addWidget(scroll_area, stretch=1)
        
        # 滚轮缩放
        def on_wheel(event: QWheelEvent):
            delta = event.angleDelta().y()
            if delta > 0:
                state['scale'] = min(state['scale'] * 1.15, state['max_scale'])
            else:
                state['scale'] = max(state['scale'] / 1.15, state['min_scale'])
            update_image()
        
        scroll_area.wheelEvent = on_wheel
        
        def fit_to_window():
            viewport = scroll_area.viewport()
            vw, vh = viewport.width() - 20, viewport.height() - 20
            img_h, img_w = state['rgba'].shape[:2]
            scale_w = vw / img_w
            scale_h = vh / img_h
            state['scale'] = min(scale_w, scale_h, 1.0)
            update_image()
        
        btn_fit.clicked.connect(fit_to_window)
        
        # ESC关闭
        def keyPressEvent(event):
            if event.key() == Qt.Key.Key_Escape:
                dialog.close()
            else:
                QDialog.keyPressEvent(dialog, event)
        dialog.keyPressEvent = keyPressEvent
        
        # 显示后适应窗口
        def on_shown():
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, fit_to_window)
        
        dialog.showEvent = lambda e: on_shown()
        dialog.exec()
        
        # 更新主预览的背景色
        self.current_bg_color = state['current_color']
        self.apply_background_color()
        # 更新主界面的颜色按钮状态
        for name, btn in self.color_buttons.items():
            btn.setChecked(name == state['current_color'])
        self.color_name_label.setText(self._display_color_name(state['current_color']))
    
    def get_current_result_path(self) -> str:
        """获取当前背景色应用后的图片路径"""
        return self.current_result_path
    
    def resizeEvent(self, event):
        """窗口大小改变时重新更新预览"""
        super().resizeEvent(event)
        if self.rgba_image is not None:
            self.apply_background_color()
    
    def _check_auth_code(self, parent_dialog=None) -> bool:
        """
        检查是否需要授权码，如果需要则弹出输入框
        
        返回:
            True: 授权通过或无需授权
            False: 授权失败或用户取消
        """
        # 每次都实时检查，不使用缓存
        try:
            from utils.auth_code import get_machine_code, check_need_auth_code, valid_auth_code
            from utils.config import SOFT_NUMBER
            from ui.auth_code_dialog import AuthCodeDialog
            
            # 1. 获取机器码
            machine_code = get_machine_code()
            
            # 2. 实时检查是否需要授权码（每次都调用API）
            need_auth, auth_url, error_msg = check_need_auth_code(machine_code, SOFT_NUMBER)
            
            if error_msg:
                # 网络错误或API错误，提示用户但不阻止操作
                from ui.custom_widgets import StyledMessageBox
                StyledMessageBox.warning(
                    parent_dialog or self,
                    tr("auth.check_failed_title"),
                    tr("auth.check_failed_continue", error=error_msg)
                )
                return True
            
            if not need_auth:
                # 无需授权码（已有有效授权）
                return True
            
            # 3. 需要授权码，循环弹出输入框直到验证成功或用户取消
            while True:
                auth_dialog = AuthCodeDialog(auth_url, parent_dialog or self)
                if auth_dialog.exec() != AuthCodeDialog.DialogCode.Accepted:
                    # 用户取消
                    return False
                
                # 4. 验证授权码
                auth_code = auth_dialog.get_auth_code()
                is_valid, error_msg = valid_auth_code(machine_code, SOFT_NUMBER, auth_code)
                
                if is_valid:
                    # 授权成功，退出循环
                    return True
                else:
                    # 授权码无效，显示错误提示，然后继续循环（重新弹出输入框）
                    from ui.custom_widgets import StyledMessageBox
                    StyledMessageBox.critical(
                        parent_dialog or self,
                        tr("auth.verify_failed_title"),
                        error_msg or tr("auth.invalid_code"),
                    )
                    # 继续循环，重新弹出授权码输入框
            
        except ImportError as e:
            # 缺少依赖模块，提示但不阻止
            from ui.custom_widgets import StyledMessageBox
            StyledMessageBox.warning(
                parent_dialog or self,
                tr("common.tip"),
                tr("auth.module_load_failed", error=str(e))
            )
            return True
        except Exception as e:
            # ???????????
            from ui.custom_widgets import StyledMessageBox
            StyledMessageBox.warning(
                parent_dialog or self,
                tr("common.tip"),
                tr("auth.check_failed_continue", error=str(e))
            )
            return True
