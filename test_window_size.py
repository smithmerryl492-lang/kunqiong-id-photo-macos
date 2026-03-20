"""测试窗口尺寸配置"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT

print("=" * 50)
print("窗口尺寸配置测试")
print("=" * 50)
print(f"WINDOW_MIN_WIDTH = {WINDOW_MIN_WIDTH}")
print(f"WINDOW_MIN_HEIGHT = {WINDOW_MIN_HEIGHT}")
print("=" * 50)

if WINDOW_MIN_WIDTH == 1200 and WINDOW_MIN_HEIGHT == 900:
    print("✓ 配置正确!")
else:
    print("✗ 配置不正确!")
    print(f"  期望: 1200 x 900")
    print(f"  实际: {WINDOW_MIN_WIDTH} x {WINDOW_MIN_HEIGHT}")
