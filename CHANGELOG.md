# 更新日志

版本号对应仓库的 git tag，发布包在 [Releases](https://github.com/yangt16/BJTU-tronclass-downloader/releases) 页面。

---

## 未发布

### 新增
- **并发下载**：`--jobs N` / `GETLEC_JOBS`（默认 2、上限 4），菜单里也能选；
  实测 4 路约 2.7 倍速
- **开跑前预扫描**：先统计已下载的节，打印
  `[skip] 已下载 N 节，本次实际需下载 M 节`，进度/ETA 只按实际要下的算
- **跑完提示**：终端响铃 + Windows 提示音 / macOS beep
- **失败清单文件**：失败节写入 `logs/failed_<课程>_<时间>.txt`
- **单文件多连接分段下载**：`--segments N` / `GETLEC_SEGMENTS`（默认关闭），
  菜单里可选"4 段"；同一个文件拆段并发下，下完即完整文件，
  断点记录在 `*.segstate`（下完自动删）；与节级并发组合时总连接数 ≤ 8
- **单入口 + 中文菜单**：根目录只剩 `1-开始下载.cmd` / `.command`，双击后按菜单选
  产物（视频+音频 / 只要音频 / 只要视频）、范围（全部 / 某一天 / 星期几 / 排除星期几）
  和并发路数；
  直接回车 = 默认，拖 txt 到图标上则跳过菜单直接跑
- **只下星期几**：菜单里可选"只下星期几 / 排除星期几"（1=周一 … 7=周日），
  也支持 `--only 4` / `--exclude 2` 命令行写法

---

## v3.3 — 2026-11-19

### 变更
- 入口文件加数字前缀，顺序即操作顺序：
  - `setup.cmd` → `0-首次安装.cmd`（macOS 同名 `.command`）
  - `下视频和音频` → `1-下视频和音频`
  - `只要音轨` → `2-只要音轨`
  - `只要视频` → `3-只要视频`
  - `只下某一天` → `4-只下某一天`
- `getlec.cmd` / `getlec.sh` 移入 `tools\`（普通用户不需要直接调用）

### 新增
- **失败节自动重试**：一轮结束后自动再试一次失败的节，仍失败才报错
- **下载集成测试** `tools/test_download.py`：本地假 HTTP 服务器，
  覆盖完整下载、断点续传、500 重试、忽略 Range、403、302 resolve（12 项）
- CI 增强：Windows/macOS 入口脚本真机冒烟（dry-run）、Linux 3.8/3.11 矩阵、
  集成测试纳入三个平台
- **整体进度 + 预计剩余时间**：每节结束打印 `[进度] 3/7 节 已用 ... 预计剩余 ...`
- **日志文件**：`GETLEC_LOG=1` 或 `--log <目录>`，输出同时写进
  `logs/<课程名>_<时间>.log`
- CI actions 升级到 `checkout@v6` / `setup-python@v6`（消除 Node 20 弃用警告）
- **不再扫描用户目录**：移除 `import_lists.py`，程序不碰「下载」「桌面」
  清单由用户放进 `lists\` 或直接拖到入口图标上
- **清单跑完即归档**：归档到 `har_archive\` 后不再重建空模板，
  `lists\` 里只保留 `<课程>.md` 索引
- 新增 `tools/test_archive.py`（8 项）：归档移走、不重建模板、重复日期不覆盖
- **重名后缀清理**：清单文件名带 `(1)` 时，自动去掉再作为课程名与文件夹名

### 说明
- 用户操作不变：仍是双击编号入口
- 高级用法路径变化：`tools\getlec.cmd lists\XX课程.txt INSTRUCTOR`
- 各入口与 CI、测试、文档已同步更新

---

## v3.2 — 2026-11-19

### 新增
- `dist/bookmarks.html`：Chrome 用「导入书签」装抓取脚本
  （拖拽会丢 `javascript:` 前缀，点击会跳网页）
- Chrome / Edge 导入书签的图文步骤（`dist/install.html`）

### 修复
- README 部署表的包名和大小与实际发布不一致
- 补充 macOS 首次运行说明：不要粘贴脚本内容（zsh 历史展开报错）、
  Gatekeeper 拦截的三种处理方式

### 文档
- README 部署章节改为双平台表格

---

## v3.1 — 2026-11-19

### 新增
- **macOS / Linux 支持**
  - `getlec.sh`（主脚本，与 `getlec.cmd` 同逻辑）
  - `setup.command`（首次设置：找 python3、检查 ffmpeg、建 lists/）
  - `下视频和音频.command` / `只要音轨.command` / `只要视频.command` / `只下某一天.command`
- `tools/test_shell.py`：shell 入口静态检查（shebang / LF / 可执行位）
- 发布包支持 `--platform mac`（不含 ffmpeg，靠 brew 安装）

### 修复
- `lectures.py` 缺 ffmpeg 时给出可操作提示，不再抛 FileNotFoundError
- 更正"本机 SChannel 坏了"的误判（实为开发沙箱限制）

### 变更
- `.gitattributes` 固定 `*.sh` / `*.command` 为 LF

---

## v3 — 2026-11-12

### 新增
- `setup.cmd` + `tools/fetch_ffmpeg.py`：新机器一键补齐 ffmpeg（BtbN → gyan 双源）
- `只下某一天.cmd` + `--only` / `--exclude`：按日期筛选，不用手动删清单
- 发布包构建脚本 `tools/build_release.py`（Windows 版内置 ffmpeg）

### 变更
- 测试去掉硬编码路径，整个文件夹搬到哪都能跑
- README 与使用说明拆分（`docs/使用说明.md`）

---

## v2.1 — 2026-11-11

### 新增
- `下视频和音频.cmd` / `只要音轨.cmd` / `只要视频.cmd` 三个入口
  - `already_done()` 按模式判断"是否已完成"

### 修复
- 按「日期+时段」分组，不再按完整目录
  （同一节课的三条轨可能在不同目录，按目录分会被拆成两组）

---

## v2 — 2026-11-11

### 新增
- **自动化抓取**：书签脚本一次导出整门课地址
  - 实测链路：列表接口 → 每节详情 → `previewToken` → 302 → 签名直链
  - 只有前两步需要登录态，其余本地完成
- `get_media.resolve()`：`previewToken` 地址自动换成签名直链
- `tools/import_lists.py`：自动收编浏览器下载的清单
- **增量下载**：已下载的节整节跳过（不联网、不重抽音轨）
- `--force` / `--keep-list`、预检跳过已下载的节

---

## v1 — 2026-11-11

首个可运行版本：

- `lists/<课程名>.txt` → `media/<课程名>/`
- HTTP Range 分块下载 + 断点续传
- `ffmpeg -vn -c:a copy` 零重编码抽音轨
- 自动命名（`<课程>_<日期>`，一天多节带时段）、自动归档、自动索引
- 下载前预检
