"""测试城市代码匹配功能

验证城市代码查找工具是否正常工作
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.tools.city_code_lookup import lookup_city_code, city_code_lookup
from app.tools.weather import get_weather


async def test_city_code_lookup():
    """测试城市代码查找"""
    print("\n" + "="*60)
    print("测试城市代码查找功能")
    print("="*60)
    
    # 测试城市列表
    test_cities = [
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "南京",
        "成都",
        "武汉",
        "西安",
        "天津",
        "重庆",
        "苏州",
        "郑州",
        "长沙",
        "青岛",
        "大连",
        "宁波",
        "厦门",
        "福州",
        "沈阳",
        # 区县测试
        "海淀区",
        "朝阳区",
        "浦东新区",
        # 模糊匹配测试
        "海淀区天气",
        "朝阳区天气",
    ]
    
    print(f"\n【测试城市代码查找】")
    
    for city in test_cities:
        city_code = lookup_city_code(city)
        
        if city_code:
            print(f"   ✅ {city} -> {city_code}")
        else:
            print(f"   ❌ {city} -> 未找到")
    
    # 测试主要城市
    print(f"\n【测试主要城市】")
    major_cities = city_code_lookup.get_major_cities()
    
    for city, code in major_cities.items():
        print(f"   {city} -> {code}")


async def test_weather_with_city_code():
    """测试天气查询（使用城市代码）"""
    print("\n" + "="*60)
    print("测试天气查询（使用城市代码）")
    print("="*60)
    
    # 测试城市
    test_cities = [
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州"
    ]
    
    for city in test_cities:
        print(f"\n【测试城市】{city}")
        
        # 1. 查找城市代码
        city_code = lookup_city_code(city)
        print(f"   城市代码: {city_code}")
        
        if city_code:
            # 2. 调用天气API
            weather_data = await get_weather(city)
            
            if weather_data.get('success'):
                print(f"   ✅ 天气查询成功")
                print(f"   温度: {weather_data.get('temperature')}°C")
                print(f"   天气: {weather_data.get('weather')}")
                print(f"   湿度: {weather_data.get('humidity')}%")
            else:
                print(f"   ❌ 天气查询失败: {weather_data.get('error')}")
        else:
            print(f"   ❌ 城市代码未找到")


async def test_weather_with_city_code_directly():
    """测试直接使用城市代码查询天气"""
    print("\n" + "="*60)
    print("测试直接使用城市代码查询天气")
    print("="*60)
    
    # 测试城市代码
    test_codes = [
        "101010100",  # 北京
        "101020100",  # 上海
        "101280101",  # 广州
        "101280601",  # 深圳
    ]
    
    for code in test_codes:
        print(f"\n【测试城市代码】{code}")
        
        weather_data = await get_weather(code)
        
        if weather_data.get('success'):
            print(f"   ✅ 天气查询成功")
            print(f"   城市: {weather_data.get('city')}")
            print(f"   温度: {weather_data.get('temperature')}°C")
            print(f"   天气: {weather_data.get('weather')}")
        else:
            print(f"   ❌ 天气查询失败: {weather_data.get('error')}")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("城市代码匹配功能测试")
    print("="*60)
    
    await test_city_code_lookup()
    await test_weather_with_city_code()
    await test_weather_with_city_code_directly()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())