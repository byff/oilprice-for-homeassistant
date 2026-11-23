"""Constants for the oilprice integration."""

DOMAIN = "oilprice"
PLATFORMS = ["sensor", "button"]

CONF_UPDATE_INTERVAL_HOURS = "update_interval_hours"
DEFAULT_UPDATE_INTERVAL_HOURS = 12
MIN_UPDATE_INTERVAL_HOURS = 1
MAX_UPDATE_INTERVAL_HOURS = 168

DEFAULT_REGION = "beijing"
ICON = "mdi:gas-station"

# Slugs used in the entity IDs. They are pinned to the values that
# slugifying the Chinese region name produces, so the entity IDs stay the
# same as before. Two regions cannot share a slug, because 山西 and 陕西 both
# slugify to "shan_xi", so 陕西 gets its own slug.
REGION_SLUGS: dict[str, str] = {
    "anhui": "an_hui",
    "beijing": "bei_jing",
    "chongqing": "zhong_qing",
    "fujian": "fu_jian",
    "gansu": "gan_su",
    "guangdong": "yan_dong",
    "guangxi": "yan_xi",
    "guizhou": "gui_zhou",
    "hainan": "hai_nan",
    "hebei": "he_bei",
    "heilongjiang": "hei_long_jiang",
    "henan": "he_nan",
    "hubei": "hu_bei",
    "hunan": "hu_nan",
    "jiangsu": "jiang_su",
    "jiangxi": "jiang_xi",
    "jilin": "ji_lin",
    "liaoning": "liao_zhu",
    "neimenggu": "nei_meng_gu",
    "ningxia": "zhu_xia",
    "qinghai": "qing_hai",
    "shandong": "shan_dong",
    "shanghai": "shang_hai",
    "shanxi": "shan_xi",
    "shanxisheng": "shaan_xi",
    "sichuan": "si_chuan",
    "tianjin": "tian_jin",
    "xinjiang": "xin_jiang",
    "xizang": "xi_cang",
    "yunnan": "yun_nan",
    "zhejiang": "zhe_jiang",
}

SENSOR_STATE_KEYS = (
    "gas92",
    "gas95",
    "gas98",
    "die0",
    "time",
    "tips",
    "trend",
    "next_adjust_date",
    "update_time",
    "friendly_name",
)

REGIONS: dict[str, str] = {
    "anhui": "安徽",
    "beijing": "北京",
    "chongqing": "重庆",
    "fujian": "福建",
    "gansu": "甘肃",
    "guangdong": "广东",
    "guangxi": "广西",
    "guizhou": "贵州",
    "hainan": "海南",
    "hebei": "河北",
    "heilongjiang": "黑龙江",
    "henan": "河南",
    "hubei": "湖北",
    "hunan": "湖南",
    "jiangsu": "江苏",
    "jiangxi": "江西",
    "jilin": "吉林",
    "liaoning": "辽宁",
    "neimenggu": "内蒙古",
    "ningxia": "宁夏",
    "qinghai": "青海",
    "shandong": "山东",
    "shanghai": "上海",
    "shanxi": "山西",
    "shanxisheng": "陕西",
    "sichuan": "四川",
    "tianjin": "天津",
    "xinjiang": "新疆",
    "xizang": "西藏",
    "yunnan": "云南",
    "zhejiang": "浙江",
}

REGION_SELECTOR_OPTIONS = [
    {"value": code, "label": f"{name} ({code})"} for code, name in REGIONS.items()
]


def region_name(region: str) -> str:
    """Return a friendly region name."""
    return REGIONS.get(region, region)


def region_slug(region: str) -> str:
    """Return the stable slug of a region, used in the entity IDs."""
    return REGION_SLUGS.get(region, region)
