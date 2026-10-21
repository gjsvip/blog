/* ============================================================
   渡劫博客 · 核心脚本
   主题切换 / 进度条 / 搜索 / TOC / 代码高亮+复制 /
   点赞 / 浏览 / 评论树 / 说说 / 入场动画
   三端统一评论 API：https://dujiecone.520691.xyz
   ============================================================ */
(function () {
  'use strict';

  /* ---------- 常量 ---------- */
  var API_BASE = 'https://dujiecone.520691.xyz';
  var POSTS_JSON = 'posts.json';
  var THEME_KEY = 'dujie-blog-theme';
  var EMOJIS = ['😀','😂','🥰','😎','🤔','😴','😭','😡','👍','👎','🙏','👏','🔥','💯','✨','🎉','❤️','💔','⭐','🌈','☀️','🌙','⚡','🍺','☕','🐟','🐱','🐶','🚀','💻','📚','✍️','🧧','🛠️','⚠️'];

  /* ---------- 工具 ---------- */
  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function getSlug() {
    // 兼容三种形态：/posts/xxx.html、/posts/xxx（CF Pages 无扩展名规范 URL）、/posts/xxx/
    var m = location.pathname.match(/posts\/([^/]+?)(?:\.html)?\/?$/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  function visitorId() {
    try {
      var id = localStorage.getItem('dujie-vid');
      if (!id) { id = 'v' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10); localStorage.setItem('dujie-vid', id); }
      return id;
    } catch (e) { return 'anon-' + navigator.userAgent.slice(0, 24); }
  }
  function timeAgo(ts) {
    var d = Date.now() - new Date(ts).getTime();
    var m = Math.floor(d / 60000);
    if (m < 1) return '刚刚';
    if (m < 60) return m + ' 分钟前';
    var h = Math.floor(m / 60);
    if (h < 24) return h + ' 小时前';
    var day = Math.floor(h / 24);
    if (day < 30) return day + ' 天前';
    var mo = Math.floor(day / 30);
    if (mo < 12) return mo + ' 个月前';
    return Math.floor(mo / 12) + ' 年前';
  }
  function toast(msg, type) {
    var wrap = $('#toast-wrap');
    if (!wrap) { wrap = document.createElement('div'); wrap.id = 'toast-wrap'; document.body.appendChild(wrap); }
    var t = document.createElement('div');
    t.className = 'toast ' + (type || '');
    t.innerHTML = (type === 'ok' ? '✅ ' : type === 'err' ? '❌ ' : '💬 ') + esc(msg);
    wrap.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transform = 'translateY(10px)'; t.style.transition = 'all .35s'; }, 2600);
    setTimeout(function () { t.remove(); }, 3100);
  }
  function api(path, opts) {
    return fetch(API_BASE + path, opts).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (j) {
      if (j && j.code === 0) return j.data;
      throw new Error((j && j.message) || '接口错误');
    });
  }

  /* ---------- 点赞本地记忆（worker stats 不回传 liked，用 localStorage 兜底） ---------- */
  var LIKED_POSTS_KEY = 'dujie-liked-posts';
  var LIKED_COMMENTS_KEY = 'dujie-liked-comments';
  function readLiked(key) {
    try {
      var raw = localStorage.getItem(key);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function isLiked(key, id) {
    return readLiked(key).some(function (x) { return String(x) === String(id); });
  }
  function saveLiked(key, id) {
    try {
      var arr = readLiked(key);
      if (arr.map(String).indexOf(String(id)) === -1) {
        arr.push(id);
        localStorage.setItem(key, JSON.stringify(arr));
      }
    } catch (e) {}
  }
  function forgetLiked(key, id) {
    try {
      var arr = readLiked(key).filter(function (x) { return String(x) !== String(id); });
      localStorage.setItem(key, JSON.stringify(arr));
    } catch (e) {}
  }

  /* ---------- 主题 ---------- */
  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
    var theme = saved || (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
    $$('.theme-toggle').forEach(function (b) { b.textContent = theme === 'light' ? '🌙' : '☀️'; });
  }
  function toggleTheme() {
    var cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    var next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    $$('.theme-toggle').forEach(function (b) { b.textContent = next === 'light' ? '🌙' : '☀️'; });
    toast(next === 'light' ? '已切换亮色模式' : '已切换暗色模式');
  }

  /* ---------- 公共 UI ---------- */
  function isMobile() {
    return !!(window.matchMedia && window.matchMedia('(max-width: 640px)').matches);
  }
  function closeMenu() {
    var nav = $('.nav');
    if (nav) nav.classList.remove('open');
    $$('.menu-toggle').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
  }
  function initChrome() {
    initTheme();
    $$('.theme-toggle').forEach(function (b) { b.addEventListener('click', toggleTheme); });
    // 移动端菜单：开 / 关（点链接、点外部、ESC 均关闭）
    $$('.menu-toggle').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        var nav = $('.nav');
        var open = nav.classList.toggle('open');
        b.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    });
    var navEl = $('.nav');
    if (navEl) {
      $$('a', navEl).forEach(function (a) { a.addEventListener('click', closeMenu); });
    }
    document.addEventListener('click', function (e) {
      var nav = $('.nav');
      if (nav && nav.classList.contains('open') && !e.target.closest('.nav') && !e.target.closest('.menu-toggle')) closeMenu();
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
    // 进度条 + 返回顶部
    var bar = $('#progress-bar'), top = $('#back-top');
    function onScroll() {
      var h = document.documentElement;
      var p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
      if (bar) bar.style.width = (p * 100).toFixed(2) + '%';
      if (top) top.classList.toggle('show', h.scrollTop > 500);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    if (top) top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    // 入场动画
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.08 });
    $$('.reveal').forEach(function (el) { io.observe(el); });
    // 导航高亮
    var page = location.pathname.split('/').pop() || 'index.html';
    if (page === '') page = 'index.html';
    $$('.nav a').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      if (href === page || (page === 'index.html' && href === 'index.html')) a.classList.add('active');
    });
  }

  /* ---------- 搜索 ---------- */
  var searchCache = null, searchIdx = -1;
  function loadPosts() {
    if (searchCache) return Promise.resolve(searchCache);
    return fetch(POSTS_JSON).then(function (r) { return r.json(); }).then(function (j) { searchCache = j.posts || j; return searchCache; });
  }
  function initSearch() {
    var modal = $('#search-modal'), input = $('#search-input'), box = $('#search-results');
    if (!modal || !input) return;
    // 底部提示：桌面显示快捷键，手机显示「点击搜索」
    var panel = $('.search-panel', modal);
    if (panel && !$('.kbd-hint', panel)) {
      var hint = document.createElement('div');
      hint.className = 'kbd-hint';
      hint.textContent = isMobile() ? '点击输入框搜索文章 · ESC 关闭' : 'Ctrl/⌘ K 随时搜索 · ESC 关闭';
      panel.appendChild(hint);
    }
    function open() { modal.classList.add('open'); input.value = ''; render(''); input.focus(); }
    function close() { modal.classList.remove('open'); searchIdx = -1; }
    function render(q) {
      loadPosts().then(function (posts) {
        q = q.trim().toLowerCase();
        var list = q ? posts.filter(function (p) {
          return (p.title + ' ' + (p.tags || []).join(' ') + ' ' + (p.excerpt || '') + ' ' + (p.category || '')).toLowerCase().indexOf(q) > -1;
        }) : posts.slice(0, 8);
        if (!list.length) { box.innerHTML = '<div class="search-empty">没有找到相关文章 🔍</div>'; return; }
        box.innerHTML = list.map(function (p) {
          function hl(t) {
            if (!q) return esc(t);
            var i = t.toLowerCase().indexOf(q);
            return i < 0 ? esc(t) : esc(t.slice(0, i)) + '<mark>' + esc(t.slice(i, i + q.length)) + '</mark>' + esc(t.slice(i + q.length));
          }
          return '<a class="search-result-item" href="posts/' + esc(p.slug) + '.html"><div class="t">' + hl(p.title) + '</div><div class="d">' + esc((p.date || '') + ' · ' + (p.tags || []).join(' / ')) + '</div></a>';
        }).join('');
        searchIdx = -1;
        $$('.search-result-item', box).forEach(function (a) {
          a.addEventListener('click', close);
        });
      });
    }
    $$('.search-trigger').forEach(function (b) { b.addEventListener('click', open); });
    modal.addEventListener('click', function (e) { if (e.target === modal) close(); });
    input.addEventListener('input', function () { render(input.value); });
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); modal.classList.contains('open') ? close() : open(); }
      if (e.key === 'Escape' && modal.classList.contains('open')) close();
      if (modal.classList.contains('open') && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter')) {
        var items = $$('.search-result-item', box);
        if (!items.length) return;
        e.preventDefault();
        if (e.key === 'Enter' && searchIdx >= 0) { items[searchIdx].click(); return; }
        searchIdx = e.key === 'ArrowDown' ? Math.min(items.length - 1, searchIdx + 1) : Math.max(0, searchIdx - 1);
        items.forEach(function (it, i) { it.classList.toggle('sel', i === searchIdx); });
        if (items[searchIdx]) items[searchIdx].scrollIntoView({ block: 'nearest' });
      }
    });
    // 支持 ?q= 查询参数：Google 站内搜索框（SearchAction）落地后自动执行搜索
    try {
      var qParam = new URLSearchParams(location.search).get('q');
      if (qParam) {
        modal.classList.add('open');
        input.value = qParam;
        render(qParam);
        input.focus();
      }
    } catch (e) { /* 老浏览器无 URLSearchParams 时静默跳过 */ }
  }

  /* ---------- 首页 ---------- */
  function fmtDate(d) { return d ? d.replace(/-/g, '/') : ''; }
  function initHome() {
    var list = $('#post-list');
    if (!list) return;
    loadPosts().then(function (posts) {
      posts.sort(function (a, b) { return (b.date || '').localeCompare(a.date || '') || (b.pinned ? 1 : -1); });
      var html = posts.map(function (p) {
        return '<article class="post-card reveal">' +
          (p.pinned ? '<span class="pinned-badge">📌 置顶</span>' : '') +
          '<a class="post-cover" href="posts/' + esc(p.slug) + '.html" aria-label="' + esc(p.title) + '"><span class="cover-emoji">' + esc(p.cover || '📄') + '</span></a>' +
          '<div class="post-body">' +
            '<div class="post-meta"><span class="cat">' + esc(p.category || '随笔') + '</span><time>' + esc(fmtDate(p.date)) + '</time></div>' +
            '<h3 class="post-title"><a href="posts/' + esc(p.slug) + '.html">' + esc(p.title) + '</a></h3>' +
            '<p class="post-excerpt">' + esc(p.excerpt || '') + '</p>' +
            '<div class="post-foot" data-slug="' + esc(p.slug) + '">' +
              '<span class="chip">👁 <b class="v-views">-</b></span>' +
              '<span class="chip">❤️ <b class="v-likes">-</b></span>' +
              '<span class="chip">💬 <b class="v-comments">-</b></span>' +
              (p.tags || []).slice(0, 3).map(function (t) { return '<span class="chip">🏷 ' + esc(t) + '</span>'; }).join('') +
            '</div>' +
          '</div></article>';
      }).join('');
      list.innerHTML = html;
      // 入场动画
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
      }, { threshold: 0.06 });
      $$('.reveal', list).forEach(function (el) { io.observe(el); });
      // 统计数据（兼容数组与对象两种返回形态；comments 缺失按 0 处理）
      var slugs = posts.map(function (p) { return p.slug; }).join(',');
      var normStats = function (data) {
        if (Array.isArray(data)) return data;
        if (data && typeof data === 'object') {
          return Object.keys(data).map(function (k) { return Object.assign({ slug: k }, data[k]); });
        }
        return [];
      };
      api('/api/blog/stats?slugs=' + encodeURIComponent(slugs)).then(function (data) {
        var arr = normStats(data);
        var map = {};
        arr.forEach(function (s) { map[s.slug] = s; });
        $$('.post-foot', list).forEach(function (foot) {
          var s = map[foot.getAttribute('data-slug')] || {};
          var v = $('.v-views', foot), l = $('.v-likes', foot), c = $('.v-comments', foot);
          if (v) v.textContent = s.views || 0;
          if (l) l.textContent = s.likes || 0;
          if (c) c.textContent = s.comments || 0;
        });
        // 侧栏死 ID 修复：文章数 / 评论总数 / 浏览总数
        var sp = $('#stat-posts'), sc = $('#stat-comments'), sv = $('#stat-views');
        if (sp) sp.textContent = posts.length;
        if (sc) sc.textContent = arr.reduce(function (sum, s) { return sum + (s.comments || 0); }, 0);
        if (sv) sv.textContent = arr.reduce(function (sum, s) { return sum + (s.views || 0); }, 0);
      }).catch(function () {});
      // 侧栏热门
      api('/api/blog/stats?slugs=' + encodeURIComponent(slugs)).then(function (data) {
        var hot = $('#hot-list');
        if (!hot) return;
        var arr = normStats(data);
        arr.sort(function (a, b) { return (b.views || 0) - (a.views || 0); });
        hot.innerHTML = arr.slice(0, 5).map(function (s, i) {
          var p = posts.filter(function (x) { return x.slug === s.slug; })[0] || {};
          return '<div class="hot-item"><span class="rank">' + (i + 1) + '</span><a href="posts/' + esc(s.slug) + '.html">' + esc(p.title || s.slug) + '</a></div>';
        }).join('');
      }).catch(function () {});
    }).catch(function () {
      list.innerHTML = '<div class="empty"><div class="big">📭</div>文章列表加载失败，请刷新重试</div>';
    });
  }

  /* ---------- 文章页 ---------- */
  function renderComment(c, isReply) {
    var av = c.avatar || '';
    var avatarHtml = av
      ? '<img src="' + esc(av) + '" alt="' + esc(c.nickname) + '" loading="lazy" onerror="this.parentNode.textContent=\'' + esc(c.nickname.charAt(0).toUpperCase()) + '\'">'
      : esc(c.nickname.charAt(0).toUpperCase());
    var isAuthor = c.nickname === '渡劫' || c.nickname === 'dujie';
    var html = '<div class="comment' + (isReply ? ' reply-c' : '') + '" data-id="' + c.id + '">' +
      '<div class="comment-avatar">' + avatarHtml + '</div>' +
      '<div class="comment-main">' +
        '<div class="comment-head"><span class="name">' + esc(c.nickname) + '</span>' +
        (isAuthor ? '<span class="badge">博主</span>' : '') +
        '<time datetime="' + esc(c.created_at) + '">' + esc(timeAgo(c.created_at)) + '</time></div>' +
        '<div class="comment-text">' + esc(c.content) + '</div>' +
        '<div class="comment-foot">' +
          '<button class="c-like' + (c.liked ? ' liked' : '') + '" data-id="' + c.id + '">❤️ <b>' + (c.likes || 0) + '</b></button>' +
          '<button class="c-reply" data-id="' + c.id + '" data-name="' + esc(c.nickname) + '">💬 回复</button>' +
        '</div>' +
        '<div class="reply-box" id="reply-' + c.id + '">' +
          '<textarea placeholder="回复 @' + esc(c.nickname) + ' …"></textarea>' +
          '<div class="rb-foot"><button class="rb-submit">发送回复</button><button class="rb-cancel">取消</button></div>' +
        '</div>' +
      '</div></div>';
    if (c.replies && c.replies.length) {
      html += '<div class="replies">' + c.replies.map(function (r) { return renderComment(r, true); }).join('') + '</div>';
    }
    return html;
  }
  function bindCommentActions(root) {
    $$('.c-like', root).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-id');
        api('/api/blog/like', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ comment_id: Number(id), visitor: visitorId() })
        }).then(function (d) {
          btn.classList.toggle('liked', !!d.liked);
          $('b', btn).textContent = d.likes;
          if (d.liked) saveLiked(LIKED_COMMENTS_KEY, id); else forgetLiked(LIKED_COMMENTS_KEY, id);
        }).catch(function (e) { toast(e.message, 'err'); });
      });
    });
    $$('.c-reply', root).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-id');
        $$('.reply-box').forEach(function (b) { if (b.id !== 'reply-' + id) b.classList.remove('open'); });
        var box = $('#reply-' + id);
        box.classList.toggle('open');
        if (box.classList.contains('open')) $('textarea', box).focus();
      });
    });
    $$('.rb-cancel', root).forEach(function (btn) {
      btn.addEventListener('click', function () { btn.closest('.reply-box').classList.remove('open'); });
    });
    $$('.rb-submit', root).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var box = btn.closest('.reply-box');
        var id = box.id.replace('reply-', '');
        var text = $('textarea', box).value.trim();
        if (!text) { toast('回复内容不能为空', 'err'); return; }
        var form = $('#comment-form');
        var nick = ($('#c-nickname') ? $('#c-nickname').value.trim() : '') || '匿名访客';
        btn.disabled = true;
        api('/api/blog/comments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug: getSlug(), nickname: nick, email: ($('#c-email') || {}).value || '', content: text, parentId: Number(id), visitor: visitorId() })
        }).then(function () {
          toast('回复成功', 'ok');
          $('textarea', box).value = '';
          box.classList.remove('open');
          loadComments();
        }).catch(function (e) { toast(e.message, 'err'); btn.disabled = false; });
      });
    });
  }
  var commentsSlug = null;
  function loadComments() {
    var box = $('#comment-list');
    if (!box) return;
    box.innerHTML = '<div class="loading">评论加载中…</div>';
    api('/api/blog/comments?slug=' + encodeURIComponent(commentsSlug)).then(function (data) {
      var list = (data && (data.comments || data.list)) || [];
      var total = (data && data.total != null) ? data.total : list.length;
      var cnt = $('#comment-count');
      if (cnt) cnt.textContent = total;
      if (!list.length) {
        box.innerHTML = '<div class="comments-empty"><div class="big">💬</div>还没有评论，来抢个沙发吧～</div>';
        return;
      }
      box.innerHTML = list.map(function (c) { return renderComment(c, false); }).join('');
      bindCommentActions(box);
      // 用本地点赞记忆预置 .liked 高亮（worker 不回传评论维度 liked）
      $$('.c-like', box).forEach(function (btn) {
        if (isLiked(LIKED_COMMENTS_KEY, btn.getAttribute('data-id'))) btn.classList.add('liked');
      });
    }).catch(function (e) {
      box.innerHTML = '<div class="comments-empty"><div class="big">⚠️</div>评论加载失败：' + esc(e.message) + '</div>';
    });
  }
  function initComments() {
    var slug = getSlug();
    if (!slug) return;
    commentsSlug = slug;
    loadComments();
    // emoji 面板
    var panel = $('#emoji-panel'), ta = $('#c-content');
    if (panel && ta) {
      panel.innerHTML = EMOJIS.map(function (e) { return '<button type="button">' + e + '</button>'; }).join('');
      $$('button', panel).forEach(function (b) {
        b.addEventListener('click', function () {
          ta.value += b.textContent;
          ta.focus();
        });
      });
      var eb = $('#emoji-btn');
      if (eb) eb.addEventListener('click', function () { panel.classList.toggle('open'); });
    }
    // 记忆昵称/邮箱
    try {
      var n = localStorage.getItem('dujie-nick'), m = localStorage.getItem('dujie-mail');
      if (n && $('#c-nickname')) $('#c-nickname').value = n;
      if (m && $('#c-email')) $('#c-email').value = m;
    } catch (e) {}
    var form = $('#comment-form');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var nick = $('#c-nickname').value.trim();
        var content = $('#c-content').value.trim();
        if (!nick) { toast('先填个昵称吧', 'err'); $('#c-nickname').focus(); return; }
        if (!content) { toast('评论内容不能为空', 'err'); $('#c-content').focus(); return; }
        var btn = $('#c-submit');
        btn.disabled = true; btn.textContent = '发送中…';
        try { localStorage.setItem('dujie-nick', nick); localStorage.setItem('dujie-mail', $('#c-email').value.trim()); } catch (err) {}
        api('/api/blog/comments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug: slug, nickname: nick, email: $('#c-email').value.trim(), content: content, visitor: visitorId() })
        }).then(function () {
          toast('评论发布成功', 'ok');
          $('#c-content').value = '';
          loadComments();
        }).catch(function (err) { toast(err.message, 'err'); })
          .finally(function () { btn.disabled = false; btn.textContent = '发布评论'; });
      });
    }
  }
  function initArticle() {
    var slug = getSlug();
    if (!slug) return;
    // 阅读量 +1
    api('/api/blog/view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slug, visitor: visitorId() })
    }).then(function (d) { var v = $('#stat-views'); if (v) v.textContent = d.views; }).catch(function () {});
    // 统计 + 点赞状态
    api('/api/blog/stats?slugs=' + encodeURIComponent(slug)).then(function (data) {
      // 兼容数组 data[0] 与对象 data[slug] 两种返回形态
      var s = (data && (Array.isArray(data) ? data[0] : (data[slug] || {}))) || {};
      var v = $('#stat-views'), l = $('#stat-likes'), c = $('#stat-comments');
      if (v) v.textContent = s.views || 0;
      if (l) l.textContent = s.likes || 0;
      if (c) c.textContent = s.comments || 0;
      var btn = $('#like-btn');
      if (btn) {
        if (s.liked || isLiked(LIKED_POSTS_KEY, slug)) btn.classList.add('liked');
        btn.addEventListener('click', function () {
          api('/api/blog/like', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug: slug, visitor: visitorId() })
          }).then(function (d) {
            btn.classList.toggle('liked', !!d.liked);
            if (l) l.textContent = d.likes;
            if (d.liked) saveLiked(LIKED_POSTS_KEY, slug); else forgetLiked(LIKED_POSTS_KEY, slug);
            toast(d.liked ? '感谢点赞 ❤️' : '已取消点赞');
          }).catch(function (e) { toast(e.message, 'err'); });
        });
      }
    }).catch(function () {});
    // 代码高亮 + 复制
    $$('.article-body pre code').forEach(function (code) {
      var pre = code.parentNode;
      var lang = (code.className.match(/language-(\w+)/) || [])[1] || pre.getAttribute('data-lang') || 'code';
      var tag = document.createElement('span');
      tag.className = 'code-lang'; tag.textContent = lang;
      pre.appendChild(tag);
      var btn = document.createElement('button');
      btn.className = 'copy-btn'; btn.textContent = '复制';
      btn.addEventListener('click', function () {
        var text = code.textContent;
        function done() { btn.textContent = '已复制 ✓'; btn.classList.add('copied'); setTimeout(function () { btn.textContent = '复制'; btn.classList.remove('copied'); }, 2000); }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () { fallback(); });
        } else fallback();
        function fallback() {
          var t = document.createElement('textarea');
          t.value = text; t.style.position = 'fixed'; t.style.opacity = '0';
          document.body.appendChild(t); t.select();
          try { document.execCommand('copy'); done(); } catch (e) { toast('复制失败', 'err'); }
          t.remove();
        }
      });
      pre.appendChild(btn);
      highlight(code);
    });
    // TOC
    var tocBox = $('#toc-list');
    if (tocBox) {
      var heads = $$('.article-body h2, .article-body h3');
      if (!heads.length) {
        var p = tocBox.closest('.panel'); if (p) p.style.display = 'none';
      } else {
        tocBox.innerHTML = heads.map(function (h, i) {
          if (!h.id) h.id = 'sec-' + i;
          return '<a class="' + (h.tagName === 'H3' ? 'lv3' : '') + '" href="#' + h.id + '">' + esc(h.textContent.replace(/^▸\s*/, '')) + '</a>';
        }).join('');
        var links = $$('a', tocBox);
        var spy = new IntersectionObserver(function (es) {
          es.forEach(function (e) {
            if (e.isIntersecting) {
              links.forEach(function (a) { a.classList.toggle('active', a.getAttribute('href') === '#' + e.target.id); });
            }
          });
        }, { rootMargin: '-80px 0px -70% 0px' });
        heads.forEach(function (h) { spy.observe(h); });
        // 移动端：目录默认收起为「目录 ▾」折叠按钮，点击展开；回到桌面自动恢复
        var tocPanel = tocBox.closest('.panel');
        var tocTitle = tocPanel ? $('.panel-title', tocPanel) : null;
        if (tocPanel && tocTitle && !$('.toc-collapse-btn', tocTitle)) {
          var collapseBtn = document.createElement('button');
          collapseBtn.type = 'button';
          collapseBtn.className = 'toc-collapse-btn';
          collapseBtn.setAttribute('aria-expanded', 'false');
          function refreshCollapse() {
            var mobile = isMobile();
            tocPanel.classList.toggle('toc-collapsed', mobile);
            if (!mobile) tocPanel.classList.remove('toc-open');
            collapseBtn.textContent = tocPanel.classList.contains('toc-open') ? '收起 ▴' : '📑 目录 ▾';
            collapseBtn.setAttribute('aria-expanded', tocPanel.classList.contains('toc-open') ? 'true' : 'false');
          }
          collapseBtn.addEventListener('click', function () {
            tocPanel.classList.toggle('toc-open');
            refreshCollapse();
          });
          tocTitle.appendChild(collapseBtn);
          refreshCollapse();
          window.addEventListener('resize', refreshCollapse);
        }
      }
    }
    // 上下篇
    loadPosts().then(function (posts) {
      posts.sort(function (a, b) { return (b.date || '').localeCompare(a.date || ''); });
      var i = posts.findIndex(function (p) { return p.slug === slug; });
      var nav = $('#post-nav');
      if (nav && i > -1) {
        var prev = posts[i - 1], next = posts[i + 1];
        nav.innerHTML =
          (prev ? '<a href="' + esc(prev.slug) + '.html"><span class="dir">← 上一篇</span>' + esc(prev.title) + '</a>' : '<a style="visibility:hidden"></a>') +
          (next ? '<a class="next" href="' + esc(next.slug) + '.html"><span class="dir">下一篇 →</span>' + esc(next.title) + '</a>' : '<a style="visibility:hidden"></a>');
      }
    }).catch(function () {});
  }
  /* 轻量高亮 */
  function highlight(code) {
    var KW = /\b(const|let|var|function|return|if|else|for|while|new|class|import|from|export|async|await|try|catch|throw|typeof|instanceof|def|print|self|None|True|False|public|private|static|void|int|string|bool|SELECT|FROM|WHERE|INSERT|INTO|VALUES|CREATE|TABLE|PRIMARY|KEY)\b/g;
    var html = esc(code.textContent);
    html = html.replace(/(&quot;.*?&quot;|&#39;.*?&#39;|`[^`]*`)/g, '<span class="tok-str">$1</span>');
    html = html.replace(KW, '<span class="tok-kw">$1</span>');
    html = html.replace(/\b(\d+(\.\d+)?)\b/g, function (m) { return '<span class="tok-num">' + m + '</span>'; });
    html = html.replace(/(\/\/[^\n]*|#[^\n]*)/g, '<span class="tok-com">$1</span>');
    code.innerHTML = html;
  }

  /* ---------- 归档 / 标签 / 关于 ---------- */
  function initArchive() {
    var box = $('#timeline');
    if (!box) return;
    loadPosts().then(function (posts) {
      posts.sort(function (a, b) { return (b.date || '').localeCompare(a.date || ''); });
      var byYear = {};
      posts.forEach(function (p) {
        var y = (p.date || '未知').slice(0, 4);
        (byYear[y] = byYear[y] || []).push(p);
      });
      box.innerHTML = Object.keys(byYear).sort().reverse().map(function (y) {
        return '<div class="tl-year">' + esc(y) + ' · ' + byYear[y].length + ' 篇</div>' +
          byYear[y].map(function (p) {
            return '<div class="tl-item"><time>' + esc(p.date) + '</time><a href="posts/' + esc(p.slug) + '.html">' + esc(p.title) + '</a></div>';
          }).join('');
      }).join('');
    }).catch(function () { box.innerHTML = '<div class="empty">加载失败</div>'; });
  }
  function initTags() {
    var box = $('#tags-cloud');
    if (!box) return;
    loadPosts().then(function (posts) {
      var map = {};
      posts.forEach(function (p) { (p.tags || []).forEach(function (t) { map[t] = (map[t] || 0) + 1; }); });
      var keys = Object.keys(map).sort(function (a, b) { return map[b] - map[a]; });
      if (!keys.length) { box.innerHTML = '<div class="empty">暂无标签</div>'; return; }
      box.innerHTML = keys.map(function (t) {
        return '<a href="index.html">🏷 ' + esc(t) + '<span class="n">' + map[t] + '</span></a>';
      }).join('');
      // 侧栏标签云（首页）
      var side = $('#side-tags');
      if (side) side.innerHTML = keys.slice(0, 14).map(function (t) { return '<a href="tags.html">' + esc(t) + '<span class="n">' + map[t] + '</span></a>'; }).join('');
    }).catch(function () {});
  }
  function initSays() {
    var box = $('#says-list');
    if (!box) return;
    api('/api/blog/says').then(function (data) {
      var list = (data && data.list) || data || [];
      if (!list.length) { box.innerHTML = '<div class="empty"><div class="big">🐟</div>暂无说说</div>'; return; }
      box.innerHTML = list.map(function (s) {
        return '<div class="say-item reveal in"><span class="say-mood">' + esc(s.mood || '🐟') + '</span><time>' + esc(s.created_at || s.createdAt) + '</time><p>' + esc(s.content) + '</p></div>';
      }).join('');
    }).catch(function () { box.innerHTML = '<div class="empty"><div class="big">⚠️</div>说说加载失败</div>'; });
  }

  /* ---------- 友链（friends.json 数据驱动，失败降级静态内容） ---------- */
  function friendCard(f) {
    var name = String(f.name || '友链');
    var status = f.status === 'pending'
      ? '<em class="friend-status pending">待互换</em>'
      : '<i class="status-dot ok" title="在线"></i>';
    var fallback = esc(name.charAt(0));
    var avatar = f.avatar
      ? '<img src="' + esc(f.avatar) + '" alt="' + esc(name) + '" width="44" height="44" loading="lazy" onerror="this.parentNode.textContent=\'' + fallback + '\';this.remove()">'
      : fallback;
    return '<a class="friend-card" href="' + esc(f.url || '#') + '" target="_blank" rel="noopener">' +
      '<span class="friend-avatar">' + avatar + '</span>' +
      '<span class="friend-info"><b>' + esc(name) + status + '</b><span>' + esc(f.desc || '') + '</span></span></a>';
  }
  function initFriends() {
    var box = $('#friends-grid');
    if (!box) return;
    fetch('friends.json').then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (j) {
      var list = (j && j.friends) || [];
      if (!list.length) return; // 数据为空时保留静态降级内容
      box.innerHTML = list.map(friendCard).join('');
      var count = $('#friends-count');
      if (count) count.textContent = '共 ' + list.length + ' 条 · friends.json 驱动';
    }).catch(function () { /* 网络或解析失败：保留页面内静态内容 */ });
  }

  /* ---------- 启动 ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    initChrome();
    initSearch();
    initHome();
    initArticle();
    initComments();
    initArchive();
    initTags();
    initSays();
    initFriends();
  });
})();
