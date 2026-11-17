import hashlib
import os
from datetime import datetime

import requests
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_config
from utils.file_reader import list_project_documents, read_project_document
from utils.logger_handler import logger

rag = RagSummarizeService()

@tool(description="从向量数据库中检索柳州文旅参考资料(景点/美食/路线/交通/文化)")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)


def _amap_request(path: str, params: dict) -> dict:
    """
    调用高德 Web 服务接口(已开启数字签名校验):
    参数按 key 名升序拼接, 末尾拼上私钥后取 md5 作为 sig
    """
    api_key = os.getenv("AMAP_API_KEY") or agent_config.get("amap_api_key", "")
    private_key = os.getenv("AMAP_PRIVATE_KEY") or agent_config.get("amap_private_key", "")
    if not api_key:
        raise RuntimeError("未配置高德 API Key")

    query = dict(params)
    query["key"] = api_key
    raw = "&".join(f"{k}={v}" for k, v in sorted(query.items())) + private_key
    query["sig"] = hashlib.md5(raw.encode("utf-8")).hexdigest()

    resp = requests.get(f"https://restapi.amap.com{path}", params=query, timeout=10).json()
    if resp.get("status") != "1":
        raise RuntimeError(f"高德接口返回异常: {resp.get('info')}")
    return resp


def _aqi_text(city: str) -> str:
    """高德天气不含空气质量: 按经纬度补查实时AQI, 失败时留空不影响主流程"""
    try:
        geo = _amap_request("/v3/geocode/geo", {"address": city})
        lon, lat = geo["geocodes"][0]["location"].split(",")
        data = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={"latitude": lat, "longitude": lon, "current": "us_aqi"},
            timeout=8,
        ).json()
        aqi = data["current"].get("us_aqi")
        return f",AQI{aqi}" if aqi is not None else ""
    except Exception:
        return ""


@tool(description="获取城市的天气,以字符串格式返回,包含当前实况与今天/明天的天气预报")
def get_weather(city: str) -> str:
    try:
        # 1. 实况天气(高德为国内直连接口, 比海外天气API稳定)
        live = (_amap_request(
            "/v3/weather/weatherInfo", {"city": city, "extensions": "base"}
        ).get("lives") or [{}])[0]
        if not live:
            return f"未查询到城市[{city}]的天气信息"

        # 2. 今明两天预报, 供行程规划参考(白天/夜间天气与气温)
        casts = (_amap_request(
            "/v3/weather/weatherInfo", {"city": city, "extensions": "all"}
        ).get("forecasts") or [{}])[0].get("casts") or []

        text = (
            f"{live.get('city', city)}当前{live.get('weather', '未知')},"
            f"气温{live.get('temperature', '未知')}摄氏度,"
            f"{live.get('winddirection', '')}风{live.get('windpower', '')}级,"
            f"湿度{live.get('humidity', '未知')}%{_aqi_text(city)}"
        )
        for cast in casts[:2]:
            text += (
                f";{cast['date']}白天{cast['dayweather']}/夜间{cast['nightweather']},"
                f"{cast['nighttemp']}~{cast['daytemp']}摄氏度,"
                f"{cast['daywind']}风{cast['daypower']}级"
            )
        return text
    except Exception as e:
        logger.warning(f"[get_weather]获取城市{city}天气失败: {e}")
        return f"获取{city}天气失败,请稍后重试"


@tool(description="获取今天的日期和星期,以字符串格式返回,如'2026-10-26 星期一'")
def get_current_date() -> str:
    """行程规划用: 把'明天/这周末'等相对时间换算成具体日期"""
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"{now.strftime('%Y-%m-%d')} {weekdays[now.weekday()]}"


@tool(description="获取用户所在城市名称,以纯字符串格式返回")
def get_user_location() -> str:
    try:
        # 高德IP定位,返回用户真实所在省市(国内直连)
        # key开启了数字签名校验:参数按key名排序拼接,末尾拼上私钥后取md5作为sig
        # 密钥优先从环境变量读取(AMAP_API_KEY/AMAP_PRIVATE_KEY), 未设置时回退config/agent.yml
        api_key = os.getenv("AMAP_API_KEY") or agent_config.get("amap_api_key", "")
        private_key = os.getenv("AMAP_PRIVATE_KEY") or agent_config.get("amap_private_key", "")
        params = {"key": api_key}
        raw = "&".join(f"{k}={v}" for k, v in sorted(params.items())) + private_key
        params["sig"] = hashlib.md5(raw.encode("utf-8")).hexdigest()
        resp = requests.get(
            "https://restapi.amap.com/v3/ip",
            params=params,
            timeout=10,
        ).json()
        city = resp.get("city") or resp.get("province") or ""
        # 直辖市city字段为空数组时兜底用省份;非国内IP返回"局域网"视为失败
        if not city or city == "局域网":
            logger.warning(f"[get_user_location]IP定位失败: {resp}")
            return "IP定位失败"
        # 去掉"市"后缀(高德返回"广州市",天气接口用短名"广州"更易解析)
        return city.removesuffix("市")
    except Exception as e:
        logger.warning(f"[get_user_location]IP定位异常: {e}")
        return "IP定位失败"


@tool(description="列出项目内置的柳州文旅资料文件(景点/美食/行程/文化等), 返回文件名列表供后续读取")
def list_documents() -> str:
    docs = list_project_documents()
    if not docs:
        return "项目资料目录为空"
    lines = [f"{d['name']}  ({d['size']} 字节)" for d in docs]
    return "项目内置资料文件:\n" + "\n".join(lines)


@tool(description="读取项目内置资料文件的完整内容, filename 必须是 list_documents 返回的文件名之一")
def view_document(filename: str) -> str:
    content = read_project_document(filename)
    return content


if __name__ == "__main__":
    print(get_current_date.invoke({}))
    print(get_weather.invoke({"city": "柳州"}))
    print(get_user_location.invoke({}))
