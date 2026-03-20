"""测试消息提示框样式"""
import sys
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from ui.custom_widgets import StyledMessageBox


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("测试提示框样式")
        self.setGeometry(100, 100, 400, 300)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 信息提示
        btn_info = QPushButton("信息提示")
        btn_info.clicked.connect(lambda: StyledMessageBox.information(
            self, "提示", "这是一条信息提示"
        ))
        layout.addWidget(btn_info)
        
        # 成功提示
        btn_success = QPushButton("成功提示")
        btn_success.clicked.connect(lambda: StyledMessageBox.success(
            self, "成功", "操作成功！"
        ))
        layout.addWidget(btn_success)
        
        # 警告提示
        btn_warning = QPushButton("警告提示")
        btn_warning.clicked.connect(lambda: StyledMessageBox.warning(
            self, "检查授权码失败", "网络连接失败\n\n将继续保存操作"
        ))
        layout.addWidget(btn_warning)
        
        # 错误提示
        btn_error = QPushButton("错误提示")
        btn_error.clicked.connect(lambda: StyledMessageBox.critical(
            self, "授权码验证失败", "授权码无效，请重新获取"
        ))
        layout.addWidget(btn_error)
        
        # 输入提示
        btn_input = QPushButton("输入提示")
        btn_input.clicked.connect(lambda: StyledMessageBox.warning(
            self, "提示", "请输入授权码"
        ))
        layout.addWidget(btn_input)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
