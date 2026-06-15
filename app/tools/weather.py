"""天气工具"""
from typing import Optional
from langchain_core.tools import Tool
from app.tools.registry import register_tool, ToolConfig


async def get_weather(city: str) -> dict:
    """获取天气
    
    Args:
        city: 城市名称
    
    Returns:
        天气信息
    """
    # 示例实现 - 可接入真实天气API
    weather_data = {
        "city": city,
        "temperature": "25°C",
        "weather": "晴",
        "humidity": "60%",
        "wind": "东南风 3级",
        "update_time": "2024-01-01 12:00"
    }
    
    return weather_data


def weather_tool():
    """创建天气工具"""
    tool = Tool(
        name="get_weather",
        func=lambda c: get_weather(c),
        description="获取城市天气信息。输入城市名称，返回当前天气状况。"
    )
    
    # 配置：超时10秒，每分钟100次，失败5次熔断
    config = ToolConfig(
        name="get_weather",
        description="获取城市天气信息",
        timeout=10,
        rate_limit=100,
        rate_period=60,
        failure_threshold=5,
        recovery_timeout=60,
        max_retries=2
    )
    
    register_tool(tool, config)
    return tool


# 自动注册
weather_tool()