# 更新日志

版本号对应仓库的 git tag，发布包在 [Releases](https://github.com/yangt16/BJTU-tronclass-downloader/releases) 页面。

---

## 未发布（目录整理）

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
