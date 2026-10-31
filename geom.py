"""归一化坐标/区域表达式的解析与格式化。"""
import re


def parse_crop_expression(crop_text):
    """解析 (x / 宽, y / 高, w / 宽, h / 高) 形式的区域，返回 0~1 元组。"""
    if crop_text in (None, "", []):
        return 0.0, 0.0, 1.0, 1.0
    if isinstance(crop_text, (list, tuple)) and len(crop_text) == 4:
        return tuple(float(item) for item in crop_text)

    text = str(crop_text).strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()

    # 支持中文括号/逗号
    text = text.replace("，", ",").replace("（", "(").replace("）", ")")
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) != 4:
        raise ValueError("区域需要 4 个值，例如 (100 / 1920, 540 / 1080, 300 / 1920, 200 / 1080)")

    values = []
    for part in parts:
        if "/" in part:
            numerator, denominator = part.split("/", 1)
            denominator_value = float(denominator.strip())
            if denominator_value == 0:
                raise ValueError("区域分母不能为 0")
            values.append(float(numerator.strip()) / denominator_value)
        else:
            values.append(float(part))
    return tuple(values)


def parse_point_expression(point_text):
    if isinstance(point_text, (list, tuple)) and len(point_text) == 2:
        return tuple(float(item) for item in point_text)
    text = str(point_text or "").strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    text = text.replace("，", ",").replace("（", "(").replace("）", ")")
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) != 2:
        raise ValueError("坐标需要 2 个值，例如 (100 / 1920, 540 / 1080)")
    values = []
    for part in parts:
        if "/" in part:
            numerator, denominator = part.split("/", 1)
            denominator_value = float(denominator.strip())
            if denominator_value == 0:
                raise ValueError("坐标分母不能为 0")
            values.append(float(numerator.strip()) / denominator_value)
        else:
            values.append(float(part))
    return tuple(values)


def build_crop_expression(x, y, width, height, screen_width, screen_height):
    return (
        f"({int(x)} / {screen_width}, {int(y)} / {screen_height}, "
        f"{int(width)} / {screen_width}, {int(height)} / {screen_height})"
    )


def format_crop_expression(crop_text):
    if crop_text in (None, "", []):
        return "全屏"
    if isinstance(crop_text, str):
        return crop_text
    if isinstance(crop_text, (list, tuple)) and len(crop_text) == 4:
        return f"({crop_text[0]}, {crop_text[1]}, {crop_text[2]}, {crop_text[3]})"
    return str(crop_text)


def format_point_expression(point_text):
    if point_text in (None, "", []):
        return ""
    if isinstance(point_text, str):
        return point_text
    if isinstance(point_text, (list, tuple)) and len(point_text) == 2:
        return f"({point_text[0]}, {point_text[1]})"
    return str(point_text)


def normalize_text(text: str) -> str:
    """OCR 文本归一化：去空白、统一大小写，避免多余空格导致匹配失败。"""
    return re.sub(r"\s+", "", str(text or "")).lower()
