"""授权码验证工具 - 根据 example/get_auth_code_demo.py 实现"""
import hashlib
import platform
import subprocess
import uuid
from typing import Optional, Tuple
import webbrowser
import requests


# API配置
API_BASE_URL = 'https://api-web.kunqiongai.com'

# 从配置文件导入软件编号
try:
    from utils.config import SOFT_NUMBER
except ImportError:
    SOFT_NUMBER = ''  # 默认值


def get_cpu_info() -> Optional[str]:
    """获取CPU序列号（不同系统命令不同）"""
    system = platform.system()
    cpu_serial = None
    try:
        if system == "Windows":
            # Windows系统获取CPU序列号
            result = subprocess.check_output(
                'wmic cpu get ProcessorId',
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL
            )
            # 解析输出，提取序列号
            lines = result.strip().split('\n')
            if len(lines) >= 2:
                cpu_serial = lines[1].strip()
        elif system == "Linux":
            # Linux系统读取CPU信息
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('processor'):
                        continue
                    if line.startswith('serial'):
                        cpu_serial = line.split(':')[1].strip()
                        break
        elif system == "Darwin":  # macOS
            result = subprocess.check_output(
                'sysctl -n machdep.cpu.core_count',
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL
            )
            # macOS获取CPU标识的替代方案
            cpu_serial = result.strip()
    except Exception:
        pass
    return cpu_serial


def get_mac_address() -> str:
    """获取网卡MAC地址（优先获取物理网卡）"""
    # 获取所有网卡的MAC地址，取第一个非虚拟网卡的地址
    mac_num = hex(uuid.getnode()).replace('0x', '').upper()
    mac = '-'.join([mac_num[i:i+2] for i in range(0, 11, 2)])
    return mac


def get_machine_code() -> str:
    """生成唯一机器码（组合CPU+MAC+主板信息）"""
    # 收集多个硬件标识
    hardware_infos = []
    
    # 1. CPU序列号
    cpu_info = get_cpu_info()
    if cpu_info:
        hardware_infos.append(cpu_info)
    
    # 2. MAC地址
    mac_info = get_mac_address()
    hardware_infos.append(mac_info)
    
    # 3. 主板序列号（Windows）
    system = platform.system()
    if system == "Windows":
        try:
            result = subprocess.check_output(
                'wmic baseboard get SerialNumber',
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL
            )
            lines = result.strip().split('\n')
            if len(lines) >= 2:
                board_serial = lines[1].strip()
                if board_serial:
                    hardware_infos.append(board_serial)
        except Exception:
            pass
    
    # 组合所有信息并哈希
    combined = '|'.join(hardware_infos)
    # 使用SHA256生成固定长度的唯一码
    machine_code = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    return machine_code


def check_need_auth_code(machine_code: str, soft_number: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    请求检查是否需要获取授权码
    
    返回:
        (需要授权码, 获取授权码URL, 错误消息)
    """
    try:
        check_url = API_BASE_URL + "/soft_desktop/check_get_auth_code"
        # Body请求参数（urlencoded）
        data = {
            "device_id": machine_code,
            "soft_number": soft_number
        }
        response = requests.post(check_url, data=data, timeout=10)
        result = response.json()
        
        if result["code"] == 1:
            if result["data"]["is_need_auth_code"] == 1:
                # 需要授权码，返回获取URL
                auth_code_url = f"{result['data']['auth_code_url']}?device_id={machine_code}&software_code={soft_number}"
                return True, auth_code_url, None
            else:
                # 无需授权码
                return False, None, None
        else:
            # API返回错误
            return False, None, result.get('msg', '检查授权码状态失败')
    except requests.exceptions.Timeout:
        return False, None, "网络请求超时，请检查网络连接"
    except requests.exceptions.RequestException as e:
        return False, None, f"网络请求失败：{str(e)}"
    except Exception as e:
        return False, None, f"检查授权码失败：{str(e)}"


def valid_auth_code(machine_code: str, soft_number: str, auth_code: str) -> Tuple[bool, Optional[str]]:
    """
    验证授权码
    
    返回:
        (验证是否成功, 错误消息)
    """
    try:
        check_url = API_BASE_URL + "/soft_desktop/check_auth_code_valid"
        # Body请求参数（urlencoded）
        data = {
            "device_id": machine_code,
            "soft_number": soft_number,
            'auth_code': auth_code
        }
        response = requests.post(check_url, data=data, timeout=10)
        result = response.json()
        
        if result["code"] == 1:
            if result["data"]["auth_code_status"] == 1:
                # 授权码有效
                return True, None
            else:
                # 授权码无效
                return False, "授权码无效，请重新获取"
        else:
            # API返回错误
            return False, result.get('msg', '验证授权码失败')
    except requests.exceptions.Timeout:
        return False, "网络请求超时，请检查网络连接"
    except requests.exceptions.RequestException as e:
        return False, f"网络请求失败：{str(e)}"
    except Exception as e:
        return False, f"验证授权码失败：{str(e)}"


# def open_auth_code_url(auth_code_url: str):
#     """打开浏览器到授权码获取页面"""
#     try:
#         webbrowser.open(auth_code_url)
#         return True
#     except Exception:
#         return False

def open_auth_code_url(auth_code_url: str):
    """
    打开浏览器到授权码获取页面（使用ShellExecute，减少360拦截）
    
    使用多重 fallback 方案：
    1. ShellExecute (Windows) - 最安全，360基本不拦截
    2. webbrowser.open() - 跨平台备用
    3. os.startfile/open/xdg-open - 系统默认方式
    4. 复制到剪贴板 - 最后备用方案
    """
    success = False
    system = platform.system()
    
    # Windows系统：优先使用ShellExecute API
    if system == "Windows":
        
        try:
            import ctypes
            
            # 加载shell32.dll
            shell32 = ctypes.windll.shell32
            
            # SW_SHOWNORMAL = 1 (正常显示窗口)
            SW_SHOWNORMAL = 1
            
            # 调用ShellExecuteW (Unicode版本)
            # 返回值 > 32 表示成功
            result = shell32.ShellExecuteW(
                None,                    # hwnd: 父窗口句柄
                "open",                  # lpOperation: 操作类型
                auth_code_url,           # lpFile: 要打开的URL
                None,                    # lpParameters: 参数
                None,                    # lpDirectory: 工作目录
                SW_SHOWNORMAL            # nShowCmd: 显示方式
            )
            
            # 检查返回值
            if result > 32:
                success = True
                return True
            
        except Exception:
            # ShellExecute失败，继续尝试其他方案
            pass
    
    # 方案2：使用webbrowser模块（跨平台）
    if not success:
        try:
            webbrowser.open(auth_code_url)
            success = True
            return True
        except Exception:
            pass
    
    # 方案3：系统默认方式
    if not success:
        try:
            import os
            if system == "Windows":
                # Windows: 使用 os.startfile
                os.startfile(auth_code_url)
                success = True
            elif system == "Darwin":  # macOS
                subprocess.run(['open', auth_code_url], check=False, stderr=subprocess.DEVNULL)
                success = True
            else:  # Linux
                subprocess.run(['xdg-open', auth_code_url], check=False, stderr=subprocess.DEVNULL)
                success = True
            
            if success:
                return True
        except Exception:
            pass
    
    # 方案4（最后备用）：复制链接到剪贴板
    try:
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(auth_code_url)
        # 返回 False 让调用者知道需要提示用户手动粘贴
        return False
    except Exception:
        return False
