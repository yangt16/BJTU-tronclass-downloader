# 课程回放下载器

[![CI](https://github.com/yangt16/BJTU-tronclass-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/yangt16/BJTU-tronclass-downloader/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

把 TronClass 的课堂回放**批量下载到本地**，并自动抽出音轨（`mp4` + `m4a`）。

> 用途很窄：**只负责拿到文件**。转写、总结、考点提取都不在这个程序里。

**完整使用手册 → [`docs/使用说明.md`](docs/使用说明.md)**

---

## 能做什么

| 能力 | 说明 |
|---|---|
| **一科一个清单** | `lists\XX课程.txt` → 落到 `media\XX课程\`，清单名即课程名 |
| **增量下载** | 重跑时本地已有的节**整节跳过**：不联网探测、不重抽音轨 |
| **进度与日志** | 每节结束报进度和预计剩余时间；可把输出写进日志文件 |
| **按日期/星期筛选** | 输入日期或星期几（`4`=周四），只下要的那几节 |
| **并发下载** | `--jobs` 1–4 路（默认 2），实测 4 路约 2.7 倍速 |
| **单节加速** | `--segments` 把一个文件拆 4/8 段并发下，只补一两节时快 2–4 倍 |
| **跑前统计 + 完成提示** | 先报“已下载 N 节 / 实际需下载 M 节”；跑完响铃；失败节写入 `logs\failed_*.txt` |
| **下载前确认** | 批量开始前列出每门课的规则；每份清单下载前显示实际节数，输入 y 才开始（`--yes` 跳过） |
| **下载台账** | 记录下过的节；删了文件再跑也不会重下（`--redownload` 可强制重下） |
| **下载校验** | 下完用 ffprobe 校验时长；坏文件自动删除并重试 |
| **并发每节进度** | 并发下载时也能看到每节百分比：`[2/6] 20261104_… 45% 35/78 MB` |
| **下载报告** | 结束时汇总本次大小/用时/平均速度，例：`[报告] 新下载 3 节 · 录像 4200 MB + 音轨 330 MB · 平均 2.4 MB/s` |
| **批量全局进度** | 多份清单连跑时统一算剩余时间：`[batch] 全局 3/12 节 已用 … 预计剩余 …` |
| **归档/日志清理** | `tools\clean_archive.py`：按天数/数量预览或删除旧归档与日志 |
| **按课程规则** | 每门课可单独设"只下周四 / 排除周二 / 只要音频"（`2-清单规则.cmd` 配置），批量时各按各的规则跑 |
| **一键抓整门课** | 浏览器里点一下书签，整门课 20+ 节地址一次导出 |
| **间接地址自动换直链** | 清单里可以直接写 `previewToken` 地址，下载时自动换成签名直链 |
| 断点续传 | 中断后重跑，从断点继续，不重下 |
| 自动抽音轨 | 音频流**直接复制**成 m4a，零重编码、零音质损失 |
| 自动命名 | `<课程>_<日期>.mp4/.m4a`，一天多节时自动带时段 |
| 下载前预检 | 先验链接是否过期，避免跑到一半才 403 |
| 可搬移 | 整个文件夹搬到任意路径/盘符都能跑 |
| 零第三方依赖 | 只用 Python 标准库 + ffmpeg |

---

## 部署（拿到程序）

### 方式 1：Release 包（不用命令行的同学）

打开 [Releases](https://github.com/yangt16/BJTU-tronclass-downloader/releases/latest)，按平台下载：

| 平台 | 文件 | 大小 | 拿到后 |
|---|---|---|---|
| Windows | `tronclass-downloader-<版本>-win64.zip` | 约 75 MB | 解压 → 双击 `0-首次安装.cmd`（ffmpeg 已内置，秒过） |
| macOS / Linux | `tronclass-downloader-<版本>-mac.zip` | 约 0.1 MB | 先 `brew install ffmpeg python3`，再 `chmod +x *.command tools/*.sh && ./0-首次安装.command` |

> 文件名里的版本号以 Releases 页为准，始终下载**最新版**。

### 方式 2：有 Git，一行命令（Windows）

```bat
git clone --depth 1 https://github.com/yangt16/BJTU-tronclass-downloader.git && cd BJTU-tronclass-downloader && .\0-首次安装.cmd
```

### 方式 3：没有 Git（Windows）

仓库页 → `Code` → `Download ZIP` → 解压 → 双击 `0-首次安装.cmd`
（这个包不含 ffmpeg，setup 会下载约 200 MB）。

### 方式 4：macOS / Linux（用 Git）

```sh
git clone --depth 1 https://github.com/yangt16/BJTU-tronclass-downloader.git
cd BJTU-tronclass-downloader
brew install ffmpeg python3       # Linux: sudo apt install ffmpeg python3
chmod +x *.command tools/*.sh           # 从 ZIP 解压时需要
./0-首次安装.command
```

之后在 Finder 里双击 `.command` 文件即可。

**前置条件**：Python 3.8+。
Windows 的 ffmpeg 由 `0-首次安装.cmd` 自动下载；macOS / Linux 用包管理器装。

---

## 快速开始

### 1. 建清单

在 `lists\` 里建一个以课程名命名的 txt：

```text
D:\course-notes\lists\XX课程.txt
```

一行一个播放地址（`#` 开头是注释）。地址怎么拿，见使用说明的
[手动版](docs/使用说明.md#手动版自己粘地址) 或
[自动版（书签）](docs/使用说明.md#自动版书签一次抓一门课)。

### 2. 双击开始下载

Windows 双击 `1-开始下载.cmd`，macOS / Linux 双击 `1-开始下载.command`。
会先问四个问题（**直接回车 = 默认**），随后列出每门课规则和本次实际节数，输入 **y** 才开始：

```text
产物：1) 视频 + 音频 [默认]   2) 只要音频   3) 只要视频
范围：1) 下载全部 [默认]      2) 只下某一天  3) 只下星期几  4) 排除星期几
并发：1 路 / 2 路 [默认] / 3 路 / 4 路
单节加速：关闭 [默认] / 4 段 / 8 段（只补一两节时用）
（菜单会记住上次选择，下次直接回车沿用；`python tools\menu.py --forget` 清除）
（下载前会先列出每门课的规则和本次实际节数，输入 y 才开始；`--yes` 跳过）
```

| 选择 | 产物 | 单节占用 |
|---|---|---|
| 视频 + 音频（默认） | mp4 + m4a | ~750 MB |
| 只要音频 | 只留 m4a | ~110 MB |
| 只要视频 | 只留 mp4 | ~640 MB |

范围选 2/3/4 时会再问一次输入：日期（`20261030`）或星期几（`1`=周一 … `7`=周日，
`2,4` 表示多个）。连按**四**次回车 = 四问全默认（视频 + 音频、下全部、2 路、单节加速关）。

> **不想把清单放进 `lists\`？** 直接把抓取导出的 txt **拖到入口图标上**即可运行：
> 把 txt 和 `.cmd` 并排显示，左手按住 txt 拖到 `1-开始下载.cmd` 上松手。
> 文件名就是课程名，决定 `media\<课程名>\`；跑完 txt 会**移进** `har_archive\`
> （原位置消失）。文件名带浏览器重名后缀（如 ` (1)`）会自动去掉。等价命令：
>
> ```bat
> 1-开始下载.cmd "D:\Downloads\XX课程.txt"
> ```

### 3. 产物

```text
media\XX课程\20260921\
├─ XX课程_20260921.mp4    1000.2 MB   录像
└─ XX课程_20260921.m4a     111.5 MB   音轨  ← 转写用这个
```

跑完会自动归档清单（`lists\` 里不再留 txt）、刷新已下载索引 `lists\XX课程.md`。

---

## 自动抓取（可选，省事很多）

手动一节节复制地址，20 节要点 20 次。装一次书签后**每门课点一下就导出整门课**：

1. 打开 `dist\install.html`
2. 装书签：
   - **Edge / Firefox**：把页面里那个蓝色按钮**拖到书签栏**
   - **Chrome**：拖拽容易丢 `javascript:` 前缀，改用导入 ——
     打开 `chrome://bookmarks` → 右上 `⋮` → **导入书签** → 选 `dist\bookmarks.html`
3. 打开课程的「直播」列表页 → 点一下书签 → 清单自动下载
4. 把下载的 txt 放进 `lists\\`（或直接拖到入口图标上），双击入口；跑完 txt 自动归档

原理与接口细节见 [使用说明 · 自动版](docs/使用说明.md#自动版书签一次抓一门课)。

---

## 依赖

| 依赖 | 状态 |
|---|---|
| Python 3.8+ | 需要。探测顺序：`python\python.exe` → PATH 的 `python` → `py -3`（macOS/Linux 先找 `python3`） |
| ffmpeg | Windows：双击 `0-首次安装.cmd` 自动下载（约 200 MB，装进 `bin\`）；macOS/Linux：`brew install ffmpeg` / `apt install ffmpeg` |
| 网络 | 能直连校内 TronClass，不需要 VPN |

> 第一次用（或换了新机器）：双击 **`0-首次安装.cmd`**（macOS：`./0-首次安装.command`）——
> 它会找 Python、确认 ffmpeg、建好 `lists\`。

程序用自身所在目录做根目录，整个文件夹可搬到任意位置。

---

## 目录结构（精简）

```text
D:\course-notes\
├─ 0-首次安装.cmd            ★ 首次使用（Windows）：补齐 ffmpeg + 建 lists\
├─ 1-开始下载.cmd             ★ 下载入口：弹菜单选产物和范围
├─ 2-清单规则.cmd             ★ 按课程配置下载规则（只下某天/星期几）
├─ 0-首次安装.command         ★ 同上（macOS / Linux）
├─ 1-开始下载.command          ★ 同上（macOS / Linux）
├─ 2-清单规则.command          ★ 同上（macOS / Linux）
├─ docs\使用说明.md           完整使用手册
├─ LICENSE                    MIT 许可证
├─ CHANGELOG.md               版本更新日志
├─ bin\                       ffmpeg / ffprobe
├─ tools\                     36 个脚本（下载、编排、抓取、测试）
│  ├─ getlec.cmd / getlec.sh  主脚本（各入口都调用它）
│  └─ ...                     其余工具与测试
├─ dist\                      抓取书签（install.html / bookmarks.html）
├─ lists\                     ★ 放抓取清单；跑完归档，只留 <课程>.md
├─ media\                     ★ 下载产物
├─ har_archive\               历史清单归档
├─ release\                   发布包产物（构建生成，不入库）
└─ tmp\                       临时目录
```

完整清单见 [使用说明 · 目录结构](docs/使用说明.md#目录结构)。

---

## 已知限制

| 限制 | 说明 |
|---|---|
| 手动版要自己拿 URL | 播放地址由服务端签名（`ts`+`token`），程序无法自己生成；用书签自动抓可省掉 |
| URL 有时效 | 实测 1 小时以上仍可用，但别放到第二天 |
| 抓取需要浏览器登录态 | 书签只能在已登录的页面里点；程序不碰账号密码 |
| 只支持三条轨 | 平台只提供 `ENCODER` / `INSTRUCTOR` / `STUDENTS` |
| 没有内置 Python | 依赖系统已有 Python；想零依赖就把免安装版解压到 `python\` |

---

## 文档索引

| 文档 | 内容 |
|---|---|
| [`docs/使用说明.md`](docs/使用说明.md) | 完整手册（含 macOS 用法）：手动/自动取地址、三种模式、输出规则、增量、命令速查、故障排查、测试、设计说明 |
| [`CHANGELOG.md`](CHANGELOG.md) | 各版本更新内容 |
| `tools/*.py` 文件头 | 各脚本职责与参数 |

---

## 免责声明

- 仅用于**个人学习**：下载自己有权访问的课程内容。
- 程序不处理、不存储任何账号密码；抓取只在你自己已登录的浏览器里执行。
- 下载的文件保存在本地 `media\`，请勿公开传播课程内容。

## 许可证

代码以 [MIT 许可证](LICENSE) 发布，可自由使用、修改、分发（保留版权声明）。

发布包内附的 ffmpeg 是独立的第三方程序，按其自身许可证（GPLv3）分发，
详见发布包内的 `LICENSE-ffmpeg.txt` 与 `COPYING.GPLv3.txt`。
