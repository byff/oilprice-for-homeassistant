"""API helpers for the oilprice integration."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

from aiohttp import ClientError
from bs4 import BeautifulSoup
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import region_name

_BASE_URL = "https://www.huangjinjiage.cn/oil/{region}.html"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}
_GRADE_LABEL_PATTERN = r"(89|92|95|98)号汽油|(-?\d+)号柴油"


class OilPriceApiError(Exception):
    """Base API error."""


class OilPriceCannotConnectError(OilPriceApiError):
    """Raised when remote endpoint cannot be reached."""


class OilPriceInvalidRegionError(OilPriceApiError):
    """Raised when region is invalid or unsupported."""


async def async_fetch_oilprice(hass, region: str) -> dict[str, Any]:
    """Fetch and parse oil price information for a region."""
    session = async_get_clientsession(hass)

    try:
        async with session.get(_BASE_URL.format(region=region), headers=_HEADERS) as response:
            if response.status >= 400:
                raise OilPriceCannotConnectError
            raw_bytes = await response.read()
            text = _decode_page(raw_bytes)
    except ClientError as err:
        raise OilPriceCannotConnectError from err

    soup = BeautifulSoup(text, "html.parser")
    normalized_text = _normalize_text(soup.get_text("\n", strip=True))

    table_prices = _extract_prices_from_tables(soup)
    parsed_prices = _extract_prices_by_section(normalized_text)
    gas92 = _pick_price(table_prices.get("gas92"), parsed_prices.get("gas92"))
    gas95 = _pick_price(table_prices.get("gas95"), parsed_prices.get("gas95"))
    gas98 = _pick_price(table_prices.get("gas98"), parsed_prices.get("gas98"))
    die0 = _pick_price(table_prices.get("die0"), parsed_prices.get("die0"))

    time_text, tips_text = _extract_notice_fields(soup, normalized_text)
    trend_text = _extract_trend_text(tips_text)
    next_adjust_date = _extract_next_adjust_date_text(time_text)

    if not any([gas92, gas95, gas98, die0, time_text, tips_text]):
        raise OilPriceInvalidRegionError

    update_time = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
    state = gas92 or time_text or "unknown"

    return {
        "state": state,
        "gas92": gas92,
        "gas95": gas95,
        "gas98": gas98,
        "die0": die0,
        "time": time_text,
        "tips": tips_text,
        "trend": trend_text,
        "next_adjust_date": next_adjust_date,
        "update_time": update_time,
        "region": region,
        "region_name": region_name(region),
    }


def _extract_notice_fields(
    soup: BeautifulSoup, page_text: str
) -> Tuple[Optional[str], Optional[str]]:
    """Extract notice time and tips from huangjinjiage page text."""
    time_text = _extract_time_text(page_text)
    tip_text = _extract_tips_text(soup)

    return time_text, tip_text


def _normalize_text(text: str) -> str:
    """Normalize whitespace for predictable regex parsing."""
    return re.sub(r"\s+", " ", text).strip()


def _decode_page(raw_bytes: bytes) -> str:
    """Decode source page with fallback charsets used by Chinese websites."""
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_bytes.decode("utf-8", errors="ignore")


def _extract_prices_by_section(page_text: str) -> dict[str, Optional[str]]:
    """Extract fuel prices from ordered gasoline/diesel sections.

    The page lists the gasoline grades in a fixed order, but the optional
    grades differ per section: 89# gasoline is the leading optional column of
    the gasoline table, while 0# diesel is the leading required column of the
    diesel table and the numbered diesel grades trail it. A grade without a
    published price is either dropped or rendered as a dash, so the prices are
    aligned to the grades from the side that stays fixed.
    """
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    gasoline_section = _extract_section(
        page_text, r"今日汽油价格[（(]元/升[）)]", r"今日柴油价格[（(]元/升[）)]"
    )
    if gasoline_section:
        _merge_prices(values, _match_prices_to_grades(gasoline_section, from_end=True))

    diesel_section = _extract_section(
        page_text,
        r"今日柴油价格[（(]元/升[）)]",
        r"油价调整最新消息|今日油价最新消息|今日汽油价格",
    )
    if diesel_section:
        _merge_prices(values, _match_prices_to_grades(diesel_section, from_end=False))

    return values


def _merge_prices(
    target: dict[str, Optional[str]], extra: dict[str, Optional[str]]
) -> None:
    """Copy the prices that are still missing into the target."""
    for key, value in extra.items():
        if target.get(key) is None and value is not None:
            target[key] = value


def _extract_section(
    page_text: str, start_pattern: str, end_pattern: str
) -> Optional[str]:
    """Return the text between the start marker and the next end marker."""
    start_match = re.search(start_pattern, page_text)
    if start_match is None:
        return None

    rest = page_text[start_match.end() :]
    end_match = re.search(end_pattern, rest)
    if end_match is not None:
        rest = rest[: end_match.start()]

    return rest.strip()


def _match_prices_to_grades(
    section_text: str, *, from_end: bool
) -> dict[str, Optional[str]]:
    """Match the prices of a section to the fuel grades listed before them.

    The section reads as a run of grade labels followed by a run of prices.
    When a grade has no published price it is either skipped or shown as a
    dash, so the prices are aligned to the grades from the fixed side.
    """
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    grade_matches = list(re.finditer(_GRADE_LABEL_PATTERN, section_text))
    if not grade_matches:
        return values

    prices = _extract_price_tokens(section_text[grade_matches[-1].end() :])
    if not prices:
        return values

    grades = [_grade_key(grade_match) for grade_match in grade_matches]
    if len(prices) > len(grades):
        return values

    if from_end:
        pairs = zip(reversed(grades), reversed(prices))
    else:
        pairs = zip(grades, prices)

    for grade, price in pairs:
        if grade is None or grade not in values:
            continue
        if values[grade] is None:
            values[grade] = _none_if_dash(price)

    return values


def _grade_key(grade_match: re.Match[str]) -> Optional[str]:
    """Return the sensor field key of a grade label match."""
    gasoline_grade = grade_match.group(1)
    if gasoline_grade is not None:
        return f"gas{gasoline_grade}"

    diesel_grade = grade_match.group(2)
    if diesel_grade == "0":
        return "die0"

    return None


def _extract_prices_from_tables(soup: BeautifulSoup) -> dict[str, Optional[str]]:
    """Extract prices from table.bx layout by reading the first data row after headers."""
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    for table in soup.select("table.bx"):
        table_prices = _extract_prices_from_table_first_data_row(table)
        if any(table_prices.values()):
            for key, value in table_prices.items():
                if values[key] is None and value is not None:
                    values[key] = value
            continue

        header_cells = table.select("tbody tr:nth-of-type(1) th, tbody tr:nth-of-type(1) td")
        value_cells = table.select("tbody tr:nth-of-type(2) td, tbody tr:nth-of-type(2) th")
        if not header_cells or not value_cells:
            continue

        for index, header_cell in enumerate(header_cells):
            if index >= len(value_cells):
                continue

            header_text = _normalize_text(header_cell.get_text(" ", strip=True))
            value_text = _normalize_text(value_cells[index].get_text(" ", strip=True))
            value = _normalize_price_value(value_text)

            if "92" in header_text and "汽油" in header_text:
                values["gas92"] = value
            elif "95" in header_text and "汽油" in header_text:
                values["gas95"] = value
            elif "98" in header_text and "汽油" in header_text:
                values["gas98"] = value
            elif header_text.startswith("0") and "柴油" in header_text:
                values["die0"] = value

    return values


def _extract_prices_from_table_first_data_row(table) -> dict[str, Optional[str]]:
    """Extract prices from the first data row after a matching header row."""
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    rows = table.select("tbody tr")
    if len(rows) < 2:
        return values

    for header_row_index, row in enumerate(rows[:-1]):
        cells = row.select("td, th")
        if not cells:
            continue

        header_texts = [_normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
        has_target_header = any(
            ("92" in text and "汽油" in text)
            or ("95" in text and "汽油" in text)
            or ("98" in text and "汽油" in text)
            or (text.startswith("0") and "柴油" in text)
            for text in header_texts
        )
        if not has_target_header:
            continue

        header_cells = rows[header_row_index].select("td, th")

        # Find the first non-empty data-like row below the matched header row.
        first_data_cells = []
        for candidate_row in rows[header_row_index + 1 :]:
            candidate_cells = candidate_row.select("td, th")
            if not candidate_cells:
                continue

            candidate_texts = [
                _normalize_text(cell.get_text(" ", strip=True)) for cell in candidate_cells
            ]
            if any(_normalize_price_value(text) is not None for text in candidate_texts):
                first_data_cells = candidate_cells
                break

        if not first_data_cells:
            continue

        for index, header_cell in enumerate(header_cells):
            if index >= len(first_data_cells):
                continue

            header_text = _normalize_text(header_cell.get_text(" ", strip=True))
            value_text = _normalize_text(first_data_cells[index].get_text(" ", strip=True))
            value = _normalize_price_value(value_text)

            if "92" in header_text and "汽油" in header_text:
                values["gas92"] = value
            elif "95" in header_text and "汽油" in header_text:
                values["gas95"] = value
            elif "98" in header_text and "汽油" in header_text:
                values["gas98"] = value
            elif header_text.startswith("0") and "柴油" in header_text:
                values["die0"] = value

        if any(values.values()):
            break

    return values


def _extract_price_tokens(text: str) -> list[str]:
    """Return ordered price-like tokens (decimal or standalone dash)."""
    return re.findall(r"\d+\.\d+|(?<!\d)-(?=\s|$)", text)


def _none_if_dash(value: str) -> Optional[str]:
    """Convert placeholder dash to None."""
    return None if value == "-" else value


def _normalize_price_value(value: str) -> Optional[str]:
    """Normalize table price cell value."""
    if not value or value == "-":
        return None
    if re.fullmatch(r"\d+\.\d+", value) is None:
        return None
    return value


def _pick_price(primary: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """Pick primary parsed value, otherwise fallback value."""
    return primary if primary is not None else fallback


def _extract_time_text(page_text: str) -> Optional[str]:
    """Extract next adjustment time sentence.

    The wording differs per province: most use "油价下次调价时间为", while
    some use "下一个油价调整日期为". The summary paragraph on the page is
    preferred over the news paragraph, so it is matched first.
    """
    for pattern in (
        r"(油价下次调价时间[为:：]?[^；。\n]+)",
        r"(下一个油价调整日期为[^；。\n]+)",
        r"(下次国内成品油价调整窗口时间为[^；。\n]+)",
    ):
        match = re.search(pattern, page_text)
        if match is not None:
            return match.group(1).strip()

    return None


def _extract_tips_text(soup: BeautifulSoup) -> Optional[str]:
    """Extract latest trend tip text from news paragraphs.

    Finds <p> tags containing target keywords and returns their full text
    content, including text within child elements like <strong>.

    The page lists several news paragraphs, and the newest one comes first.
    Every paragraph after it describes an older adjustment, so the paragraphs
    are scanned in order and the first one that carries a dated "今日油价"
    headline wins over the older "油价调整最新消息" entries.
    """
    keywords = ["今日油价最新消息", "今日油价涨跌最新消息", "油价调整最新消息"]

    for p in soup.find_all("p"):
        p_text = _normalize_text(p.get_text(" ", strip=True))
        if not p_text:
            continue
        for keyword in keywords:
            if keyword in p_text:
                return p_text

    # Fallback: search in stripped_strings if no <p> tag matches
    page_lines = [_normalize_text(line) for line in soup.stripped_strings]
    page_lines = [line for line in page_lines if line]
    for keyword in keywords:
        for line in page_lines:
            if keyword in line:
                return line

    return None


def _extract_trend_text(tips_text: Optional[str]) -> Optional[str]:
    """Extract adjustment trend from the forecast segment in tips text."""
    if not tips_text:
        return None

    normalized = _normalize_text(tips_text)

    # Highest priority: extract from the pricing-cycle forecast segment.
    cycle_match = re.search(
        r"新一轮\d+个工作日统计周期[^。；]{0,120}(?:预计|预期|预测)[^。；]{0,20}油价[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
        normalized,
    )
    if cycle_match is not None:
        trend = _normalize_trend_token(cycle_match.group(1))
        if trend is not None:
            return trend

    # Prefer the explicit forecast wording (e.g. "预计油价上涨...") to avoid
    # being misled by unrelated "国际油价上涨/下跌" context.
    forecast_patterns = (
        r"(?:预计|预期|预测)[^。；，]{0,20}油价[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
    )
    for pattern in forecast_patterns:
        match = re.search(pattern, normalized)
        if match is not None:
            trend = _normalize_trend_token(match.group(1))
            if trend is not None:
                return trend

    # The settlement wording states the change of the finished oil price
    # directly, e.g. "油价下调480元/吨". The crude oil market is described as
    # "国际油价" or "原油价格", so those wordings are excluded here.
    settlement_patterns = (
        r"(?<![际原])油价(?![格])[^。；，]{0,6}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
    )
    for pattern in settlement_patterns:
        match = re.search(pattern, normalized)
        if match is not None:
            trend = _normalize_trend_token(match.group(1))
            if trend is not None:
                return trend

    # Some pages use settlement wording like "今晚汽油上涨...柴油上涨...".
    settle_match = re.search(
        r"(?:今晚|本次|本轮)?[^。；，]{0,12}(?:汽油|柴油)[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
        normalized,
    )
    if settle_match is not None:
        trend = _normalize_trend_token(settle_match.group(1))
        if trend is not None:
            return trend

    # Conservative fallback: only parse when adjustment keywords lead the trend term.
    fallback_patterns = (
        r"调价[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
        r"窗口时间[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
    )
    for pattern in fallback_patterns:
        match = re.search(pattern, normalized)
        if match is not None:
            trend = _normalize_trend_token(match.group(1))
            if trend is not None:
                return trend

    return None


def _normalize_trend_token(token: str) -> Optional[str]:
    """Normalize trend wording to canonical values."""
    if token in ("下调", "下跌", "下降"):
        return "下调"
    if token in ("搁浅", "不作调整", "不做调整", "维持"):
        return "搁浅"
    if token in ("上调", "上涨", "上升"):
        return "上涨"
    return None


def _extract_next_adjust_date_text(time_text: Optional[str]) -> Optional[str]:
    """Extract concise next adjustment date text from the full time sentence.

    The page states the adjustment moment in several shapes, for example
    "2026年4月7日 24:00", "2026年4月7日24时" and
    "2026年11月26日24时（2026年11月27日0点）". A "24" hour always means
    midnight of the following day, and the page sometimes states that
    following day explicitly in parentheses, which is the most reliable
    source.
    """
    if not time_text:
        return None

    parenthesized = re.search(
        r"[（(]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[:：点](\d{2})?\s*[）)]",
        time_text,
    )
    if parenthesized is not None:
        year = int(parenthesized.group(1))
        month = int(parenthesized.group(2))
        day = int(parenthesized.group(3))
        hour = int(parenthesized.group(4))
        minute = int(parenthesized.group(5) or 0)
        return _format_adjust_date(year, month, day, hour, minute)

    match = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(?:(\d{1,2})[:：](\d{2})|(\d{1,2})[点时])?",
        time_text,
    )
    if match is None:
        return None

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    if match.group(4) is not None:
        hour = int(match.group(4))
        minute = int(match.group(5))
    elif match.group(6) is not None:
        hour = int(match.group(6))
        minute = 0
    else:
        hour = 0
        minute = 0

    return _format_adjust_date(year, month, day, hour, minute)


def _format_adjust_date(year: int, month: int, day: int, hour: int, minute: int) -> str:
    """Format an adjustment moment, rolling 24:00 over to the next day."""
    if hour == 24:
        date_obj = datetime(year, month, day) + timedelta(days=1)
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        hour = 0
        minute = 0

    date_part = f"{year}年{month}月{day}日"
    if minute == 0:
        return f"{date_part}{hour}点"
    return f"{date_part}{hour}:{minute:02d}"
