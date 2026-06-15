"""测试CSV文件路径

检查CSV文件路径是否正确
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("\n" + "="*60)
print("测试CSV文件路径")
print("="*60)

# 1. 检查当前工作目录
print(f"\n【当前工作目录】")
print(f"   os.getcwd(): {os.getcwd()}")

# 2. 检查文件路径
print(f"\n【文件路径检查】")

# 方法1：相对路径
relative_path = "data/China-City-List-latest.csv"
print(f"   相对路径: {relative_path}")
print(f"   是否存在: {os.path.exists(relative_path)}")

# 方法2：绝对路径
absolute_path = os.path.abspath(relative_path)
print(f"   绝对路径: {absolute_path}")
print(f"   是否存在: {os.path.exists(absolute_path)}")

# 方法3：从脚本目录计算
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
csv_path = os.path.join(project_root, "data", "China-City-List-latest.csv")
print(f"   从脚本计算: {csv_path}")
print(f"   是否存在: {os.path.exists(csv_path)}")

# 方法4：从app/tools目录计算（模拟city_code_lookup.py）
tools_dir = os.path.join(project_root, "app", "tools")
print(f"   tools目录: {tools_dir}")
print(f"   tools目录是否存在: {os.path.exists(tools_dir)}")

# 从tools目录计算项目根目录
project_root_from_tools = os.path.dirname(os.path.dirname(tools_dir))
csv_path_from_tools = os.path.join(project_root_from_tools, "data", "China-City-List-latest.csv")
print(f"   从tools计算: {csv_path_from_tools}")
print(f"   是否存在: {os.path.exists(csv_path_from_tools)}")

# 3. 尝试读取文件
print(f"\n【尝试读取文件】")
if os.path.exists(absolute_path):
    import csv
    with open(absolute_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            count += 1
            if count <= 5:
                print(f"   第{count}行: {row.get('Location_Name_ZH')} -> {row.get('Location_ID')}")
        
        print(f"   总行数: {count}")
else:
    print(f"   文件不存在")

print("\n" + "="*60)
print("测试完成")
print("="*60)