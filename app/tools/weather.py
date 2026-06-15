"""天气工具 - 接入和风天气API"""
import httpx
from typing import Optional, Dict, Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.tools.registry import register_tool, ToolConfig
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class WeatherInput(BaseModel):
    """天气查询输入参数"""
    city: str = Field(
        ...,
        description="城市名称或城市代码（如：北京、101010100）"
    )


async def get_weather(city: str) -> Dict[str, Any]:
    """获取天气信息（接入和风天气API）
    
    Args:
        city: 城市名称或城市代码
    
    Returns:
        天气信息字典，包含温度、天气状况、湿度等
    """
    try:
        # 1. 获取城市代码（如果输入的是城市名称，需要先查询城市代码）
        location_id = await _get_location_id(city)
        
        # 2. 调用天气API
        weather_data = await _fetch_weather(location_id)
        
        # 3. 格式化返回结果
        return _format_weather_response(city, weather_data)
    
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"获取天气信息失败: {str(e)}"
        }


async def _get_location_id(city: str) -> str:
    """获取城市代码
    
    Args:
        city: 城市名称或城市代码
    
    Returns:
        城市代码（如：101010100）
    """
    # 如果已经是城市代码（数字），直接返回
    if city.isdigit():
        logger.info(f"使用城市代码: {city}")
        return city
    
    # 优先使用本地CSV文件查找城市代码（快速、可靠）
    try:
        from app.tools.city_code_lookup import lookup_city_code
        
        city_code = lookup_city_code(city)
        if city_code:
            logger.info(f"本地查找成功: {city} -> {city_code}")
            return city_code
        else:
            logger.warning(f"本地查找失败: {city}")
    except Exception as e:
        logger.warning(f"本地查找出错: {e}")
    
    # 如果本地查找失败，调用和风天气的城市查询API（备用方案）
    try:
        url = f"{settings.QWEATHER_API_HOST}/v2/city/lookup"
        
        # 和风天气使用 HTTP Header 认证
        headers = {
            "X-QW-Api-Key": settings.QWEATHER_API_TOKEN
        }
        
        params = {
            "location": city
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params, headers=headers)
            data = response.json()
            
            if data.get("code") == "200" and data.get("location"):
                # 返回第一个匹配的城市代码
                city_code = data["location"][0]["id"]
                logger.info(f"API查找成功: {city} -> {city_code}")
                return city_code
            else:
                # 如果查询失败，使用默认城市代码
                logger.warning(f"API查找失败 for {city}, using default")
                return settings.QWEATHER_DEFAULT_LOCATION
    
    except Exception as e:
        logger.error(f"API查找出错: {e}")
        return settings.QWEATHER_DEFAULT_LOCATION


async def _fetch_weather(location_id: str) -> Dict[str, Any]:
    """调用和风天气API获取天气数据
    
    Args:
        location_id: 城市代码
    
    Returns:
        天气API原始数据
    """
    url = f"{settings.QWEATHER_API_HOST}/v7/weather/now"
    
    # 和风天气使用 HTTP Header 认证，不是 URL 参数
    headers = {
        "X-QW-Api-Key": settings.QWEATHER_API_TOKEN
    }
    
    params = {
        "location": location_id
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, params=params, headers=headers)
        
        # 检查响应状态
        if response.status_code != 200:
            logger.error(f"HTTP error: {response.status_code}, response: {response.text[:200]}")
            raise Exception(f"HTTP error: {response.status_code}")
        
        try:
            data = response.json()
        except Exception as e:
            logger.error(f"JSON parse error: {e}, response text: {response.text[:200]}")
            raise Exception(f"JSON parse error: {str(e)}")
        
        if data.get("code") != "200":
            raise Exception(f"API returned error code: {data.get('code')}, message: {data.get('message', 'Unknown')}")
        
        return data


def _format_weather_response(city: str, weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """格式化天气响应
    
    Args:
        city: 城市名称
        weather_data: API原始数据
    
    Returns:
        格式化的天气信息
    """
    now = weather_data.get("now", {})
    
    # 构建天气信息
    weather_info = {
        "success": True,
        "city": city,
        "temperature": now.get("temp", "未知"),
        "feels_like": now.get("feelsLike", "未知"),
        "weather": now.get("text", "未知"),
        "humidity": now.get("humidity", "未知"),
        "wind_dir": now.get("windDir", "未知"),
        "wind_scale": now.get("windScale", "未知"),
        "wind_speed": now.get("windSpeed", "未知"),
        "pressure": now.get("pressure", "未知"),
        "visibility": now.get("vis", "未知"),
        "update_time": weather_data.get("updateTime", "未知"),
        "observation_time": now.get("obsTime", "未知"),
        
        # 格式化的文本描述
        "description": f"""
城市：{city}
天气：{now.get('text', '未知')}
温度：{now.get('temp', '未知')}°C（体感温度：{now.get('feelsLike', '未知')}°C）
风向：{now.get('windDir', '未知')} {now.get('windScale', '未知')}级（风速：{now.get('windSpeed', '未知')} km/h）
湿度：{now.get('humidity', '未知')}%
气压：{now.get('pressure', '未知')} hPa
能见度：{now.get('vis', '未知')} km
更新时间：{weather_data.get('updateTime', '未知')}
"""
    }
    
    return weather_info


def weather_tool():
    """创建天气工具"""
    tool = StructuredTool(
        name="get_weather",
        func=lambda city: get_weather(city),
        coroutine=lambda city: get_weather(city),
        description="获取城市天气信息。输入城市名称（如：北京、上海）或城市代码，返回当前天气状况，包括温度、湿度、风向等详细信息。",
        args_schema=WeatherInput
    )
    
    # 配置：超时10秒，每分钟100次，失败5次熔断
    config = ToolConfig(
        name="get_weather",
        description="获取城市天气信息（和风天气API）",
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