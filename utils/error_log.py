# -*- coding: utf-8 -*-
"""统一错误日志：记录详细错误信息（含堆栈、位置），便于排查"""
import os
import sys
import traceback
from datetime import datetime

_LOG_FILE = None


def get_log_file_path():
    """返回当前使用的错误日志文件路径（打包后为 exe 同目录）"""
    global _LOG_FILE
    if _LOG_FILE is not None:
        return _LOG_FILE
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        _LOG_FILE = os.path.join(exe_dir, "鲲穹AI证件照_error.log")
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _LOG_FILE = os.path.join(base, "app_error.log")
    return _LOG_FILE


def log_error(message, exc_info=None, location=None):
    """
    写入一条错误日志（含时间、位置、消息、可选堆栈）。
    location: 如 "ui.main_window._run_direct" 或 "modules.id_photo.process"
    """
    path = get_log_file_path()
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 错误\n")
            if location:
                f.write(f"位置: {location}\n")
            f.write(f"消息: {message}\n")
            if exc_info is not None:
                if isinstance(exc_info, BaseException):
                    f.write("堆栈:\n")
                    f.write(traceback.format_exc())
                elif isinstance(exc_info, tuple):
                    f.write("堆栈:\n")
                    f.write(''.join(traceback.format_exception(*exc_info)))
                else:
                    f.write(f"堆栈:\n{exc_info}\n")
            elif sys.exc_info()[0] is not None:
                f.write("堆栈:\n")
                f.write(traceback.format_exc())
            f.write("=" * 60 + "\n")
    except Exception:
        pass
    return path


def get_error_log_tip():
    """返回给用户看的日志路径提示"""
    return f"详细日志已保存到:\n{get_log_file_path()}"
