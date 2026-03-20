import hashlib
import platform
import subprocess
import uuid
from typing import Optional
import webbrowser
import requests
import json

API_BASE_URL = 'https://api-web.kunqiongai.com'
soft_number = '' # 软件编号，可在配置文件中设置

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

#获取设备码/机器码
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

#请求检查是否需要获取授权码
def check_need_auth_code(machine_code: str, soft_number: str):
    
    check_url = API_BASE_URL + "/soft_desktop/check_get_auth_code"
    # Body请求参数（urlencoded）
    data = {
            "device_id": machine_code,
            "soft_number": soft_number
    }
    response = requests.post(check_url, data=data)
    result = response.json()
    if result["code"] == 1:
        if result["data"]["is_need_auth_code"] == 1:
            # 3. 打开获取授权码页面
            get_auth_code_url = f"{result['data']['auth_code_url']}?device_id={machine_code}&software_code={soft_number}"
            webbrowser.open(get_auth_code_url)
        else:
            print("无需获取授权码")
    else:
        print(f"异常：{result['msg']}")
        return False

#验证授权码
#machine_code 机器码
#soft_number 软件编号
def valid_auth_code(machine_code: str, soft_number: str, auth_code: str):
    check_url = API_BASE_URL + "/soft_desktop/check_auth_code_valid"
    # Body请求参数（urlencoded）
    data = {
            "device_id": machine_code,
            "soft_number": soft_number,
            'auth_code': auth_code
    }
    response = requests.post(check_url, data=data)
    result = response.json()
    if result["code"] == 1:
        if result["data"]["auth_code_status"] == 1:
            print("授权码验证有效")
        else:
            print("授权码验证无效")
    else:
        print(f"异常：{result['msg']}")
        return False

if __name__ == "__main__":
    # 测试获取机器码
    machine_code = get_machine_code()
    print(f"电脑唯一机器码：{machine_code}")
    check_need_auth_code(machine_code, soft_number)
    #valid_auth_code(machine_code, "10019", "GQS7D6DQ")
    