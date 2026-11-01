"""OneBot v11（NapCat / go-cqhttp / LLOneBot）私聊通知。"""
import base64
import io
import json
import time
import urllib.error
import urllib.request

from PIL import Image

from .config import SHOT_DIR


class OneBotNotifier:
    def __init__(self, cfg, log):
        self.cfg = cfg
        self.log = log

    def enabled(self):
        return bool(self.cfg.get("notify_enabled")) and bool(self.cfg.get("qq_target"))

    def _post(self, action, payload):
        base = str(self.cfg.get("onebot_url", "") or "").strip().rstrip("/")
        if not base:
            self.log("QQ 通知失败：未填写 OneBot API 地址")
            return False
        url = f"{base}/{action}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        token = str(self.cfg.get("onebot_token", "") or "").strip()
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", "ignore")
            try:
                result = json.loads(body)
                ok = result.get("status") in {"ok", "async"} or result.get("retcode") == 0
            except Exception:
                ok = True
            if not ok:
                self.log(f"QQ 通知失败：{body[:300]}")
            return ok
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            self.log(f"QQ 通知 HTTP {exc.code}：{detail}")
        except Exception as exc:
            self.log(f"QQ 通知失败：{exc}")
        return False

    def send_text(self, text):
        if not self.enabled():
            return False
        try:
            user_id = int(str(self.cfg.get("qq_target", "")).strip())
        except ValueError:
            self.log(f"QQ 通知失败：QQ 号格式不正确（{self.cfg.get('qq_target')}）")
            return False
        return self._post("send_private_msg", {
            "user_id": user_id,
            "message": [{"type": "text", "data": {"text": text}}],
        })

    def send_image(self, path, caption=""):
        if not self.enabled():
            return False
        try:
            user_id = int(str(self.cfg.get("qq_target", "")).strip())
        except ValueError:
            return False
        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((1280, 1280), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=85, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception as exc:
            self.log(f"QQ 图片读取失败：{exc}")
            return False

        message = []
        if caption:
            message.append({"type": "text", "data": {"text": caption}})
        message.append({"type": "image", "data": {"file": f"base64://{encoded}"}})
        ok = self._post("send_private_msg", {"user_id": user_id, "message": message})
        self.log(f"QQ 图片发送：{'成功' if ok else '失败'}（{path}）")
        return ok

    def send_signin(self, ok, text, shots):
        if not self.enabled():
            return
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        header = "✅ 星穹签到成功" if ok else "❌ 星穹签到失败"
        self.send_text(f"{header}\n时间：{now}\n{text}")
        if not self.cfg.get("send_screenshots", True):
            return
        if ok and shots.get("success"):
            self.send_image(shots["success"], "签到成功截图")
        elif shots.get("no_popup"):
            self.send_image(shots["no_popup"], "未发现签到弹窗截图")
        elif shots.get("failure"):
            self.send_image(shots["failure"], "签到失败截图")

    def send_daily(self, ok, text, image_path=None):
        if not self.enabled():
            return
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        header = "✅ 日常执行完成" if ok else "❌ 日常执行失败"
        self.send_text(f"{header}\n时间：{now}\n{text}")
        if self.cfg.get("send_screenshots", True) and image_path:
            self.send_image(image_path, "日常结束截图")

    def send_test(self):
        return self.send_text("星穹签到助手 · QQ 通知测试消息\n如果你收到这条消息，说明 OneBot 配置正确。")


def latest_shot(kind):
    """按修改时间取最近一张指定前缀的截图（备用）。"""
    try:
        files = sorted(SHOT_DIR.glob(f"{kind}_*.png"), key=lambda item: item.stat().st_mtime)
        return str(files[-1]) if files else None
    except Exception:
        return None
