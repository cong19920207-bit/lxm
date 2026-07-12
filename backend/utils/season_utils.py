# -*- coding: utf-8 -*-
# 生活流·季节计算工具（STEP-013）
#
# 北半球：3-5 春 / 6-8 夏 / 9-11 秋 / 12-2 冬
# 南半球白名单城市反向：3-5 秋 / 6-8 冬 / 9-11 春 / 12-2 夏（PRD 4.4.3 / 10.7#4）

from datetime import date

from backend.constants.life_feed_config import DEFAULT_SOUTHERN_HEMISPHERE_CITIES

_NORTH = {3: "春", 4: "春", 5: "春", 6: "夏", 7: "夏", 8: "夏",
          9: "秋", 10: "秋", 11: "秋", 12: "冬", 1: "冬", 2: "冬"}
_SOUTH = {3: "秋", 4: "秋", 5: "秋", 6: "冬", 7: "冬", 8: "冬",
          9: "春", 10: "春", 11: "春", 12: "夏", 1: "夏", 2: "夏"}


def compute_season(city: str, plan_date: date, southern_cities=None) -> str:
    """
    按城市 + 日期计算季节。

    Args:
        city: 城市名
        plan_date: 日期
        southern_cities: 南半球城市集合；None 时使用默认白名单常量
    """
    if southern_cities is None:
        southern_cities = DEFAULT_SOUTHERN_HEMISPHERE_CITIES
    month = plan_date.month
    if city in set(southern_cities):
        return _SOUTH[month]
    return _NORTH[month]
