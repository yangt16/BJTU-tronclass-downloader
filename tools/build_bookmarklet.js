/**
 * build_bookmarklet.js - 把 scrape_course.js 编译成书签，并生成安装页。
 *
 * 产出:
 *   dist/bookmarklet.txt   一行 javascript: 地址（可直接粘贴到书签 URL）
 *   dist/install.html      打开后把一个按钮拖到书签栏即可安装
 *
 * 用法: node tools/build_bookmarklet.js
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SRC = path.join(ROOT, 'tools', 'scrape_course.js');
const DIST = path.join(ROOT, 'dist');

let code = fs.readFileSync(SRC, 'utf8');

// 去掉文件头部的大段注释（书签里不需要，能省不少体积）
code = code.replace(/^\/\*\*[\s\S]*?\*\/\s*/, '').trim();

// bookmarklet 必须是单行 javascript: 地址；整体编码最稳
const url = 'javascript:' + encodeURIComponent(code)
  // 这两个字符在 HTML 属性里也安全，但统一编码更省心
  .replace(/'/g, '%27')
  .replace(/!/g, '%21');

fs.mkdirSync(DIST, { recursive: true });
fs.writeFileSync(path.join(DIST, 'bookmarklet.txt'), url + '\n', 'utf8');

// Chrome 里拖拽 javascript: 链接经常丢协议头或被拦；改成"导入书签文件"最稳。
// 这是 Netscape 书签格式，Chrome / Edge / Safari 都认。
const bookmarksHtml = `<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="${url}" ADD_DATE="${Math.floor(Date.now()/1000)}">抓取课程清单</A>
</DL><p>
`;
fs.writeFileSync(path.join(DIST, 'bookmarks.html'), bookmarksHtml, 'utf8');

const html = `<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<title>安装「抓取课程清单」书签</title>
<style>
  body{font:16px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#1f2328;background:#fff}
  h1{font-size:24px;margin-bottom:.2em}
  .sub{color:#57606a;margin-top:0}
  ol{padding-left:1.4em}
  li{margin:.5em 0}
  .bm{display:inline-block;margin:24px 0;padding:14px 28px;background:#0969da;color:#fff;border-radius:8px;
      text-decoration:none;font-weight:600;font-size:18px;box-shadow:0 2px 6px rgba(9,105,218,.3)}
  .bm:hover{background:#0550ae}
  kbd{background:#f6f8fa;border:1px solid #d0d7de;border-bottom-width:2px;border-radius:5px;padding:1px 6px;font-size:90%}
  .note{background:#fff8c5;border:1px solid #d4a72c66;border-radius:8px;padding:12px 16px;margin:20px 0}
  .warn{background:#ffebe9;border:1px solid #ff818266}
  code{background:#f6f8fa;padding:1px 5px;border-radius:4px;font-size:90%}
</style>

<h1>安装「抓取课程清单」书签</h1>
<p class="sub">装一次，以后每门课点一下就导出整门课的回放地址。</p>

<ol>
  <li>先显示书签栏：按 <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>B</kbd>（或 Edge 菜单 → 收藏夹 → 显示收藏夹栏）</li>
  <li>把下面这个蓝色按钮 <b>拖到书签栏</b>（不是点击它）</li>
  <li>拖上去后右键改名为「抓取课程清单」</li>
</ol>

<a class="bm" href="${url}">抓取课程清单</a>

<div class="note">
  <b>怎么用：</b><br>
  1. 打开某门课的「直播」列表页（地址里有 <code>/course/数字/live-activities</code>）<br>
  2. 点一下书签栏里的「抓取课程清单」<br>
  3. 按弹框提示填课程名、选是否导出三条轨（选取消 = 只导 ENCODER）<br>
  4. 浏览器会下载 <code>&lt;课程名&gt;.txt</code><br>
  5. 双击课程下载器的 <code>1-开始下载.cmd</code>，按菜单选产物、范围、并发和单节加速；
  确认规则和本次节数后按 <code>y</code> 开始<br>
  6. （可选）要按课程区分范围/产物时，双击 <code>2-清单规则.cmd</code> 配置一次
</div>

<div class="note warn">
  <b>注意：</b>必须在已登录的课程页面里点，书签要借用你的登录态调接口。脚本不会读取或上传任何账号信息，
  只会把「回放地址」写进一个本地 txt 文件。
</div>

<div class="note warn">
  <b>Chrome / Edge 用户（如果拖拽后点击没反应）：</b><br>
  拖拽容易丢掉 <code>javascript:</code> 前缀。改用书签导入，稳得多：<br>
  1. Chrome 打开 <code>chrome://bookmarks</code>（Edge 是 <code>edge://favorites</code>）<br>
  2. 右上角 <b>⋮</b> → <b>导入书签</b>（Edge：… → 导入收藏夹）<br>
  3. 选本文件夹里的 <code>dist/bookmarks.html</code><br>
  4. 书签栏里会出现「抓取课程清单」，去课程页点它即可
</div>

<p style="color:#57606a;font-size:14px;margin-top:32px">
  如果拖拽没反应，也可以：新建一个书签，名字随便填，<b>网址</b>粘贴 <code>dist/bookmarklet.txt</code> 里的那一整行。
</p>
</html>
`;
fs.writeFileSync(path.join(DIST, 'install.html'), html, 'utf8');

const kb = (s) => (Buffer.byteLength(s, 'utf8') / 1024).toFixed(1) + ' KB';
console.log('源码      : ' + kb(code) + ' -> javascript: 地址 ' + kb(url));
console.log('书签地址  : ' + path.join(DIST, 'bookmarklet.txt'));
console.log('安装页    : ' + path.join(DIST, 'install.html'));
console.log('Chrome 书签: ' + path.join(DIST, 'bookmarks.html') + '   (书签管理器 -> 导入)');
if (Buffer.byteLength(url) > 60 * 1024) {
  console.warn('警告：书签长度超过 60 KB，部分浏览器可能截断');
}
