"""诊断天气API问题

检查API配置和请求是否正确
"""
import asyncio
import httpx
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.config import get_settings

settings = get_settings()


async def diagnose_weather_api():
    """诊断天气API"""
    print("\n" + "="*60)
    print("诊断天气API问题")
    print("="*60)
    
    # 1. 检查配置
    print(f"\n【步骤 1】检查配置")
    print(f"API Host: {settings.QWEATHER_API_HOST}")
    print(f"API Token: {settings.QWEATHER_API_TOKEN}")
    print(f"默认城市: {settings.QWEATHER_DEFAULT_LOCATION}")
    
    if not settings.QWEATHER_API_TOKEN:
        print(f"\n❌ API Token未配置")
        return
    
    # 2. 测试API连接
    print(f"\n【步骤 2】测试API连接")
    
    # 测试不同的API endpoint
    test_urls = [
        f"{settings.QWEATHER_API_HOST}/v7/weather/now",
        "https://devapi.qweather.com/v7/weather/now",
        "https://api.qweather.com/v7/weather/now"
    ]
    
    for url in test_urls:
        print(f"\n测试URL: {url}")
        
        params = {
            "location": settings.QWEATHER_DEFAULT_LOCATION,
            "key": settings.QWEATHER_API_TOKEN
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                
                print(f"HTTP状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"API返回码: {data.get('code')}")
                    print(f"响应数据: {data}")
                    
                    if data.get("code") == "200":
                        print(f"\n✅ 成功！API连接正常")
                        print(f"天气数据: {data.get('now')}")
                        return
                    else:
                        print(f"\n❌ API返回错误: {data.get('code')}")
                        print(f"可能原因:")
                        print(f"  - API Token无效或过期")
                        print(f"  - 权限不足（需要订阅服务）")
                        print(f"  - 城市代码错误")
                else:
                    print(f"\n❌ HTTP错误: {response.status_code}")
                    print(f"响应内容: {response.text[:200]}")
                    
                    if response.status_code == 403:
                        print(f"\n可能原因:")
                        print(f"  - API Token无效或过期")
                        print(f"  - 权限不足（免费订阅可能有限制）")
                        print(f"  - IP地址不在白名单中")
        
        except Exception as e:
            print(f"\n❌ 异常: {str(e)}")
    
    # 3. 检查API Token格式
    print(f"\n【步骤 3】检查API Token格式")
    
    if len(settings.QWEATHER_API_TOKEN) < 10:
        print(f"❌ API Token太短，可能无效")
    else:
        print(f"✅ API Token长度正常")
    
    # 4. 提供解决方案
    print(f"\n【解决方案】")
    print(f"1. 检查API Token是否正确")
    print(f"   - 登录和风天气开发者平台: https://dev.qweather.com/")
    print(f"   - 查看应用详情，确认API Token")
    print(f"   - 确认应用状态是否正常")
    
    print(f"\n2. 检查订阅权限")
    print(f"   - 免费订阅可能有限制（每天1000次）")
    print(f"   - 确认是否订阅了天气API服务")
    print(f"   - 检查是否有足够的调用次数")
    
    print(f"\n3. 检查API Host")
    print(f"   - 免费订阅: https://devapi.qweather.com")
    print(f"   - 付费订阅: https://api.qweather.com")
    print(f"   - 确认你使用的是正确的Host")


async def main():
    """主函数"""
    await diagnose_weather_api()
    
    print("\n" + "="*60)
    print("诊断完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())