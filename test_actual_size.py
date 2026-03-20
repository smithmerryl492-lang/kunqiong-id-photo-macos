"""测试实际窗口尺寸"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow

# 导入配置
from utils.config import WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT

print("=" * 60)
print("测试窗口尺寸配置")
print("=" * 60)
print(f"配置中的值:")
print(f"  WINDOW_MIN_WIDTH  = {WINDOW_MIN_WIDTH}")
print(f"  WINDOW_MIN_HEIGHT = {WINDOW_MIN_HEIGHT}")
print("=" * 60)

# 创建测试窗口
app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowTitle("测试窗口尺寸")
window.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
window.resize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

print(f"窗口设置后的实际尺寸:")
print(f"  宽度 = {window.width()}")
print(f"  高度 = {window.height()}")
print("=" * 60)

if window.width() == WINDOW_MIN_WIDTH and window.height() == WINDOW_MIN_HEIGHT:
    print("✓ 窗口尺寸设置正确!")
else:
    print("✗ 窗口尺寸不匹配!")
print("=" * 60)

window.show()
sys.exit(app.exec())
