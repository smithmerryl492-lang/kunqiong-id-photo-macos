"""测试授权码对话框界面"""
import sys
from PyQt6.QtWidgets import QApplication
from ui.auth_code_dialog import AuthCodeDialog


def main():
    """主测试函数"""
    app = QApplication(sys.argv)
    
    # 创建测试用的授权码URL
    test_url = "https://www.kunqiongai.com/auth?device_id=test123&software_code=10019"
    
    # 显示对话框
    dialog = AuthCodeDialog(test_url)
    result = dialog.exec()
    
    if result == AuthCodeDialog.DialogCode.Accepted:
        auth_code = dialog.get_auth_code()
        print(f"✓ 用户输入的授权码: {auth_code}")
    else:
        print("✗ 用户取消了输入")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
