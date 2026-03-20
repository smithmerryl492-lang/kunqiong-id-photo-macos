"""证件照独立版 - 主程序入口"""
import sys
import os
import ssl
import warnings
import traceback
import logging
from datetime import datetime

# 全局未捕获异常写入统一错误日志
def _excepthook(etype, value, tb):
    try:
        from utils.error_log import log_error, get_error_log_tip
        log_error(str(value), (etype, value, tb), location="sys.excepthook")
    except Exception:
        pass
    if _excepthook._original:
        _excepthook._original(etype, value, tb)
_excepthook._original = sys.excepthook
sys.excepthook = _excepthook

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TQDM_DISABLE"] = "1"
warnings.filterwarnings("ignore")

# 模型路径（必须在 import rembg 之前）
def _get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(base_path, relative_path))
    if os.path.exists(path):
        return path
    internal = os.path.normpath(os.path.join(os.path.dirname(sys.executable), "_internal", relative_path))
    if os.path.exists(internal):
        return internal
    return path

_model_dir = _get_resource_path("models")
_u2net_dir = os.path.join(_model_dir, "u2net")
os.environ["U2NET_HOME"] = _u2net_dir

# 日志
def setup_logging():
    if getattr(sys, 'frozen', False):
        logging.disable(logging.CRITICAL)
        return None
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, "app_error.log")
    if os.path.exists(log_file) and os.path.getsize(log_file) > 10 * 1024 * 1024:
        open(log_file, 'w').close()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.FileHandler(log_file, encoding='utf-8', mode='a')]
    )
    return log_file

LOG_FILE = setup_logging()
logger = logging.getLogger(__name__)

def main():
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor

        logger.info("初始化 QApplication...")
        app = QApplication(sys.argv)

        def load_module(msg, import_func):
            logger.info(msg)
            try:
                return import_func()
            except Exception as e:
                logger.error(f"  -> 失败: {e}")
                logger.error(traceback.format_exc())
                try:
                    from utils.error_log import log_error
                    log_error(str(e), sys.exc_info(), location="main.load_module")
                except Exception:
                    pass
                raise

        MainWindow = load_module("正在初始化界面", lambda: __import__('ui.main_window', fromlist=['MainWindow']).MainWindow)
        IDPhotoModule = load_module("正在加载AI证件照模型", lambda: __import__('modules.id_photo', fromlist=['IDPhotoModule']).IDPhotoModule)

        modules = [IDPhotoModule()]
        window = MainWindow(modules)
        window.show()
        logger.info("主窗口已显示")
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        logger.error(traceback.format_exc())
        try:
            from utils.error_log import log_error, get_error_log_tip
            log_error(str(e), sys.exc_info(), location="main.main")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "启动失败", f"程序启动失败:\n{e}\n\n{get_error_log_tip()}")
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()
