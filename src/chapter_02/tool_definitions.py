import datetime
import httpx


weather_tool = {
    "name": "get_weather",
    "description": "获取指定城市的实时天气信息，包括温度、天气状况、湿度等",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，如'北京'、'shanghai'、'tokyo'（支持中英文）",
                "minLength": 1,
            },
        },
        "required": ["city"],
    },
}


time_tool = {
    "name": "get_current_time",
    "description": "获取当前的日期和时间",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def fetch_weather(city):
    """真实天气查询 —— 调用 wttr.in 免费 API"""
    url = f"https://wttr.in/{city}?format=j1"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    data = response.json()

    current = data["current_condition"][0]
    return {
        "city": city,
        "temperature": f"{current['temp_C']}°C",
        "humidity": f"{current['humidity']}%",
        "condition": current["weatherDesc"][0]["value"],
        "wind": f"{current['windspeedKmph']} km/h",
        "feels_like": f"{current['FeelsLikeC']}°C",
        "visibility": f"{current['visibility']} km",
    }



def get_current_time():
    """获取当前日期时间"""
    now = datetime.datetime.now()
    tz_name = now.astimezone().tzname() if now.astimezone().tzinfo else "UTC"
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": now.timestamp(),
        "timezone": tz_name,
    }
