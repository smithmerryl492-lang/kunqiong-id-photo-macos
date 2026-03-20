"""Tailwind CSS + Shadcn UI 风格样式系统"""

# Tailwind + Shadcn UI 配色方案（深色模式）
# 基于 Tailwind zinc/slate 和 Shadcn 设计系统

TAILWIND_SHADCN_STYLESHEET = """
/* ========================================
   Tailwind CSS + Shadcn UI Design System
   ======================================== */

/* 全局字体 - Inter/SF Pro 风格 */
QWidget {
    font-family: 'Inter', 'SF Pro Display', -apple-system, 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
    font-size: 14px;
}

/* 主窗口 - Shadcn 深色背景 */
QMainWindow {
    background-color: hsl(222.2, 47.4%, 11.2%);
    color: hsl(213, 31%, 91%);
}

/* 基础背景和前景色 */
QWidget {
    background-color: hsl(222.2, 47.4%, 11.2%);
    color: hsl(213, 31%, 91%);
}

/* 卡片背景 - Shadcn card */
QWidget[class="card"] {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 8px;
}

/* 工具栏 */
QWidget#editor_toolbar {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 8px;
    padding: 8px;
}

/* 分隔线 */
QFrame[class="separator"] {
    background-color: hsl(217.2, 32.6%, 17.5%);
    min-width: 1px;
    max-width: 1px;
    margin: 4px 8px;
}

/* 柔和文本 */
QLabel[class="muted"] {
    color: hsl(215, 20.2%, 65.1%);
    font-size: 13px;
}

/* ========================================
   按钮样式 - Shadcn Button
   ======================================== */

/* 默认按钮 - Primary */
QPushButton {
    background-color: hsl(221.2, 83.2%, 53.3%);
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 14px;
    min-height: 36px;
}

QPushButton:hover {
    background-color: hsl(217.2, 91.2%, 59.8%);
}

QPushButton:pressed {
    background-color: hsl(224.3, 76.3%, 48%);
}

QPushButton:disabled {
    background-color: hsl(217.2, 32.6%, 17.5%);
    color: hsl(215, 20.2%, 65.1%);
    opacity: 0.5;
}

/* 次要按钮 - Secondary */
QPushButton[class="secondary"] {
    background-color: hsl(217.2, 32.6%, 17.5%);
    color: hsl(213, 31%, 91%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
}

QPushButton[class="secondary"]:hover {
    background-color: hsl(215, 27.9%, 16.9%);
    border-color: hsl(215, 20.2%, 65.1%);
}

/* Outline 按钮 */
QPushButton[class="outline"] {
    background-color: transparent;
    color: hsl(213, 31%, 91%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
}

QPushButton[class="outline"]:hover {
    background-color: hsl(217.2, 32.6%, 17.5%);
    border-color: hsl(215, 20.2%, 65.1%);
}

/* Ghost 按钮 - 图标按钮 */
QPushButton[class="ghost"] {
    background-color: transparent;
    color: hsl(213, 31%, 91%);
    border: none;
    padding: 6px 12px;
}

QPushButton[class="ghost"]:hover {
    background-color: hsl(217.2, 32.6%, 17.5%);
}

/* 破坏性按钮 */
QPushButton[class="destructive"] {
    background-color: hsl(0, 72.2%, 50.6%);
    color: white;
}

QPushButton[class="destructive"]:hover {
    background-color: hsl(0, 72.2%, 45%);
}

/* 图标按钮 - 工具栏 */
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

QPushButton[class="icon-button"]:pressed {
    background-color: hsl(215, 27.9%, 16.9%);
}

/* 主要操作按钮 */
QPushButton#btn_process {
    background-color: hsl(221.2, 83.2%, 53.3%);
    color: white;
    font-weight: 600;
    font-size: 15px;
    padding: 10px 24px;
    min-height: 44px;
}

QPushButton#btn_process:hover {
    background-color: hsl(217.2, 91.2%, 59.8%);
}

/* ========================================
   输入控件 - Shadcn Input
   ======================================== */

QLineEdit, QTextEdit, QComboBox {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 6px;
    padding: 8px 12px;
    color: hsl(213, 31%, 91%);
    font-size: 14px;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 2px solid hsl(221.2, 83.2%, 53.3%);
    outline: none;
}

QLineEdit:hover, QTextEdit:hover, QComboBox:hover {
    border-color: hsl(215, 20.2%, 65.1%);
}

QComboBox {
    padding-right: 30px;
    min-height: 20px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 25px;
    border: none;
    border-left: 1px solid hsl(217.2, 32.6%, 17.5%);
    background: hsl(217.2, 32.6%, 17.5%);
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}

QComboBox::drop-down:hover {
    background: hsl(221.2, 83.2%, 53.3%);
}

/* 箭头由自定义控件 StyledComboBox 绘制 */
QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 6px;
    selection-background-color: hsl(221.2, 83.2%, 53.3%);
    selection-color: white;
    color: hsl(213, 31%, 91%);
    padding: 4px;
}

/* ========================================
   数字调节框 - QSpinBox / QDoubleSpinBox
   ======================================== */

QSpinBox, QDoubleSpinBox {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 6px;
    padding: 6px 10px;
    padding-right: 25px;
    color: hsl(213, 31%, 91%);
    font-size: 14px;
    min-width: 80px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid hsl(221.2, 83.2%, 53.3%);
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: hsl(215, 20.2%, 65.1%);
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 50%;
    border-left: 1px solid hsl(217.2, 32.6%, 17.5%);
    border: none;
    border-top-right-radius: 5px;
    background-color: hsl(217.2, 32.6%, 17.5%);
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: hsl(221.2, 83.2%, 53.3%);
}

/* 箭头由自定义控件 StyledSpinBox 绘制 */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    width: 0;
    height: 0;
    border: none;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 50%;
    border: none;
    border-bottom-right-radius: 5px;
    background-color: hsl(217.2, 32.6%, 17.5%);
}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: hsl(221.2, 83.2%, 53.3%);
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border: none;
}

/* ========================================
   滑块 - Shadcn Slider
   ======================================== */

QSlider {
    background: transparent;
    min-height: 20px;
    max-height: 20px;
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: hsl(215, 20%, 30%);
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
    background: hsl(217.2, 91.2%, 59.8%);
}

QSlider::handle:horizontal:pressed {
    background: hsl(224.3, 76.3%, 48%);
}

QSlider::sub-page:horizontal {
    background: hsl(221.2, 83.2%, 53.3%);
    height: 4px;
    border-radius: 2px;
}

QSlider::add-page:horizontal {
    background: hsl(215, 20%, 30%);
    height: 4px;
    border-radius: 2px;
}

/* 可选中按钮（如笔刷/移动切换） */
QPushButton:checked {
    background-color: hsl(217.2, 32.6%, 17.5%);
    color: hsl(215, 20.2%, 65.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
}

QPushButton:checked:hover {
    background-color: hsl(215, 27.9%, 22%);
}

/* ========================================
   标签页 - Shadcn Tabs
   ======================================== */

QTabWidget::pane {
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 8px;
    background-color: hsl(224, 71.4%, 4.1%);
    top: -1px;
}

QTabBar::tab {
    background: hsl(217.2, 32.6%, 17.5%);
    color: hsl(215, 20.2%, 65.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 6px;
    padding: 8px 14px;
    margin-right: 4px;
    font-weight: 500;
    font-size: 13px;
}

QTabBar::tab:selected {
    background: hsl(221.2, 83.2%, 53.3%);
    color: white;
    border-color: hsl(221.2, 83.2%, 53.3%);
}

QTabBar::tab:hover {
    color: hsl(213, 31%, 91%);
    background-color: hsl(215, 27.9%, 22%);
}

/* ========================================
   进度条 - Shadcn Progress
   ======================================== */

QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: hsl(217.2, 32.6%, 17.5%);
    height: 8px;
    text-align: center;
    color: hsl(213, 31%, 91%);
}

QProgressBar::chunk {
    background-color: hsl(221.2, 83.2%, 53.3%);
    border-radius: 4px;
}

/* ========================================
   滚动条 - Shadcn Scrollbar
   ======================================== */

QScrollBar:vertical, QScrollBar:horizontal {
    border: none;
    background: transparent;
    width: 12px;
    height: 12px;
    margin: 0;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: hsl(217.2, 32.6%, 17.5%);
    min-height: 30px;
    min-width: 30px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: hsl(215, 20.2%, 65.1%);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0;
    width: 0;
}

/* ========================================
   标签 - Shadcn Label
   ======================================== */

QLabel {
    color: hsl(213, 31%, 91%);
    font-size: 14px;
}

QLabel[class="muted"] {
    color: hsl(215, 20.2%, 65.1%);
    font-size: 13px;
}

QLabel[class="heading"] {
    font-weight: 600;
    font-size: 18px;
}

QLabel[class="subheading"] {
    font-weight: 500;
    font-size: 16px;
}

/* ========================================
   分割线 - Shadcn Separator
   ======================================== */

QFrame[class="separator"] {
    background-color: hsl(217.2, 32.6%, 17.5%);
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QFrame[class="separator-vertical"] {
    background-color: hsl(217.2, 32.6%, 17.5%);
    border: none;
    min-width: 1px;
    max-width: 1px;
}

/* ========================================
   工具栏 - Shadcn Toolbar
   ======================================== */

QWidget[class="toolbar"] {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 8px;
    padding: 8px;
}

/* ========================================
   卡片 - Shadcn Card
   ======================================== */

QWidget[class="card"] {
    background-color: hsl(224, 71.4%, 4.1%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 8px;
    padding: 16px;
}

/* ========================================
   图片显示区域
   ======================================== */

QLabel[class="image-container"] {
    background-color: hsl(222.2, 47.4%, 11.2%);
    border: 1px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 8px;
}

/* ========================================
   复选框 - Shadcn Checkbox
   ======================================== */

QCheckBox {
    color: hsl(213, 31%, 91%);
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid hsl(217.2, 32.6%, 17.5%);
    border-radius: 4px;
    background-color: hsl(224, 71.4%, 4.1%);
}

QCheckBox::indicator:hover {
    border-color: hsl(215, 20.2%, 65.1%);
}

QCheckBox::indicator:checked {
    background-color: hsl(221.2, 83.2%, 53.3%);
    border-color: hsl(221.2, 83.2%, 53.3%);
}
"""
