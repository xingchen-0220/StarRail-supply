"""星穹签到助手入口：图形界面 / 自动签到（计划任务）。"""
import argparse
import sys


def build_parser():
    parser = argparse.ArgumentParser(
        prog="星穹签到助手",
        description="启动《崩坏：星穹铁道》，识别并点击「点击进入 → 领取今日奖励」，完成后关闭游戏。",
    )
    parser.add_argument("--auto", action="store_true", help="无界面执行一次签到（供计划任务调用）")
    parser.add_argument("--no-overlay", action="store_true", help="自动签到时不在左下角显示步骤浮窗")
    parser.add_argument("--demo-overlay", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="store_true", help="显示版本")
    parser.add_argument("--selftest-ocr", action="store_true", help=argparse.SUPPRESS)
    return parser


def auto_signin(show_overlay=True):
    from app import winapi
    from app.config import cfg
    from app.logger import AppLog

    winapi.set_dpi_aware()
    log = AppLog()
    cfg.load()
    log("===== 自动签到开始 =====")
    ok = False
    try:
        if show_overlay:
            try:
                from app.gui import run_auto_with_overlay

                ok = run_auto_with_overlay(log)
            except Exception as exc:
                log(f"浮窗不可用（{exc}），改为无界面执行")
                from app.signin import SigninRunner

                ok = SigninRunner(cfg, log).run()
        else:
            from app.signin import SigninRunner

            ok = SigninRunner(cfg, log).run()
    except Exception as exc:
        import traceback

        log(f"签到异常：{exc}")
        log(traceback.format_exc())
    log("===== 自动签到成功 =====" if ok else "===== 自动签到失败 =====")
    return 0 if ok else 1


def ocr_selftest():
    """无游戏环境下验证 OCR 模型可用（打包后自检用）。"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from app.config import DATA_DIR
    from app.ocr_engine import OcrEngine

    image = Image.new("RGB", (640, 220), (28, 30, 36))
    draw = ImageDraw.Draw(image)
    font = None
    for name in ("msyh.ttc", "simhei.ttf", "simsun.ttc"):
        try:
            font = ImageFont.truetype(rf"C:\Windows\Fonts\{name}", 44)
            break
        except Exception:
            continue
    draw.text((30, 40), "点击进入", font=font, fill=(240, 240, 240))
    draw.text((30, 130), "点击领取今日补给", font=font, fill=(240, 240, 240))
    lines = OcrEngine(0.3).recognize(np.array(image))
    report = "\n".join(f"{text}\t{score:.3f}" for _, _, _, _, text, score in lines)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "ocr_selftest.txt").write_text(report, encoding="utf-8")
    ok = any("点击进入" in text for _, _, _, _, text, _ in lines)
    print(report)
    return 0 if ok else 1


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.selftest_ocr:
        sys.exit(ocr_selftest())
    if args.version:
        from app.config import APP_VERSION

        print(APP_VERSION)
        return
    if args.demo_overlay:
        from app.gui import run_demo_overlay

        run_demo_overlay()
        return
    if args.auto:
        sys.exit(auto_signin(show_overlay=not args.no_overlay))

    from app.gui import run_gui

    run_gui()


if __name__ == "__main__":
    main()
