"""测试天气工具

验证和风天气API是否正常工作
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.tools.weather import get_weather
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def test_weather_tool():
    """测试天气工具"""
    print("\n" + "="*60)
    print("测试天气工具（和风天气API）")
    print("="*60)
    
    # 检查配置
    print(f"\n【配置检查】")
    print(f"API Host: {settings.QWEATHER_API_HOST}")
    print(f"API Token: {settings.QWEATHER_API_TOKEN[:20]}..." if settings.QWEATHER_API_TOKEN else "未配置")
    print(f"默认城市: {settings.QWEATHER_DEFAULT_LOCATION}")
    
    if not settings.QWEATHER_API_TOKEN or settings.QWEATHER_API_TOKEN == "your_token_here":
        print(f"\n⚠️  请在 .env 文件中配置 QWEATHER_API_TOKEN")
        print(f"   获取Token: https://dev.qweather.com/")
        return
    
    # 测试城市查询
    test_cities = ["北京", "上海", "广州", "深圳", "101010100"]
    
    for city in test_cities:
        print(f"\n【测试城市】{city}")
        
        try:
            result = await get_weather(city)
            
            if result.get("success"):
                print(f"✅ 成功获取天气信息")
                print(f"   城市: {result.get('city')}")
                print(f"   天气: {result.get('weather')}")
                print(f"   温度: {result.get('temperature')}°C")
                print(f"   体感温度: {result.get('feels_like')}°C")
                print(f"   湿度: {result.get('humidity')}%")
                print(f"   风向: {result.get('wind_dir')} {result.get('wind_scale')}级")
                print(f"   更新时间: {result.get('update_time')}")
                
                # 打印完整描述
                print(f"\n【天气描述】")
                print(result.get('description'))
            else:
                print(f"❌ 失败: {result.get('error')}")
        
        except Exception as e:
            print(f"❌ 异常: {str(e)}")
            import traceback
            traceback.print_exc()


async def test_weather_in_chat():
    """测试天气工具在聊天中的使用"""
    print("\n" + "="*60)
    print("测试天气工具在聊天中的使用")
    print("="*60)
    
    # 这里可以测试通过聊天API调用天气工具
    # 例如："北京天气怎么样"
    print(f"\n【提示】")
    print(f"可以通过聊天API测试天气工具：")
    print(f"   用户问题: '北京天气怎么样'")
    print(f"   预期响应: 返回北京的实时天气信息")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("天气工具测试")
    print("="*60)
    
    await test_weather_tool()
    await test_weather_in_chat()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())