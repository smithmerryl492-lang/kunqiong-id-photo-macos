"""测试授权码功能"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.auth_code import (
    get_machine_code,
    check_need_auth_code,
    valid_auth_code
)
from utils.config import SOFT_NUMBER


def test_machine_code():
    """测试机器码生成"""
    print("=" * 50)
    print("测试机器码生成")
    print("=" * 50)
    
    machine_code = get_machine_code()
    print(f"机器码: {machine_code}")
    print(f"机器码长度: {len(machine_code)}")
    
    # 验证机器码是否稳定（多次调用应返回相同值）
    machine_code2 = get_machine_code()
    assert machine_code == machine_code2, "机器码不稳定"
    print("✓ 机器码生成稳定")
    print()


def test_check_need_auth():
    """测试检查是否需要授权码"""
    print("=" * 50)
    print("测试检查授权码需求")
    print("=" * 50)
    
    machine_code = get_machine_code()
    print(f"使用机器码: {machine_code[:16]}...")
    print(f"软件编号: {SOFT_NUMBER if SOFT_NUMBER else '(空)'}")
    
    try:
        need_auth, auth_url, error = check_need_auth_code(machine_code, SOFT_NUMBER)
        
        if error:
            print(f"✗ 检查失败: {error}")
        elif need_auth:
            print("✓ 需要授权码")
            print(f"  获取URL: {auth_url}")
        else:
            print("✓ 无需授权码")
    except Exception as e:
        print(f"✗ 异常: {str(e)}")
    
    print()


def test_valid_auth(auth_code: str = None):
    """测试验证授权码"""
    print("=" * 50)
    print("测试验证授权码")
    print("=" * 50)
    
    if not auth_code:
        print("跳过测试（未提供授权码）")
        print("使用方法: python test_auth_code.py <授权码>")
        print()
        return
    
    machine_code = get_machine_code()
    print(f"使用机器码: {machine_code[:16]}...")
    print(f"软件编号: {SOFT_NUMBER if SOFT_NUMBER else '(空)'}")
    print(f"授权码: {auth_code}")
    
    try:
        is_valid, error = valid_auth_code(machine_code, SOFT_NUMBER, auth_code)
        
        if is_valid:
            print("✓ 授权码有效")
        else:
            print(f"✗ 授权码无效: {error}")
    except Exception as e:
        print(f"✗ 异常: {str(e)}")
    
    print()


def main():
    """主测试函数"""
    print("\n授权码功能测试\n")
    
    # 测试1: 机器码生成
    test_machine_code()
    
    # 测试2: 检查授权码需求
    test_check_need_auth()
    
    # 测试3: 验证授权码（如果提供了授权码）
    auth_code = sys.argv[1] if len(sys.argv) > 1 else None
    test_valid_auth(auth_code)
    
    print("=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
