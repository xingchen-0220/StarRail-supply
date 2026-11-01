"""GitHub 更新检查：优先 Release API，失败时读取仓库 version.json。"""
import json
import re
import time
import urllib.error
import urllib.request

REPO = "xingchen-0220/StarRail-supply"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/main/version.json"
RELEASE_URL = f"https://github.com/{REPO}/releases/latest"
USER_AGENT = "starrail-supply-updater"


def version_tuple(text):
    value = str(text or "").strip().lower().lstrip("v")
    value = value.split("-")[0].split("+")[0]
    parts = []
    for item in value.split("."):
        match = re.match(r"\d+", item)
        parts.append(int(match.group()) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(latest, current):
    return version_tuple(latest) > version_tuple(current)


def _get_json(url, timeout=6):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def check_for_update(current_version, api_url=API_URL, version_url=VERSION_URL, timeout=6):
    """返回更新信息 dict；已是最新则返回 None；全部请求失败抛 RuntimeError。"""
    errors = []
    try:
        data = _get_json(api_url, timeout=timeout)
        tag = str(data.get("tag_name", "")).strip()
        if tag:
            assets = data.get("assets") or []
            download = ""
            for asset in assets:
                name = str(asset.get("name", "")).lower()
                if name.endswith(".zip") or name.endswith(".exe"):
                    download = asset.get("browser_download_url", "")
                    break
            latest = tag.lstrip("v")
            return {
                "latest": latest,
                "current": current_version,
                "notes": data.get("body") or "（该版本没有填写更新说明）",
                "url": data.get("html_url") or RELEASE_URL,
                "download": download,
                "is_new": is_newer(latest, current_version),
                "source": "GitHub Release",
            }
        errors.append("Release 数据缺少 tag_name")
    except Exception as exc:
        errors.append(f"Release API: {exc}")

    try:
        url = f"{version_url}?t={int(time.time())}"
        data = _get_json(url, timeout=timeout)
        latest = str(data.get("version", "")).strip().lstrip("v")
        if latest:
            return {
                "latest": latest,
                "current": current_version,
                "notes": data.get("notes") or "（该版本没有填写更新说明）",
                "url": data.get("url") or RELEASE_URL,
                "download": data.get("download") or "",
                "is_new": is_newer(latest, current_version),
                "source": "version.json",
            }
        errors.append("version.json 缺少 version 字段")
    except Exception as exc:
        errors.append(f"version.json: {exc}")

    raise RuntimeError("；".join(errors))
