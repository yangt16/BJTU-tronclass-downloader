/**
 * scrape_course.js (v3) - 在课程「直播」页上运行，导出整门课的回放清单。
 *
 * v3：每节详情并发 6 路（右下角显示进度）；三条轨固定全部导出（不再询问）。
 *
 * 纯走接口，不依赖 DOM，不受分页影响。已实测的接口形状：
 *
 *   1) 列表
 *      GET /api/courses/<courseId>/live-activities
 *          ?status=&types[]=lecture_live&types[]=third_party_live
 *          &page=<n>&page_size=<n>
 *      → { items:[{id,title,start_time,type}], total, pages, page, start, end }
 *        注意 items 里【没有】replay_videos
 *
 *   2) 每节详情
 *      GET /api/activities/<activityId>
 *      → data.external_live_detail.replay_videos[]
 *        每条 { camera_type: encoder|students|instructor,
 *               url: https://incast.../videos/<id>/preview?previewToken=xxx }
 *
 *   3) 本地程序拿到这些 url 后自己换签名直链（这步不需要登录）
 *
 * 怎么运行（Edge）：
 *   a) 打开课程「直播」列表页，形如 /course/26384/live-activities
 *   b) F12 → Sources → 左侧 >> → 代码片段 → 新建代码片段
 *   c) 把本文件全部内容粘进编辑器
 *   d) Ctrl+Enter 运行
 *   e) 下载出 <课程名>.txt；放进 lists\\ 或直接拖到入口图标上再双击
 */
(async () => {
  const m = location.pathname.match(/course\/(\d+)/);
  if (!m) {
    alert('请在课程页面运行本脚本（地址里要有 /course/<数字>/）');
    return;
  }
  const courseId = m[1];
  console.log(`[scrape] courseId=${courseId}`);

  // 页面右下角进度提示（抓取时不再像卡死）
  const ui = (() => {
    let el = null;
    const box = () => {
      if (el) return el;
      el = document.createElement('div');
      el.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;' +
        'background:#1f2430;color:#fff;padding:10px 14px;border-radius:8px;' +
        'font:13px/1.5 system-ui,sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.35);' +
        'max-width:320px;white-space:pre-wrap';
      el.textContent = '';
      document.body.appendChild(el);
      return el;
    };
    return {
      set(text) { box().textContent = text; },
      done(text, ms) {
        box().textContent = text;
        setTimeout(() => { if (el) { el.remove(); el = null; } }, ms || 4000);
      },
    };
  })();
  ui.set('抓取中：正在拉活动列表…');

  // ---------- 1. 拉列表（自动翻页） ----------
  const PAGE = 100;                 // 先试一次拉完；服务端若限流，pages 会告诉我们
  const types = 'types[]=lecture_live&types[]=third_party_live';
  const all = [];
  let page = 1, pages = 1, total = 0;
  do {
    const url = `/api/courses/${courseId}/live-activities` +
                `?status=&${types}&page=${page}&page_size=${PAGE}`;
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) { alert(`列表接口失败 HTTP ${r.status}`); return; }
    const j = await r.json();
    total = j.total ?? 0;
    pages = j.pages ?? 1;
    (j.items || []).forEach(it => all.push(it));
    console.log(`[scrape] 第 ${page}/${pages} 页，累计 ${all.length}/${total} 条`);
    page++;
  } while (page <= pages && page <= 50);

  ui.set(`列表已取 ${all.length} 条，正在取每节回放…`);
  const live = all.filter(it => it.type === 'lecture_live');
  if (!live.length) { alert('这门课没有 lecture_live 类型的活动'); return; }
  console.log(`[scrape] lecture_live 共 ${live.length} 条`);

  // 未开始的节没有回放，先按状态过滤掉，省掉无谓的详情请求
  const started = live.filter(it => {
    if (it.is_started === false) {
      console.log(`[scrape] ${it.id} ${it.title} 未开始，跳过（出回放后重跑本脚本即可）`);
      return false;
    }
    return true;
  });
  console.log(`[scrape] 需要查详情的 ${started.length} 条`);

  // ---------- 2. 并发取回放轨（一次 6 节，进度显示在右下角）----------
  const CONC = 6;
  const raw = new Array(started.length).fill(null);
  let fetched = 0;
  const queue = started.map((it, i) => [it, i]);
  async function one(it) {
    try {
      const r = await fetch(`/api/activities/${it.id}`, { credentials: 'include' });
      if (!r.ok) { console.warn(`[scrape] ${it.id} HTTP ${r.status}`); return null; }
      const j = await r.json();
      const det = (j.data && j.data.external_live_detail) || {};
      const vids = det.replay_videos || [];
      if (!vids.length) { console.warn(`[scrape] ${it.id} 无回放（可能还没下课）`); return null; }
      console.log(`[scrape] ${it.id} ${it.start_time} -> ${vids.length} 条轨`);
      return {
        id: it.id,
        title: j.title || it.title || '',
        date: (it.start_time || '').slice(0, 10),
        videos: vids,
      };
    } catch (e) {
      console.warn(`[scrape] ${it.id} 失败:`, e);
      return null;
    }
  }
  async function worker() {
    while (queue.length) {
      const [it, idx] = queue.shift();
      raw[idx] = await one(it);
      fetched++;
      ui.set(`抓取中：${fetched}/${started.length} 节`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONC, started.length) }, worker));
  const rows = raw.filter(Boolean);
  if (!rows.length) { alert('一条回放都没取到（这门课可能还没出回放）'); return; }
  const missing = started.length - rows.length;
  ui.set(`已查 ${started.length} 节${missing ? `，${missing} 节暂无回放` : ''}，正在整理清单…`);
  // 让浏览器先把上面这句画出来，再弹 prompt（prompt 会阻塞页面渲染）
  await new Promise(r => (typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame(r) : setTimeout(r, 0)));

  // ---------- 3. 课程名：从活动标题里去掉日期前缀 ----------
  const guess = (rows[0].title || '').replace(/^\d{4}-\d{2}-\d{2}-?/, '').trim() || `course${courseId}`;
  const course = (prompt(
    `共 ${started.length} 节已开始，取到 ${rows.length} 节回放` +
    (missing ? `（${missing} 节暂无回放，可能还没生成）` : '') +
    `。\n\n清单名（= 课程名，决定 media\\ 下的文件夹名）：`,
    guess) || '').trim();
  if (!course) { alert('已取消'); return; }

  // 三条轨固定全部导出：本地程序按需解析，不会全下

  // ---------- 4. 生成清单 ----------
  const lines = [
    `# ${course} · 自动抓取于 ${new Date().toLocaleString()}`,
    `# 共 ${rows.length} 节；每行「轨名 + preview 地址」，本地程序只解析要下的轨`,
  ];
  for (const r of rows) {
    lines.push(`# ${r.date} ${r.title}`);
    for (const v of r.videos) {
      const tr = (v.camera_type || '').toUpperCase();
      lines.push(tr ? `${tr} ${v.url}` : v.url);
    }
  }

  const blob = new Blob([lines.join('\n') + '\n'], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${course}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();

  console.log(`[scrape] 完成：${rows.length} 节 -> ${course}.txt`);
  ui.done(`完成：${rows.length} 节，已下载 ${course}.txt`);
  alert(`已导出 ${rows.length} 节到「下载」文件夹的 ${course}.txt\n\n把下载的 txt 放进 lists\\，或直接拖到入口图标上。\\n跑完后 txt 会自动归档，lists 里不会留下 txt。`);
})();
