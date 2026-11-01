# starrail-supply · 星穹签到助手

《崩坏：星穹铁道》列车补给自动领取工具。
<img width="1139" height="1139" alt="reward_qr" src="https://github.com/user-attachments/assets/6fb0ea9f-269a-48ee-976c-924ec8350e7f" />

> 仓库名：`starrail-supply` ｜ 仓库地址：<https://github.com/xingchen-0220/StarRail-supply> ｜ 完整介绍见 [REPO_INTRO.md](REPO_INTRO.md)。

基于**图像识别（OCR + 模板/文字定位 + 模拟鼠标点击）**，从开源项目
[March7thAssistant](https://github.com/moesnow/March7thAssistant) 中提取游戏启动与识别点击能力，
重新实现为一个独立、轻量的 Windows 小程序。

启动游戏 → 识别「点击进入」→ 识别「点击领取今日补给 / 今日奖励」→ 点击领取 → 关闭游戏，
并支持每天定时自动执行。

签到完成后可以执行日常：邮件 / 委托 / 清体力 / 支援 / 无名勋礼 / 每日实训 500，不需要任何外部程序。签到/日常结束时通过 QQ（OneBot v11）发送结果和截图。



## 功能

- **一键签到**：自动启动 `StarRail.exe`，等待标题界面，识别并点击「点击进入」，再识别并领取每日补给。
- **日常任务**：内置邮件、委托、清体力、支援战斗/奖励、无名勋礼、每日实训 500，不需要任何外部程序。
- **左下角步骤浮窗**：签到过程中在屏幕左下角显示 `1/7 → 7/7` 的实时步骤，鼠标可穿透、不抢游戏焦点。
- **QQ 通知**：OneBot v11 私聊，先发签到/日常成功或失败文字，再发对应截图。
- **关键截图**：签到成功瞬间、未发现签到弹窗、签到失败、日常结束。
- **自动更新**：启动时对比 GitHub 仓库最新版本，有新版本弹窗提示，可直接前往下载。
- **每日定时**：
  - 程序内定时（保持程序运行）；
  - Windows 计划任务（不需要保持程序运行，以最高权限执行）。
  - 两者互斥，创建计划任务后会自动关闭程序内定时，避免重复领取。
- **游戏路径自动检测**：支持注册表与常见安装目录，也可以手动选择 `StarRail.exe`。
- **运行日志**：实时日志与失败截图，方便排查识别问题。
- **现代化界面**：左侧导航（首页 / 日常任务 / QQ 通知 / 定时签到 / 运行日志 / 设置 / 关于）。

## 下载与使用

1. 打开右侧 **Releases**，下载最新的 `starrail-supply_vX.X.X.zip`，解压到任意目录；
   也可以直接下载单文件 `starrail-supply_vX.X.X.exe`。
2. 只双击 **`星穹签到助手.exe`** 运行；压缩包里没有、也不需要运行任何 `.bat` 文件。
   （GitHub 源码包不含 EXE，只有源码，需按下方“打包 EXE”自行构建。）
3. Windows UAC 弹窗点「是」。
   - 游戏 `StarRail.exe` 本身要求管理员权限；普通权限无法启动，模拟点击也会被 Windows 拦截。
4. 首次运行会自动检测 `StarRail.exe`；没有检测到就在「设置」里手动选择。
5. 先手动登录一次游戏（让启动器记住账号），然后关闭游戏。
6. 回到「首页」点 **立即签到**。签到成功后默认关闭游戏并退出程序。

> 游戏请使用「窗口化 / 无边框窗口」，窗口比例保持 16:9，推荐 1920×1080。

### 日常任务

打开「日常任务」页，勾选「签到成功后执行日常任务」：

- 邮件全部领取
- 委托奖励领取
- 拟造花萼「回忆之蕾」连续挑战，默认按剩余开拓力清空（最多 24 次/批）
- 使用支援角色完成战斗（同时完成支援任务）
- 支援奖励、无名勋礼（奖励页 + 任务页「一键领取」）
- 每日实训领取全部任务奖励 + 100/200/300/400/500 活跃度奖励

默认清空剩余开拓力（按当前开拓力计算挑战次数）；如果不想清空，可以在日常页取消「清空剩余开拓力」。不包含模拟宇宙/差分宇宙/货币战争等。

日常结束后，按「签到后关闭游戏」选项决定是否关闭游戏。

开启日常后，即使签到失败（例如没有弹窗、已领取），程序也会继续执行日常任务；签到和日常的结果会分别通知。


### QQ 通知（OneBot v11）

1. 打开「QQ 通知」页，勾选「启用 QQ 通知」。
2. 填写 OneBot API 地址，例如 `http://127.0.0.1:3000`。
3. 如果机器人设置了 Access Token，一并填写。
4. 目标 QQ 号填你自己的 QQ，机器人会私聊发送。
5. 点「发送测试消息」确认能收到，再保存。

流程会先发文字，再发截图：

- 签到成功 → 「✅ 星穹签到成功」+ 成功瞬间截图；
- 未发现签到弹窗（已领取/无月卡）→ 「❌ 星穹签到失败」+ 该窗口截图；
- 签到失败 → 「❌ 星穹签到失败」+ 失败截图；
- 日常结束 → 「✅ 日常执行完成」或「❌ 日常执行失败」+ 日常结束截图。

### 自动更新

程序启动 2.5 秒后会在后台检查 GitHub 仓库版本：

- 优先读取仓库的 **Latest Release**（`tag_name`）；
- 如果还没有 Release 或 API 不可用，则读取仓库根目录的 `version.json`；
- 发现比当前版本更新的版本时，弹出「发现新版本」窗口，显示更新内容和下载/Release 按钮；
- 「关于」页也有「检查更新」按钮，可手动检查；
- 在「设置」里可以关闭「启动时检查 GitHub 更新」；
- 弹窗里勾选「跳过此版本」后，启动时不再提示该版本。

发布新版本时，记得同时更新根目录的 `version.json`（`version`、`notes`、`url`），并打对应的 tag。

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
│  ├─ signin.py         签到流程（含成功/未弹窗/失败截图）
│  ├─ flow.py           签到 → 通知 → 日常 → 关闭游戏 总流程
│  ├─ daily_native.py   内置日常（邮件/每日实训/委托）
│  ├─ notifier.py       OneBot v11 QQ 通知
│  ├─ updater.py        GitHub 版本检查
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
├─ version.json         更新检查用的版本信息
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

**日常任务没有执行？**
请确认游戏在 16:9 / 1920×1080 下运行；如果菜单布局变化，可能需要更新识别素材。

**QQ 收不到消息？**
先点「发送测试消息」。检查 OneBot HTTP 服务是否启动、地址/Token 是否正确、目标 QQ 号是否为数字；NapCat / go-cqhttp 需要开启 HTTP 服务端。

**检查更新失败？**
访问 GitHub 需要网络；如果 Release API 不可用，程序会尝试读取 `version.json`。也可以直接打开仓库 Releases 页面手动下载。

## 支持作者

**觉得好用就支持一下呗！**

- 作者：梦和星辰
- B站UID：1321645331
- B站主页：<https://space.bilibili.com/1321645331>

<img width="1180" height="780" alt="screenshot" src="https://github.com/user-attachments/assets/e19dfe72-8bcb-4079-a972-f33f572d5e50" />

## 开源协议与致谢

本项目的流程思路、图像识别与游戏启动方式参考自
[moesnow/March7thAssistant](https://github.com/moesnow/March7thAssistant)（GPL-3.0），
因此本项目同样以 **GPL-3.0** 发布，完整协议见 [LICENSE](LICENSE)。

- 原项目：https://github.com/moesnow/March7thAssistant
- OCR：RapidOCR（PaddleOCR 模型的 ONNX 实现）
- 界面：Python tkinter

请遵守游戏用户协议，使用脚本的风险由使用者自行承担。




