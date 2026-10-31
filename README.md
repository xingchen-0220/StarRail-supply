# starrail-supply · 星穹签到助手

《崩坏：星穹铁道》列车补给自动领取工具。

> 仓库名：`starrail-supply` ｜ 仓库地址：<https://github.com/xingchen-0220/StarRail-supply> ｜ 完整介绍见 [REPO_INTRO.md](REPO_INTRO.md)。

基于**图像识别（OCR + 模板/文字定位 + 模拟鼠标点击）**，从开源项目
[March7thAssistant](https://github.com/moesnow/March7thAssistant) 中提取游戏启动与识别点击能力，
重新实现为一个独立、轻量的 Windows 小程序。

启动游戏 → 识别「点击进入」→ 识别「点击领取今日补给 / 今日奖励」→ 点击领取 → 关闭游戏，
并支持每天定时自动执行。




## 功能

- **一键签到**：自动启动 `StarRail.exe`，等待标题界面，识别并点击「点击进入」，再识别并领取每日补给。
- **左下角步骤浮窗**：签到过程中在屏幕左下角显示 `1/7 → 7/7` 的实时步骤，鼠标可穿透、不抢游戏焦点。
- **每日定时**：
  - 程序内定时（保持程序运行）；
  - Windows 计划任务（不需要保持程序运行，以最高权限执行）。
  - 两者互斥，创建计划任务后会自动关闭程序内定时，避免重复领取。
- **游戏路径自动检测**：支持注册表与常见安装目录，也可以手动选择 `StarRail.exe`。
- **运行日志**：实时日志与失败截图，方便排查识别问题。


## 下载与使用

1. 打开右侧 **Releases**，下载最新的 `星穹签到助手_vX.X.X.zip`，解压到任意目录。
2. 双击 `星穹签到助手.exe`，Windows UAC 弹窗点「是」。
   - 游戏 `StarRail.exe` 本身要求管理员权限；普通权限无法启动，模拟点击也会被 Windows 拦截。
3. 首次运行会自动检测 `StarRail.exe`；没有检测到就在「设置」里手动选择。
4. 先手动登录一次游戏（让启动器记住账号），然后关闭游戏。
5. 回到「首页」点 **立即签到**。签到成功后默认关闭游戏并退出程序。

> 游戏请使用「窗口化 / 无边框窗口」，窗口比例保持 16:9，推荐 1920×1080。

### 定时签到

- **程序内定时**：定时签到页 →「设置定时…」→ 勾选启用、选择时间与星期 → 保存。程序需要保持运行。
- **Windows 计划任务**：设置好时间后点「创建计划任务」。程序不在运行也会执行；创建后程序内定时会自动关闭。
- 修改任务时间：先点「删除计划任务」，改好时间后再重新创建。

## 从源码运行

环境：Windows 10/11、Python 3.12。

```bat
git clone https://github.com/xingchen-0220/StarRail-supply.git
cd starrail-supply
python -m pip install -r requirements.txt
python main.py
```

依赖：`opencv-python`、`numpy`、`pillow`、`mss`、`pywin32`、`rapidocr-onnxruntime`。

## 打包 EXE

```bat
.\build.ps1
```

脚本会调用 PyInstaller，生成 `dist\星穹签到助手.exe`（约 100 MB，内置 OCR 模型，含管理员清单）。
打包配置见 `build.spec`。

## 项目结构

```
starrail-supply/
├─ main.py              入口（GUI / --auto 计划任务模式）
├─ app/
│  ├─ gui.py            左侧导航界面
│  ├─ signin.py         固定签到流程
│  ├─ vision.py         截图、OCR、模板匹配、点击
│  ├─ ocr_engine.py     RapidOCR 封装
│  ├─ winapi.py         Windows 窗口 / 键鼠输入
│  ├─ launcher.py       游戏路径检测与启动
│  ├─ overlay.py        左下角步骤浮窗
│  ├─ config.py         配置
│  └─ logger.py         日志
├─ assets/              图标、赞赏码
├─ docs/                界面截图
├─ tools/selftest_flow.py  假窗口端到端自测
├─ REPO_INTRO.md        完整仓库介绍
├─ build.spec / build.ps1
├─ requirements.txt
└─ LICENSE
```

## 常见问题

**启动游戏报 `WinError 740`？**
本程序没有以管理员身份运行。右键 → 以管理员身份运行。

**一直等「点击进入」？**
游戏还在加载/更新，或账号未登录。查看 `data\logs` 与 `data\screenshots` 下的失败截图。

**点击没反应 / 截图是黑的？**
游戏改成了独占全屏，或本程序与游戏权限不一致。改成无边框窗口，并确认程序以管理员运行。

**计划任务没有执行？**
在任务计划程序里查看 `星穹签到助手-每日签到` 的「上次运行结果」；修改时间需要先删除任务再创建。

## 支持作者

**觉得好用就支持一下呗！**

- 作者：梦和星辰
- B站UID：1321645331
- B站主页：<https://space.bilibili.com/1321645331>

<img width="1139" height="1139" alt="reward_qr" src="https://github.com/user-attachments/assets/74b904c4-d395-48c4-8460-94a5eb6982c3" />


## 开源协议与致谢

本项目的流程思路、图像识别与游戏启动方式参考自
[moesnow/March7thAssistant](https://github.com/moesnow/March7thAssistant)（GPL-3.0），
因此本项目同样以 **GPL-3.0** 发布，完整协议见 [LICENSE](LICENSE)。

- 原项目：https://github.com/moesnow/March7thAssistant
- OCR：RapidOCR（PaddleOCR 模型的 ONNX 实现）
- 界面：Python tkinter

请遵守游戏用户协议，使用脚本的风险由使用者自行承担。


