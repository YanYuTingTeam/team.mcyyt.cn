function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
}
function avatarUrl(u) {
    if (u && u.avatar) return u.avatar;
    var name = (u && u.name) || '?';
    var ch = name.charAt(0).toUpperCase();
    var palette = ['#ef5777', '#4dabf7', '#4caf7d', '#cc5de8', '#f59f00', '#ff6b6b', '#748ffc', '#098b78', '#f06595', '#7048e8'];
    var hash = 0;
    for (var i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    var color = palette[Math.abs(hash) % palette.length];
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" rx="32" fill="' + color + '"/><text x="32" y="34" text-anchor="middle" dominant-baseline="central" font-size="30" fill="#fff" font-family="sans-serif" font-weight="bold">' + esc(ch) + '</text></svg>';
    return 'data:image/svg+xml,' + encodeURIComponent(svg);
}
function escAttr(s) { return String(s == null ? '' : s).replace(/\"/g, '&quot;').replace(/'/g, '&#39;').replace(/\\/g, '\\\\'); }
function markErr(input, msg) {
    if (!input) return;
    input.classList.add('input-error');
    if (msg) {
        var wrap = input.closest('.md-v, .form-row, .picker-wrap, .add-todo-row');
        if (wrap) {
            var t = wrap.querySelector('.err-tip');
            if (!t) {
                t = document.createElement('div');
                t.className = 'err-tip';
                t.style.color = '#ef5777'; t.style.fontSize = '12px'; t.style.marginTop = '4px';
                wrap.appendChild(t);
            }
            t.textContent = msg;
        }
    }
    setTimeout(function(){ input && input.classList.remove('input-error'); }, 300);
    input.classList.add('input-error');
}
document.addEventListener('input', function(e) {
    if (e.target.classList && e.target.classList.contains('input-error')) {
        e.target.classList.remove('input-error');
        var wrap = e.target.closest('.md-v, .form-row, .picker-wrap, .add-todo-row');
        if (wrap) {
            var t = wrap.querySelector('.err-tip');
            if (t) t.textContent = '';
        }
    }
});
async function getJson(url) {
    var res = await fetch(url);
    var ret = await res.json();
    if (ret.code === 401) { location.reload(); throw new Error('no login'); }
    return ret;
}
async function postJson(url, body) {
    var res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    return res.json();
}
var PAGE_PATH = { home: '/', overview: '/overview', todo: '/todos', notice: '/notice', project: '/projects', apis: '/apis', logs: '/logs', mcsm: '/mcsmanager', team: '/team', addtodo: '/todos/add', tododetail: '/todos' };
var NAV_OF = { home: 'home', overview: 'overview', todo: 'todo', notice: 'notice', project: 'project', apis: 'apis', logs: 'overview', mcsm: 'mcsm', team: 'team', addtodo: 'todo', tododetail: 'todo' };
var PAGE_LOADER = { home: null, overview: loadOverview, todo: loadTodo, notice: loadNotice, project: loadProject, apis: loadApis, logs: loadLogs, mcsm: loadMcsm, team: loadTeam, addtodo: resetAddTodo, tododetail: null };
var SPIN_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="spin" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3a9 9 0 1 0 9 9"/></svg>';
var LEVEL_NAME = { 0: '待定', 1: '志愿者 | 初级', 2: '志愿者 | 中级', 3: '志愿者 | 高级', 4: '管理员', 5: '服主' };
var LEVEL_COLOR = { 0: '#888', 1: '#4caf7d', 2: '#4dabf7', 3: '#cc5de8', 4: '#f59f00', 5: '#ef5777' };
var levelMeta = {};
var ALL_USERS = [];
var DEFAULT_PAGE_ACCESS = {
    home: { min_level: 0, show_in_nav: 1 }, overview: { min_level: 0, show_in_nav: 1 },
    todo: { min_level: 1, show_in_nav: 1 }, notice: { min_level: 1, show_in_nav: 1 },
    project: { min_level: 1, show_in_nav: 1 }, apis: { min_level: 1, show_in_nav: 1 },
    mcsm: { min_level: 4, show_in_nav: 1 }, team: { min_level: 5, show_in_nav: 1 },
    invite_create: { min_level: 4, show_in_nav: 0 }
};
var PAGE_LABEL = { home: '空间首页', overview: '个人概览', todo: '待办事项', notice: '通知动态', project: '项目展示', apis: 'API 文档', mcsm: 'MCSManager', team: '团队管理', invite_create: '生成邀请码' };
var PAGE_KIND = { invite_create: 'feature' };
var meUser = null;
var pageAccess = {};
function hexA(hex, a) {
    var h = (hex || '#ef5777').replace('#','');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var r = parseInt(h.substr(0,2),16), g = parseInt(h.substr(2,2),16), b = parseInt(h.substr(4,2),16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + (a||0.1) + ')';
}
function renderSkillHtml(raw) {
    if (!raw) return '<span class="empty-tip">未填写</span>';
    var list = String(raw).split(/[,，]/).map(function(x) { return x.trim(); }).filter(Boolean);
    if (!list.length) return '<span class="empty-tip">未填写</span>';
    var lookup = window.__SKILL_META || {};
    return list.map(function(nm) {
        var m = null;
        for (var k in lookup) {
            if (lookup[k] && lookup[k].name === nm) { m = lookup[k]; break; }
        }
        var c = m ? m.color : '#ef5777';
        return '<span class="skill-tag sm" style="color:' + c + ';border-color:' + hexA(c,.45) + ';background:' + hexA(c,.08) + '">' + esc(nm) + '</span>';
    }).join('');
}
function myLevel() { return (meUser && meUser.level) || 0; }
function levelName(lv) { var m = levelMeta[lv]; return (m && m.name) || LEVEL_NAME[lv] || '待定'; }
function levelColor(lv) { var m = levelMeta[lv]; return (m && m.color) || LEVEL_COLOR[lv] || '#888'; }
function lvlBadge(lv) { var c = levelColor(lv); return '<span class="lvl-badge" style="--lc:' + c + ';--lcbd:' + hexA(c,.45) + ';border-color:' + c + ';color:' + c + ';background:' + hexA(c,.08) + '">' + esc(levelName(lv)) + '</span>'; }
function pageCfg(page) {
    var c = pageAccess[page] || DEFAULT_PAGE_ACCESS[page] || { min_level: 0, show_in_nav: 1 };
    return { min_level: c.min_level || 0, show_in_nav: c.show_in_nav ? 1 : 0 };
}
function canAccess(page) { return myLevel() >= pageCfg(page).min_level; }
function levelOptions(sel) {
    var o = '';
    for (var i = 0; i <= 5; i++) {
        var c = levelColor(i);
        o += '<option value="' + i + '"' + (i === sel ? ' selected' : '') + ' style="color:' + c + '">' + levelName(i) + '</option>';
    }
    return o;
}
function openModal(title, bodyHtml, footHtml) {
    var root = document.getElementById('modalRoot');
    root.classList.remove('closing');
    document.getElementById('modalTitle').textContent = title || '';
    document.getElementById('modalBody').innerHTML = bodyHtml || '';
    document.getElementById('modalFoot').innerHTML = footHtml || '';
    root.classList.remove('hide');
}
function closeModal() {
    var root = document.getElementById('modalRoot');
    if (root.classList.contains('hide')) return;
    root.classList.add('closing');
    setTimeout(function() {
        root.classList.add('hide');
        root.classList.remove('closing');
        document.getElementById('modalBody').innerHTML = '';
        document.getElementById('modalFoot').innerHTML = '';
    }, 180);
}
async function btnRun(btn, fn) {
    if (btn.dataset.busy) return false;
    btn.dataset.busy = '1';
    var old = btn.innerHTML;
    var svg = btn.querySelector('svg');
    if (svg) svg.outerHTML = SPIN_SVG;
    else btn.innerHTML = SPIN_SVG + old;
    var ok = true;
    try {
        await fn();
    } catch (e) {
        ok = false;
    } finally {
        btn.innerHTML = old;
        delete btn.dataset.busy;
    }
    return ok;
}
function toggleUserMenu(e) {
    e.stopPropagation();
    document.getElementById('userMenu').classList.toggle('hide');
}
document.addEventListener('click', function(e) {
    document.getElementById('userMenu').classList.add('hide');
    var pw = document.querySelector('.picker-wrap');
    if (pw && !pw.contains(e.target)) {
        var drop = document.getElementById('assignDrop');
        if (drop) drop.classList.add('hide');
    }
});
var nowPage = 'home';
var barNum = 0;
function topBarOn() {
    barNum++;
    document.getElementById('topBar').classList.add('on');
}
function topBarOff() {
    barNum--;
    if (barNum < 1) document.getElementById('topBar').classList.remove('on');
}
function showPage(name) {
    nowPage = name;
    var navName = NAV_OF[name] || name;
    document.querySelectorAll('.nav-item').forEach(function(n) { n.classList.toggle('now', n.dataset.page === navName); });
    document.querySelectorAll('.page').forEach(function(p) { p.classList.add('hide'); });
    var pageId = 'page' + name.charAt(0).toUpperCase() + name.slice(1);
    if (name === 'tododetail') pageId = 'pageTodoDetail';
    document.getElementById(pageId).classList.remove('hide');
    window.scrollTo({ top: 0 });
}
async function switchPage(name, el) {
    if (name === nowPage) return;
    if (!canAccess(name)) return;
    var fn = PAGE_LOADER[name];
    if (fn) {
        topBarOn();
        try {
            if (el) {
                if (!await btnRun(el, fn)) return;
            } else {
                await fn();
            }
        } finally {
            topBarOff();
        }
    }
    history.pushState(null, '', PAGE_PATH[name]);
    showPage(name);
}
function pageFromPath() {
    var p = location.pathname;
    if (p === '/todos/add') return 'addtodo';
    if (/^\/todos\/\d+$/.test(p)) return 'tododetail';
    if (p === '/todos' || p.indexOf('/todos/') === 0) return 'todo';
    for (var k in PAGE_PATH) {
        if (PAGE_PATH[k] === p) return k;
    }
    return 'home';
}
window.addEventListener('popstate', function() {
    var p = pageFromPath();
    showPage(p);
    if (p === 'tododetail') {
        var m = location.pathname.match(/^\/todos\/(\d+)$/);
        if (m) loadTodoDetail(m[1]);
    }
});
function doSearch(kw) {
    kw = kw.trim().toLowerCase();
    document.querySelectorAll('.card').forEach(function(c) {
        c.style.display = (!kw || c.textContent.toLowerCase().indexOf(kw) > -1) ? '' : 'none';
    });
}
async function loadMe() {
    var ret = await getJson('/api/me');
    var u = ret.data;
    meUser = u;
    document.getElementById('pfName').textContent = u.name;
    document.getElementById('pfMail').textContent = u.email;
    document.getElementById('pfRole').innerHTML = lvlBadge(u.level || 0);
    document.getElementById('sideName').textContent = u.name;
    document.getElementById('sideMail').textContent = u.email;
    document.getElementById('sideAvatar').src = avatarUrl(u);
    var canPublish = (u.level || 0) >= 4;
    var nb = document.getElementById('noticeAddBtn'); if (nb) nb.classList.toggle('hide', !canPublish);
    var pb = document.getElementById('projectAddBtn'); if (pb) pb.classList.toggle('hide', !canPublish);
    document.getElementById('heroText').textContent = '嘿, ' + u.name + '! 欢迎回到烟雨庭. 这里汇总了你的待办、团队通知和正在进行的项目, 一起把服务器做得更好吧.';
    var skillBox = document.getElementById('pfSkill');
    skillBox.innerHTML = renderSkillHtml(u.skill);
}
var CLOCK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0-18 0"/><path d="M12 7v5l3 3"/></g></svg>';
var OK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="st-icon ok" viewBox="0 0 24 24"><path fill="currentColor" d="M17 3.34a10 10 0 1 1-14.995 8.984L2 12l.005-.324A10 10 0 0 1 17 3.34m-1.293 5.953a1 1 0 0 0-1.32-.083l-.094.083L11 12.585l-1.293-1.292l-.094-.083a1 1 0 0 0-1.403 1.403l.083.094l2 2l.094.083a1 1 0 0 0 1.226 0l.094-.083l4-4l.083-.094a1 1 0 0 0-.083-1.32"/></svg>';
var NO_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="st-icon no" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2c5.523 0 10 4.477 10 10a10 10 0 0 1-19.995.324L2 12l.004-.28C2.152 6.327 6.57 2 12 2m.01 13l-.127.007a1 1 0 0 0 0 1.986L12 17l.127-.007a1 1 0 0 0 0-1.986zM12 7a1 1 0 0 0-.993.883L11 8v4l.007.117a1 1 0 0 0 1.986 0L13 12V8l-.007-.117A1 1 0 0 0 12 7"/></svg>';
var CHECK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5 12l5 5L20 7"/></svg>';
var UNDO_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="m9 14l-4-4l4-4"/><path d="M5 10h11a4 4 0 1 1 0 8h-1"/></g></svg>';
var LINK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6m-7 1l9-9m-5 0h5v5"/></svg>';
var X_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 6L6 18M6 6l12 12"/></svg>';
function chipHtml(done) {
    return done ? '<span class="chip ok">Complete</span>' : '<span class="chip no">Incomplete</span>';
}
function isInnerTodo(href) {
    return /^\/todos\/\d+$/.test(href || '');
}
function todoLinkHtml(it) {
    var inner = isInnerTodo(it.link);
    return '<a class="todo-link" href="' + esc(it.link) + '"' + (inner ? '' : ' target="_blank"') +
        ' onclick="return todoLinkClick(event, this)">' + esc(it.title) + LINK_SVG + '</a>';
}
async function loadTodo() {
    var ret = await getJson('/api/todo');
    var homeBox = document.getElementById('todoList');
    var pageBox = document.getElementById('todoPageList');
    if (!ret.data || !ret.data.length) {
        homeBox.innerHTML = '<div class="empty-tip">暂时没有待办, 很清闲喵</div>';
        pageBox.innerHTML = '<div class="empty-tip">暂时没有待办, 很清闲喵</div>';
        return;
    }
    homeBox.innerHTML = ret.data.slice(0, 3).map(function(it) {
        return '<div class="todo-item' + (it.is_done ? ' done' : '') + '">' + CLOCK_SVG +
            '<div class="t">' + todoLinkHtml(it) + '</div>' + chipHtml(it.is_done) + '</div>';
    }).join('');
    pageBox.innerHTML = ret.data.map(function(it) {
        var t = todoLinkHtml(it);
        var btn = it.is_done
        ? '<button class="act-btn" onclick="btnRun(this, function(){ return markDone(' + it.id + ', false) })">' + UNDO_SVG + ' 撤销确认</button>'
        : '<button class="act-btn" onclick="btnRun(this, function(){ return markDone(' + it.id + ', true) })">' + CHECK_SVG + ' 我已完成</button>';
        var desc = it.content ? '<div class="t-desc">' + esc(it.content) + '</div>' : '';
        var gTag = it.is_global ? '<span class="chip global-tag">全局</span>' : '';
        var meta = '<div class="t-meta">' + gTag + '由 ' + esc(it.creator_name) + ' 创建 · ' + esc(it.created_at) + '</div>';
        return '<div class="trow' + (it.is_done ? ' done' : '') + '" data-tid="' + it.id + '">' + (it.is_done ? OK_SVG : NO_SVG) +
            '<div class="t-body"><div class="t-line">' + t + chipHtml(it.is_done) + '</div>' + desc + meta + '</div>' + btn + '</div>';
    }).join('');
}
async function markDone(id, done) {
    await postJson('/api/todo', { id: id, done: done });
    await loadTodo();
}
function todoLinkClick(e, a) {
    var href = a.getAttribute('href');
    if (!isInnerTodo(href)) return true;
    e.preventDefault();
    openTodo(href.split('/')[2]);
    return false;
}
var __todoDetailId = null;
async function openTodo(tid, el) {
    if (el) {
        topBarOn();
        try { if (!await btnRun(el, function() { return loadTodoDetail(tid); })) return; } finally { topBarOff(); }
    } else {
        topBarOn();
        try { await loadTodoDetail(tid); } finally { topBarOff(); }
    }
    history.pushState(null, '', '/todos/' + tid);
    showPage('tododetail');
}
async function loadTodoDetail(tid) {
    __todoDetailId = tid;
    var box = document.getElementById('todoDetailBox');
    box.innerHTML = '<div style="text-align:center;padding:40px">' + SPIN_SVG + '</div>';
    try {
        var ret = await getJson('/api/todo_detail?id=' + tid);
        if (ret.code !== 0) {
            box.innerHTML = '<div class="empty-tip">' + esc(ret.message || '加载失败') + '</div>';
            return;
        }
        renderTodoDetail(ret.data);
    } catch (e) {
        box.innerHTML = '<div class="empty-tip">网络错误, 请重试</div>';
    }
}
function renderTodoDetail(d) {
    var t = d.todo;
    var icon = d.my_done ? OK_SVG : NO_SVG;
    var gTag = t.is_global ? '<span class="chip global-tag">全局</span>' : '';
    var head = '<div class="td-head">' + icon + '<span class="td-title">#' + esc(t.id) + ' · ' + esc(t.title) + '</span>' + gTag + '</div>';
    var creator = { id: t.creator_id, name: t.creator_name, avatar: t.creator_avatar };
    var creatorLine = '<div class="td-meta">' +
        '<img class="td-ava" src="' + avatarUrl(creator) + '" alt="">' +
        '<span class="td-name">' + esc(t.creator_name) + '</span>' +
        '<span class="td-sep">|</span>' +
        '<span class="td-time">创建时间 ' + esc(t.created_at) + '</span>' +
        '</div>';
    var assigneeHtml = '';
    if (t.is_global) {
        assigneeHtml = '<div class="td-section"><div class="td-label">目标</div><div class="td-assignees"><span class="chip global-tag">全体成员</span></div></div>';
    } else if (d.assignees && d.assignees.length) {
        var chips = d.assignees.map(function(u) {
            return '<div class="td-person"><img src="' + avatarUrl(u) + '" alt=""><span>' + esc(u.name) + '</span></div>';
        }).join('');
        assigneeHtml = '<div class="td-section"><div class="td-label">目标</div><div class="td-assignees">' + chips + '</div></div>';
    }
    var contentHtml = t.content ? '<div class="td-section"><div class="td-label">内容</div><div class="td-content">' + esc(t.content) + '</div></div>' : '';
    var doneHtml = '';
    if (d.done_users && d.done_users.length) {
        var doneChips = d.done_users.map(function(u) {
            return '<div class="td-person done"><img src="' + avatarUrl(u) + '" alt=""><span>' + esc(u.name) + '</span>' + CHECK_SVG + '</div>';
        }).join('');
        doneHtml = '<div class="td-section"><div class="td-label">已完成的用户</div><div class="td-assignees">' + doneChips + '</div></div>';
    }
    var actionHtml = '';
    if (d.my_done) {
        actionHtml = '<div class="td-actions">' +
            '<button class="act-btn" onclick="btnRun(this, function(){ return markTodoDetailDone(false) })">' + UNDO_SVG + ' 撤销确认</button>' +
            '<span class="td-my-done">你已于 ' + esc(d.my_done_at) + ' 完成</span>' +
            '</div>';
    } else {
        actionHtml = '<div class="td-actions">' +
            '<button class="add-todo-btn" onclick="btnRun(this, function(){ return markTodoDetailDone(true) })">' + CHECK_SVG + ' 我已完成</button>' +
            '</div>';
    }
    document.getElementById('todoDetailBox').innerHTML = '<div class="card td-card">' + head + creatorLine + assigneeHtml + contentHtml + doneHtml + actionHtml + '</div>';
}
async function markTodoDetailDone(done) {
    if (!__todoDetailId) return;
    await postJson('/api/todo', { id: parseInt(__todoDetailId), done: done });
    await loadTodoDetail(__todoDetailId);
}
var assignUsers = [];
function toggleGlobalTodo() {
    var isGlobal = document.getElementById('atGlobal').checked;
    document.getElementById('assignRow').classList.toggle('hide', isGlobal);
}
function resetAddTodo() {
    document.getElementById('atTitle').value = '';
    document.getElementById('atLink').value = '';
    document.getElementById('atContent').value = '';
    document.getElementById('atErr').textContent = '';
    document.getElementById('assignInput').value = '';
    document.getElementById('assignDrop').classList.add('hide');
    document.getElementById('atGlobal').checked = false;
    document.getElementById('assignRow').classList.remove('hide');
    assignUsers = [];
    renderChips();
}
function renderChips() {
    var picker = document.getElementById('assignPicker');
    var input = document.getElementById('assignInput');
    picker.querySelectorAll('.u-chip').forEach(function(c) { c.remove(); });
    assignUsers.forEach(function(u) {
        var chip = document.createElement('span');
        chip.className = 'u-chip';
        chip.innerHTML = '<img src="' + avatarUrl(u) + '" alt=""><span>' + esc(u.name) + '</span><span class="rm" data-id="' + u.id + '">' + X_SVG + '</span>';
        chip.querySelector('.rm').onclick = function(e) { e.stopPropagation(); removeChip(u.id); };
        picker.insertBefore(chip, input);
    });
}
function removeChip(id) {
    assignUsers = assignUsers.filter(function(u) { return u.id !== id; });
    renderChips();
}
function addChip(u) {
    if (!assignUsers.some(function(x) { return x.id === u.id; })) assignUsers.push(u);
    document.getElementById('assignInput').value = '';
    document.getElementById('assignDrop').classList.add('hide');
    renderChips();
    document.getElementById('assignInput').focus();
}
function assignKey(e) {
    if (e.key === 'Backspace' && !e.target.value && assignUsers.length) {
        removeChip(assignUsers[assignUsers.length - 1].id);
    }
}
var searchTimer = null;
function searchUser(kw) {
    kw = (kw || '').trim();
    var drop = document.getElementById('assignDrop');
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(async function() {
        try {
            var ret = await getJson('/api/user_search?q=' + encodeURIComponent(kw));
            var list = (ret.data || []).filter(function(u) {
                return !assignUsers.some(function(x) { return x.id === u.id; });
            });
            if (!list.length) {
                drop.innerHTML = '<div class="drop-empty">没有匹配的用户</div>';
            } else {
                drop.innerHTML = '';
                list.forEach(function(u) {
                    var row = document.createElement('div');
                    row.className = 'drop-row';
                    row.innerHTML = '<img src="' + avatarUrl(u) + '" alt=""><div><div class="dn">' + esc(u.name) + '</div><div class="de">' + esc(u.email) + '</div></div>';
                    row.onclick = function() { addChip({ id: u.id, name: u.name }); };
                    drop.appendChild(row);
                });
            }
            drop.classList.remove('hide');
        } catch (e) {}
    }, kw ? 160 : 0);
}
async function submitTodo() {
    var err = document.getElementById('atErr');
    err.textContent = '';
    var title = document.getElementById('atTitle').value.trim();
    if (!title) { err.textContent = '标题不能为空'; return; }
    var isGlobal = document.getElementById('atGlobal').checked;
    var body = {
        title: title,
        link: document.getElementById('atLink').value.trim(),
        content: document.getElementById('atContent').value.trim(),
        is_global: isGlobal
    };
    if (!isGlobal) {
        body.assignees = assignUsers.map(function(u) { return u.id; });
    }
    var ret = await postJson('/api/todo', body);
    if (ret.code === 0) {
        resetAddTodo();
        await switchPage('todo');
    } else {
        err.textContent = ret.message || '创建失败';
    }
}
var DESKTOP_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="dv-icon" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zm4 15h10m-8-4v4m6-4v4"/></svg>';
var MOBILE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="dv-icon" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2zm5-1h2m-1 13v.01"/></svg>';
var LOGOUT_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="M14 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2"/><path d="M9 12h12l-3-3m0 6l3-3"/></g></svg>';
var ovData = null;
function renderSkillHtml(raw) {
    if (!raw) return '<span class="empty-tip">未填写</span>';
    var list = String(raw).split(/[,，]/).map(function(x) { return x.trim(); }).filter(Boolean);
    if (!list.length) return '<span class="empty-tip">未填写</span>';
    var lookup = window.__SKILL_META || {};
    return list.map(function(nm) {
        var m = null;
        for (var k in lookup) {
            if (lookup[k] && lookup[k].name === nm) { m = lookup[k]; break; }
        }
        var c = m ? m.color : '#ef5777';
        return '<span class="skill-tag sm" style="color:' + c + ';border-color:' + hexA(c,.45) + ';background:' + hexA(c,.08) + '">' + esc(nm) + '</span>';
    }).join('');
}
function hexA(hex, a) {
    var h = (hex || '#ef5777').replace('#','');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var r = parseInt(h.substr(0,2),16), g = parseInt(h.substr(2,2),16), b = parseInt(h.substr(4,2),16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + (a||0.1) + ')';
}
async function loadOverview() {
    var ret = await getJson('/api/overview');
    ovData = ret.data;
    var u = ovData.user;
    document.getElementById('ovName').textContent = u.name;
    var roleEl = document.getElementById('ovRole');
    var c = levelColor(u.level || 0);
    roleEl.outerHTML = roleEl.outerHTML; // noop keep
    roleEl = document.getElementById('ovRole');
    roleEl.style.color = c;
    roleEl.style.borderColor = hexA(c, .45);
    roleEl.style.background = hexA(c, .08);
    roleEl.innerHTML = lvlBadge(u.level || 0);
    document.getElementById('ovMail').textContent = u.email;
    document.getElementById('ovAvatar').src = avatarUrl(u);
    document.getElementById('ovSkill').innerHTML = renderSkillHtml(u.skill);
    document.getElementById('ovBio').textContent = u.bio || '未填写';
    document.getElementById('ovId').textContent = u.id;
    var bt = document.getElementById('ovCreateInviteBtn');
    if (bt) bt.classList.toggle('hide', !canAccess('invite_create'));
    document.getElementById('stYesterday').textContent = ovData.calls.yesterday;
    document.getElementById('stToday').textContent = ovData.calls.today;
    document.getElementById('stWeek').textContent = ovData.calls.week;
    document.getElementById('stMonth').textContent = ovData.calls.month;
    document.getElementById('apikeyInput').value = ovData.apikey;
    renderApikeyBox();
    renderOvInvites(ovData.invites);
    var dvBox = document.getElementById('deviceList');
    dvBox.innerHTML = ovData.sessions.map(function(s) {
        var icon = /mobile|android|iphone/i.test(s.ua || '') ? MOBILE_SVG : DESKTOP_SVG;
        var cur = s.is_current ? '<span class="chip ok">本机</span>' : '';
        return '<div class="dev-row">' + icon +
            '<div class="dv-main"><div class="dv-ip">' + esc(s.ip || '未知IP') + cur + '</div>' +
            '<div class="dv-ua">' + esc(s.ua || '未知设备') + '</div>' +
            '<div class="dv-time">' + esc(s.created_at) + '</div></div>' +
            '<button class="act-btn" onclick="btnRun(this, function(){ return killSession(' + s.id + ', ' + s.is_current + ') })">' + LOGOUT_SVG + ' 登出</button></div>';
    }).join('');
}
function renderOvInvites(invites) {
    var ivBox = document.getElementById('inviteList');
    if (!invites || !invites.length) {
        ivBox.innerHTML = '<div class="empty-tip">还没有创建过邀请码</div>';
        return;
    }
    ivBox.innerHTML = invites.map(function(iv) {
        var used = !!iv.used_at;
        var top = '<div class="iv-top"><span class="iv-code">#' + esc(iv.code) + '</span>' +
            (used ? '<span class="chip no">已被使用</span>' : '<span class="chip ok">未使用</span>') + '</div>';
        var mid = used
        ? '<div class="iv-user"><img src="' + avatarUrl({avatar: iv.used_avatar}) + '" alt=""><div><div class="iv-un">' + esc(iv.used_name) + '</div><div class="iv-ue">' + esc(iv.used_email) + '</div></div></div>' +
          '<div class="iv-date">创建日期: ' + esc(iv.created_at) + '<br>使用日期: ' + esc(iv.used_at) + '</div>'
        : '<div class="iv-date">创建日期: ' + esc(iv.created_at) + '</div>' +
          '<div style="margin-top:10px"><button class="act-btn" style="width:100%;justify-content:center" onclick="copyText(\'' + esc(iv.code) + '\', this)">' + '复制邀请码</button></div>';
        return '<div class="invite-box">' + top + mid + '</div>';
    }).join('');
}
async function refreshOvInvite() {
    var ret = await getJson('/api/overview');
    ovData = ret.data;
    renderOvInvites(ovData.invites);
}
function openProfileModal() {
    if (!ovData) return;
    var u = ovData.user;
    var avatarHtml = '<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">' +
        '<div class="avatar-upload" id="pmAvatarUpload" onclick="document.getElementById(\'pmAvatarInput\').click()" style="width:80px;height:80px">' +
        '<img id="pmAvatar" src="' + avatarUrl(u) + '" alt="">' +
        '<div class="avatar-overlay"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" r="4" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg><span>更换头像</span></div>' +
        '</div>' +
        '<input type="file" id="pmAvatarInput" accept="image/jpeg,image/png,image/webp,image/gif" style="display:none" onchange="uploadModalAvatar(this)">' +
        '<div style="color:#888;font-size:13px">点击头像上传新图片<br>支持 jpg / png / webp / gif</div></div>';
    var formHtml = '<div class="md-section">' +
        '<div class="md-row"><div class="md-k">昵称</div><div class="md-v"><input id="pmName" value="' + esc(u.name || '') + '"></div></div>' +
        '<div class="md-row"><div class="md-k">核心能力</div><div class="md-v"><div class="picker-wrap"><div class="picker" id="pfSkillPicker" onclick="document.getElementById(\'pfSkillInput\').focus()"><input id="pfSkillInput" placeholder="选择核心能力" autocomplete="off" onfocus="skillPickerSearch(this.value,\'pf\')" oninput="skillPickerSearch(this.value,\'pf\')" onkeydown="skillPickerKey(event,\'pf\')"></div><div class="picker-drop hide" id="pfSkillDrop"></div></div></div></div>' +
        '<div class="md-row"><div class="md-k">个人简介</div><div class="md-v"><textarea id="pmBio" placeholder="介绍一下自己..." style="resize:vertical;min-height:60px;max-height:160px">' + esc(u.bio || '') + '</textarea></div></div>' +
        '</div>';
    var foot = '<button class="act-btn" onclick="closeModal()">取消</button>' +
        '<button class="add-todo-btn" onclick="btnRun(this, saveProfileModal)">保存修改</button>';
    openModal('修改个人资料', avatarHtml + formHtml, foot);
    setTimeout(function() { initSkillPicker('pf', u.skill || ''); }, 0);
}
function syncAvatars() {
    if (!meUser) return;
    var url = avatarUrl(meUser);
    var els = ['sideAvatar', 'ovAvatar', 'pfAvatar'];
    els.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.src = url;
    });
}
async function uploadModalAvatar(input) {
    var file = input.files && input.files[0];
    if (!file) return;
    input.value = '';
    var allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
    if (allowed.indexOf(file.type) < 0) {
        notify(null, '格式不支持', '仅支持 jpg / png / webp / gif 格式', 4000, '', false);
        return;
    }
    var btn = document.getElementById('pmAvatarUpload');
    var oldHtml = '';
    if (btn) {
        oldHtml = btn.innerHTML;
        btn.innerHTML = '<img src="' + (meUser ? avatarUrl(meUser) : '/assets/yyt64x.png') + '" alt="" style="opacity:.3"><div class="avatar-overlay" style="opacity:1">' + SPIN_SVG + '</div>';
        btn.style.cursor = 'wait';
    }
    try {
        var fd = new FormData();
        fd.append('avatar', file);
        var res = await fetch('/api/avatar_upload', { method: 'POST', body: fd });
        var ret = await res.json();
        if (ret.code === 0) {
            var url = ret.data.avatar;
            if (meUser) meUser.avatar = url;
            syncAvatars();
            var img = document.getElementById('pmAvatar');
            if (img) img.src = url;
            notify(null, '头像更新成功', '点击「保存修改」以应用', 3000, '', false);
        } else {
            notify(null, '上传失败', ret.message || '服务器错误', 4000, '', false);
        }
    } catch (e) {
        notify(null, '上传失败', '网络错误，请重试', 4000, '', false);
    } finally {
        if (btn) { btn.style.cursor = ''; btn.innerHTML = oldHtml; }
    }
}
async function saveProfileModal(btn) {
    var name = document.getElementById('pmName').value.trim();
    if (!name) { markErr(document.getElementById('pmName'), '昵称不能为空'); return; }
    var ret = await postJson('/api/profile', {
        name: name,
        skill: getSkillPickerValues('pf'),
        bio: document.getElementById('pmBio').value.trim()
    });
    if (ret.code === 0) {
        closeModal();
        await Promise.all([loadOverview(), loadMe()]);
        notify(null, '资料已更新', '你的个人资料已保存', 3000, '', false);
    }
}
async function uploadAvatar(input) {
    var file = input.files && input.files[0];
    if (!file) return;
    input.value = '';
    var allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
    if (allowed.indexOf(file.type) < 0) {
        notify(null, '格式不支持', '仅支持 jpg / png / webp / gif 格式', 4000, '', false);
        return;
    }
    var btn = document.getElementById('avatarUpload');
    var oldHtml = '';
    if (btn) {
        oldHtml = btn.innerHTML;
        btn.innerHTML = '<img src="' + (meUser ? avatarUrl(meUser) : '/assets/yyt64x.png') + '" alt="" style="opacity:.3"><div class="avatar-overlay" style="opacity:1">' + SPIN_SVG + '</div>';
        btn.style.cursor = 'wait';
    }
    try {
        var fd = new FormData();
        fd.append('avatar', file);
        var res = await fetch('/api/avatar_upload', { method: 'POST', body: fd });
        var ret = await res.json();
        if (ret.code === 0) {
            var url = ret.data.avatar;
            if (meUser) meUser.avatar = url;
            syncAvatars();
            notify(null, '头像更新成功', '你的新头像已生效', 3000, '', false);
        } else {
            notify(null, '上传失败', ret.message || '服务器错误', 4000, '', false);
        }
    } catch (e) {
        notify(null, '上传失败', '网络错误，请重试', 4000, '', false);
    } finally {
        if (btn) {
            btn.style.cursor = '';
            btn.innerHTML = oldHtml;
            if (meUser) document.getElementById('ovAvatar').src = avatarUrl(meUser);
        }
    }
}
async function createInvite() {
    var ret = await postJson('/api/invite_create', {});
    if (ret.code === 0) await loadOverview();
}
function renderApikeyBox() {
    var has = !!(ovData && ovData.apikey);
    document.getElementById('apikeyHas').classList.toggle('hide', !has);
    document.getElementById('apikeyNone').classList.toggle('hide', has);
    document.getElementById('apikeyResetBtn').classList.toggle('hide', !has);
    document.getElementById('apikeyApplyBtn').classList.toggle('hide', has);
}
async function resetApikey() {
    var ret = await postJson('/api/apikey_reset', {});
    if (ret.code === 0) {
        if (ovData) ovData.apikey = ret.data.apikey;
        document.getElementById('apikeyInput').value = ret.data.apikey;
        renderApikeyBox();
    }
}
async function loadLogs() {
    var ret = await getJson('/api/logs');
    var box = document.getElementById('logList');
    var list = ret.data || [];
    if (!list.length) {
        box.innerHTML = '<div class="empty-tip">还没有任何调用记录</div>';
        return;
    }
    box.innerHTML = list.map(function(it) {
        return '<div class="trow"><div class="t-body"><div class="t-line"><span class="t-title">' + esc(it.path || '--') + '</span></div>' +
            '<div class="t-meta">IP: ' + esc(it.ip || '未知') + ' · ' + esc(it.created_at) + '</div></div></div>';
    }).join('');
}
function _add32(a, b) { return (a + b) & 0xFFFFFFFF; }
function _cmn(q, a, b, x, s, t) { a = _add32(_add32(a, q), _add32(x, t)); return _add32((a << s) | (a >>> (32 - s)), b); }
function _ff(a,b,c,d,x,s,t){ return _cmn((b&c)|((~b)&d), a, b, x, s, t); }
function _gg(a,b,c,d,x,s,t){ return _cmn((b&d)|(c&(~d)), a, b, x, s, t); }
function _hh(a,b,c,d,x,s,t){ return _cmn(b^c^d, a, b, x, s, t); }
function _ii(a,b,c,d,x,s,t){ return _cmn(c^(b|(~d)), a, b, x, s, t); }
function _md5blk(s) { var m = [], i; for (i = 0; i < 64; i += 4) m[i>>2] = s.charCodeAt(i) + (s.charCodeAt(i+1)<<8) + (s.charCodeAt(i+2)<<16) + (s.charCodeAt(i+3)<<24); return m; }
function _md5cycle(x, k) {
    var a=x[0],b=x[1],c=x[2],d=x[3];
    a=_ff(a,b,c,d,k[0],7,-680876936);d=_ff(d,a,b,c,k[1],12,-389564586);c=_ff(c,d,a,b,k[2],17,606105819);b=_ff(b,c,d,a,k[3],22,-1044525330);
    a=_ff(a,b,c,d,k[4],7,-176418897);d=_ff(d,a,b,c,k[5],12,1200080426);c=_ff(c,d,a,b,k[6],17,-1473231341);b=_ff(b,c,d,a,k[7],22,-45705983);
    a=_ff(a,b,c,d,k[8],7,1770035416);d=_ff(d,a,b,c,k[9],12,-1958414417);c=_ff(c,d,a,b,k[10],17,-42063);b=_ff(b,c,d,a,k[11],22,-1990404162);
    a=_ff(a,b,c,d,k[12],7,1804603682);d=_ff(d,a,b,c,k[13],12,-40341101);c=_ff(c,d,a,b,k[14],17,-1502002290);b=_ff(b,c,d,a,k[15],22,1236535329);
    a=_gg(a,b,c,d,k[1],5,-165796510);d=_gg(d,a,b,c,k[6],9,-1069501632);c=_gg(c,d,a,b,k[11],14,643717713);b=_gg(b,c,d,a,k[0],20,-373897302);
    a=_gg(a,b,c,d,k[5],5,-701558691);d=_gg(d,a,b,c,k[10],9,38016083);c=_gg(c,d,a,b,k[15],14,-660478335);b=_gg(b,c,d,a,k[4],20,-405537848);
    a=_gg(a,b,c,d,k[9],5,568446438);d=_gg(d,a,b,c,k[14],9,-1019803690);c=_gg(c,d,a,b,k[3],14,-187363961);b=_gg(b,c,d,a,k[8],20,1163531501);
    a=_gg(a,b,c,d,k[13],5,-1444681467);d=_gg(d,a,b,c,k[2],9,-51403784);c=_gg(c,d,a,b,k[7],14,1735328473);b=_gg(b,c,d,a,k[12],20,-1926607734);
    a=_hh(a,b,c,d,k[5],4,-378558);d=_hh(d,a,b,c,k[8],11,-2022574463);c=_hh(c,d,a,b,k[11],16,1839030562);b=_hh(b,c,d,a,k[14],23,-35309556);
    a=_hh(a,b,c,d,k[1],4,-1530992060);d=_hh(d,a,b,c,k[4],11,1272893353);c=_hh(c,d,a,b,k[7],16,-155497632);b=_hh(b,c,d,a,k[10],23,-1094730640);
    a=_hh(a,b,c,d,k[13],4,681279174);d=_hh(d,a,b,c,k[0],11,-358537222);c=_hh(c,d,a,b,k[3],16,-722521979);b=_hh(b,c,d,a,k[6],23,76029189);
    a=_hh(a,b,c,d,k[9],4,-640364487);d=_hh(d,a,b,c,k[12],11,-421815835);c=_hh(c,d,a,b,k[15],16,530742520);b=_hh(b,c,d,a,k[2],23,-995338651);
    a=_ii(a,b,c,d,k[0],6,-198630844);d=_ii(d,a,b,c,k[7],10,1126891415);c=_ii(c,d,a,b,k[14],15,-1416354905);b=_ii(b,c,d,a,k[5],21,-57434055);
    a=_ii(a,b,c,d,k[12],6,1700485571);d=_ii(d,a,b,c,k[3],10,-1894986606);c=_ii(c,d,a,b,k[10],15,-1051523);b=_ii(b,c,d,a,k[1],21,-2054922799);
    a=_ii(a,b,c,d,k[8],6,1873313359);d=_ii(d,a,b,c,k[15],10,-30611744);c=_ii(c,d,a,b,k[6],15,-1560198380);b=_ii(b,c,d,a,k[13],21,1309151649);
    a=_ii(a,b,c,d,k[4],6,-145523070);d=_ii(d,a,b,c,k[11],10,-1120210379);c=_ii(c,d,a,b,k[2],15,718787259);b=_ii(b,c,d,a,k[9],21,-343485551);
    x[0]=_add32(a,x[0]);x[1]=_add32(b,x[1]);x[2]=_add32(c,x[2]);x[3]=_add32(d,x[3]);
}
function _md51(s) {
    var n=s.length, state=[1732584193,-271733879,-1732584194,271733878], i;
    for (i=64;i<=n;i+=64) _md5cycle(state, _md5blk(s.substring(i-64,i)));
    s = s.substring(i-64);
    var tail=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
    for (i=0;i<s.length;i++) tail[i>>2] |= s.charCodeAt(i) << ((i%4)<<3);
    tail[i>>2] |= 0x80 << ((i%4)<<3);
    if (i>55) { _md5cycle(state, tail); for (i=0;i<16;i++) tail[i]=0; }
    tail[14] = n*8;
    _md5cycle(state, tail);
    return state;
}
var _hexc = '0123456789abcdef'.split('');
function _rhex(n){ var s='',j=0; for(;j<4;j++) s += _hexc[(n>>(j*8+4))&0x0F] + _hexc[(n>>(j*8))&0x0F]; return s; }
function _hex(x){ for (var i=0;i<x.length;i++) x[i]=_rhex(x[i]); return x.join(''); }
function _md5raw(s){ var st=_md51(s), o='',i; for(i=0;i<4;i++){ var v=st[i]; o += String.fromCharCode(v&0xff,(v>>8)&0xff,(v>>16)&0xff,(v>>24)&0xff);} return o; }
function _utf8(s){ return unescape(encodeURIComponent(s)); }
function hmacMd5(key, data) {
    key = _utf8(key); data = _utf8(data);
    if (key.length > 64) key = _md5raw(key);
    var ipad='', opad='';
    for (var i=0;i<64;i++){ var c = i < key.length ? key.charCodeAt(i) : 0; ipad += String.fromCharCode(c^0x36); opad += String.fromCharCode(c^0x5c); }
    var inner = _md5raw(ipad + data);
    return _hex(_md51(opad + inner));
}
async function loadMcsm() {
    var box = document.getElementById('mcsmBox');
    var ret = await getJson('/api/mcsm_info');
    var d = ret.data || {};
    if (!d.is_admin) { box.innerHTML = '<div class="mcsm-tip">仅管理员及以上可访问 MCSManager 面板.</div>'; return; }
    if (!d.token || !d.panel_host) { box.innerHTML = '<div class="mcsm-tip">请先在「个人概览」申请 API KEY (会同时分配你的专属面板入口) 后再访问.</div>'; return; }
    if (!d.panel_suffix) { box.innerHTML = '<div class="mcsm-tip">管理员尚未配置面板域名后缀.</div>'; return; }
    var url = 'https://' + d.panel_host + '.' + d.panel_suffix + '/?token=' + encodeURIComponent(d.token);
    box.innerHTML = '<div class="mcsm-frame-wrap"><iframe src="' + url + '"></iframe></div>';
}
function mcsmRefresh() {
    var iframe = document.querySelector('#mcsmBox iframe');
    if (iframe) {
        btnRun(document.querySelector('#mcsmToolbar button'), async function() {
            iframe.src = iframe.src;
        });
    } else {
        loadMcsm();
    }
}
function mcsmTutorial() {
    var body = '<div style="text-align:center">' +
        '<div class="mcsm-tut-video">视频教程即将上线</div>' +
        '<div style="color:#777;font-size:13px;margin-top:14px;line-height:1.7">本教程将指导你如何使用 MCSManager 管理服务器实例、<br>查看控制台、上传文件等. 视频资源后续补充.</div>' +
        '</div>';
    var foot = '<button class="add-todo-btn" onclick="closeModal()">知道了</button>';
    openModal('MCSManager 使用教程', body, foot);
}
var __mcsmFsWrap = null;
function mcsmFullscreen() {
    var iframe = document.querySelector('#mcsmBox iframe');
    if (!iframe) return;
    __mcsmFsWrap = iframe.parentNode;
    var overlay = document.createElement('div');
    overlay.className = 'mcsm-fs-overlay';
    overlay.id = 'mcsmFsOverlay';
    overlay.innerHTML =
        '<div class="mcsm-fs-top">@team - YanYuTing / MCSManager</div>' +
        '<div class="mcsm-fs-frame" id="mcsmFsFrame"></div>' +
        '<div class="mcsm-fs-bottom"><button class="mcsm-fs-exit" onclick="mcsmExitFullscreen()"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9H5V5m10 4h4V5M9 15H5v4m10-4h4v4"/></svg> 退出全屏</button></div>';
    document.body.appendChild(overlay);
    document.getElementById('mcsmFsFrame').appendChild(iframe);
    document.body.style.overflow = 'hidden';
}
function mcsmExitFullscreen() {
    var overlay = document.getElementById('mcsmFsOverlay');
    if (!overlay) return;
    var iframe = overlay.querySelector('iframe');
    if (iframe && __mcsmFsWrap) __mcsmFsWrap.appendChild(iframe);
    __mcsmFsWrap = null;
    overlay.classList.add('closing');
    document.body.style.overflow = '';
    setTimeout(function() {
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }, 180);
}
async function mcsmOpenExternal() {
    var ret = await getJson('/api/mcsm_info');
    var d = ret.data || {};
    if (!d.token || !d.panel_host || !d.panel_suffix) return;
    var url = 'https://' + d.panel_host + '.' + d.panel_suffix + '/?token=' + encodeURIComponent(d.token);
    window.open(url, '_blank');
}
async function killSession(sid, isCurrent) {
    var ret = await postJson('/api/session_kill', { sid: sid });
    if (ret.code !== 0) return;
    if (isCurrent) { location.reload(); return; }
    await loadOverview();
}
async function copyText(txt, btn) {
    try {
        await navigator.clipboard.writeText(txt);
    } catch (e) {
        var ta = document.createElement('textarea');
        ta.value = txt;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
    }
    if (btn) {
        var old = btn.innerHTML;
        btn.innerHTML = '已复制';
        setTimeout(function() { btn.innerHTML = old; }, 1000);
    }
}
async function loadApis() {
    var ret = await getJson('/api/api_list');
    var box = document.getElementById('apiList');
    var list = ret.data || [];
    if (!list.length) {
        box.innerHTML = '<div class="empty-tip">还没有配置任何 API</div>';
        return;
    }
    box.innerHTML = list.map(function(a) {
        var method = (a.method || 'GET').toLowerCase();
        var html = '<div class="api-card"><div class="api-top"><span class="api-method ' + esc(method) + '">' + esc((a.method || 'GET').toUpperCase()) + '</span><span class="api-path">' + esc(a.path || '') + '</span></div>';
        if (a.title) html += '<div class="api-desc" style="color:#eee;margin-top:8px">' + esc(a.title) + '</div>';
        if (a.desc) html += '<div class="api-desc">' + esc(a.desc) + '</div>';
        if (a.params && a.params.length) {
            html += '<div class="api-sec"><div class="st-label">PARAMS</div><table class="api-table"><tr><th>参数</th><th>类型</th><th>说明</th></tr>';
            a.params.forEach(function(p) {
                html += '<tr><td><span class="pn">' + esc(p.name || '') + '</span>' + (p.required ? ' <span class="pr">*必填</span>' : '') + '</td><td><span class="pt">' + esc(p.type || '') + '</span></td><td>' + esc(p.desc || '') + '</td></tr>';
            });
            html += '</table></div>';
        }
        if (a.example) {
            var ex = typeof a.example === 'string' ? a.example : JSON.stringify(a.example, null, 2);
            html += '<div class="api-sec"><div class="st-label">EXAMPLE</div><div class="api-example">' + esc(ex) + '</div></div>';
        }
        return html + '</div>';
    }).join('');
}
async function loadNotice() {
    var ret = await getJson('/api/notice');
    var homeBox = document.getElementById('noticeList');
    var pageBox = document.getElementById('noticePageList');
    if (!ret.data || !ret.data.length) {
        homeBox.innerHTML = '<div class="empty-tip">还没有任何通知</div>';
        pageBox.innerHTML = '<div class="empty-tip">还没有任何通知</div>';
        return;
    }
    var render = function(it) {
        return '<div class="notice-item"><div class="tt">' + esc(it.title) + '</div>' +
            (it.content ? '<div class="cc">' + esc(it.content) + '</div>' : '') +
            '<div class="dd">' + esc(it.created_at) + '</div></div>';
    };
    homeBox.innerHTML = ret.data.slice(0, 3).map(render).join('');
    pageBox.innerHTML = ret.data.map(render).join('');
}
async function loadProject() {
    var ret = await getJson('/api/project');
    var homeBox = document.getElementById('projectList');
    var pageBox = document.getElementById('projectPageList');
    if (!ret.data || !ret.data.length) {
        homeBox.innerHTML = '<div class="empty-tip">还没有登记项目</div>';
        pageBox.innerHTML = '<div class="empty-tip">还没有登记项目</div>';
        return;
    }
    var render = function(it) {
        var nm = it.link ? '<a href="' + esc(it.link) + '" target="_blank">' + esc(it.name) + '</a>' : esc(it.name);
        return '<div class="project-item"><div class="proj-name">' + nm + '</div>' +
            (it.info ? '<div class="proj-info">' + esc(it.info) + '</div>' : '') +
            (it.members ? '<div class="proj-mem">成员: ' + esc(it.members) + '</div>' : '') + '</div>';
    };
    homeBox.innerHTML = ret.data.slice(0, 3).map(render).join('');
    pageBox.innerHTML = ret.data.map(render).join('');
}
async function doLogout() {
    await postJson('/api/logout', {});
    location.reload();
}
async function loadPagesConfig() {
    try {
        var r1 = await getJson('/api/admin_levels');
        if (r1.code === 0 && r1.data) {
            var lvs = r1.data.levels || [];
            lvs.forEach(function(m) {
                levelMeta[m.level] = { name: m.name, color: m.color };
            });
            var pgs = r1.data.pages || [];
            pgs.forEach(function(p) {
                pageAccess[p.page_key] = { min_level: p.min_level, show_in_nav: p.show_in_nav };
            });
            return;
        }
    } catch (e) {}
    var ret = await getJson('/api/pages');
    var list = ret.data || [];
    list.forEach(function(p) {
        pageAccess[p.page_key] = { min_level: p.min_level, show_in_nav: p.show_in_nav };
    });
}
function applyNavFilter() {
    var lv = myLevel();
    document.querySelectorAll('.nav-item').forEach(function(n) {
        var page = n.dataset.page;
        if (!page) return;
        var cfg = pageCfg(page);
        n.classList.toggle('hide', !(cfg.show_in_nav && lv >= cfg.min_level));
    });
}
async function loadTeam() {
    var ru = await getJson('/api/admin_users');
    if (ru.code === 403) {
        ['teamGroups','teamMembers','teamInvites','teamStats','teamLogs','teamSkills'].forEach(function(id) {
            var el = document.getElementById(id); if (el) el.innerHTML = '<div class="empty-tip">无权限访问</div>';
        });
        return;
    }
    ALL_USERS = ru.data || [];
    var ret = await Promise.all([
        getJson('/api/admin_invites'),
        getJson('/api/admin_stats'),
        getJson('/api/admin_logs?limit=50'),
        loadPagesConfig().then(function(){}),
        loadSkillsMeta()
    ]);
    applyNavFilter();
    renderTeamGroups(ALL_USERS);
    renderTeamMembers(ALL_USERS);
    renderTeamInvites(ret[0].data || []);
    renderTeamStats(ret[1].data || {});
    renderTeamLogs(ret[2].data || []);
    var sret = await getJson('/api/admin_skills');
    renderTeamSkills(sret.data || []);
}
async function refreshTeamInvites() {
    var ret = await getJson('/api/admin_invites');
    renderTeamInvites(ret.data || []);
}
async function loadSkillsMeta() {
    try {
        var ret = await getJson('/api/skills');
        var arr = (ret.data || []).reduce(function(acc, s) {
            acc[s.id] = { id: s.id, name: s.name, color: s.color || '#ef5777' };
            return acc;
        }, {});
        window.__SKILL_META = arr;
        return arr;
    } catch (e) {
        window.__SKILL_META = window.__SKILL_META || {};
        return window.__SKILL_META;
    }
}
async function reloadSkills() {
    await loadSkillsMeta();
    var ret = await getJson('/api/admin_skills');
    renderTeamSkills(ret.data || []);
}
function renderTeamSkills(list) {
    var box = document.getElementById('teamSkills');
    if (!box) return;
    var addBtn = '<div style="margin-top:12px"><button class="add-todo-btn" onclick="openSkillEdit(null)"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m-7-7h14"/></svg> 新增核心能力</button></div>';
    if (!list || !list.length) {
        box.innerHTML = '<div class="empty-tip">还没有能力标签</div>' + addBtn;
        return;
    }
    var html = '<div class="grp-grid">';
    list.forEach(function(s) {
        var c = s.color || '#ef5777';
        html += '<div class="grp-card">' +
            '<span class="skill-tag sm" style="color:' + c + ';border-color:' + hexA(c,.45) + ';background:' + hexA(c,.08) + '">' + esc(s.name) + '</span>' +
            '<div class="grp-name">' + esc(s.name) + '</div>' +
            '<div class="grp-count">' + (s.count || 0) + ' 人</div>' +
            '<div class="grp-actions">' +
            '<button class="card-head-btn" onclick="openSkillMembers(\'' + escAttr(s.name) + '\')">成员</button>' +
            '<button class="card-head-btn" onclick="openSkillEdit(' + s.id + ',\'' + escAttr(s.name) + '\',\'' + escAttr(c) + '\')">编辑</button>' +
            '<button class="card-head-btn danger" onclick="btnRun(this, function(btn){ return deleteSkill(' + s.id + ',\'' + escAttr(s.name) + '\',btn); })">删除</button>' +
            '</div></div>';
    });
    html += '</div>' + addBtn;
    box.innerHTML = html;
}
function openSkillMembers(sName) {
    var users = (ALL_USERS || []).filter(function(u) {
        var raw = u.skill || '';
        return raw.split(/[,，]/).map(function(x) { return x.trim(); }).indexOf(sName) !== -1;
    });
    var head = '<div style="margin-bottom:10px"><span class="skill-tag sm" style="color:#ef5777;border-color:rgba(239,87,119,.45);background:rgba(239,87,119,.08)">' + esc(sName) + '</span> · 共 ' + users.length + ' 人</div>';
    var html = head + '<div class="group-members">';
    if (!users.length) html += '<div class="empty-tip">该能力暂无成员</div>';
    else {
        html += users.map(function(u) {
            return '<div class="member-bar">' +
                '<img class="mb-ava" src="' + avatarUrl(u) + '" alt=""><div class="mb-main">' +
                '<div class="mb-name">' + esc(u.name) + ' ' + lvlBadge(u.level || 0) + '</div>' +
                '<div class="mb-mail">' + esc(u.email) + '</div>' +
                '<div class="mb-skill">' + renderSkillHtml(u.skill) + '</div></div>' +
                '<button class="act-btn" onclick="openMemberDetail(' + u.id + ')">详情</button></div>';
        }).join('');
    }
    html += '</div>';
    openModal('能力成员 · ' + sName, html, '<button class="add-todo-btn" onclick="closeModal()">关闭</button>');
}
function openSkillEdit(id, name, color) {
    name = name || '';
    color = color || '#ef5777';
    var isNew = !id;
    var title = isNew ? '新增核心能力' : '编辑核心能力';
    var body = '<div class="md-section"><div class="md-label">基础设置</div>' +
        '<div class="md-row"><div class="md-k">名称</div><div class="md-v"><input id="sk_name" value="' + esc(name) + '" placeholder="如 开发/运维/策划"></div></div>' +
        '<div class="md-row"><div class="md-k">标识颜色</div><div class="md-v"><input type="color" class="color-in" id="sk_color" value="' + esc(color) + '"></div></div>' +
        '</div>';
    var foot = '<button class="act-btn" onclick="closeModal()">关闭</button>' +
        '<button class="add-todo-btn" onclick="btnRun(this, function(btn){ return saveSkill(' + (id || 'null') + ',' + isNew + ',btn); })">保存</button>';
    openModal(title, body, foot);
}
async function saveSkill(id, isNew, btn) {
    var name = document.getElementById('sk_name').value.trim();
    var color = document.getElementById('sk_color').value;
    if (!name) { markErr(document.getElementById('sk_name'), '名称不能为空'); return; }
    var action = isNew ? 'add' : 'update';
    var body = { action: action, name: name, color: color };
    if (!isNew) body.id = id;
    var ret = await postJson('/api/admin_skills', body);
    if (ret.code === 0) {
        closeModal();
        await reloadSkills();
    }
}
async function deleteSkill(id, name, btn) {
    if (!confirm('确定删除能力「' + name + '」? 所有成员的该能力会被移除。')) return;
    var ret = await postJson('/api/admin_skills', { action: 'delete', id: id });
    if (ret.code === 0) await reloadSkills();
}
async function loadTeamStats() {
    var ret = await getJson('/api/admin_stats');
    renderTeamStats(ret.data || {});
}
async function loadTeamLogs() {
    var ret = await getJson('/api/admin_logs?limit=50');
    renderTeamLogs(ret.data || []);
}
async function loadTeamLogsAll() {
    var ret = await getJson('/api/admin_logs?limit=500');
    renderTeamLogs(ret.data || []);
}
function renderTeamGroups(users) {
    var counts = {};
    for (var i = 0; i <= 5; i++) counts[i] = 0;
    users.forEach(function(u) { counts[u.level || 0] = (counts[u.level || 0] || 0) + 1; });
    var html = '';
    for (var i = 5; i >= 0; i--) {
        var c = levelColor(i);
        html += '<div class="grp-card">' +
            lvlBadge(i) +
            '<div class="grp-name">' + esc(levelName(i)) + '</div>' +
            '<div class="grp-count">' + counts[i] + ' 人</div>' +
            '<div class="grp-actions">' +
            '<button class="card-head-btn" onclick="openGroupMembers(' + i + ')">成员</button>' +
            '<button class="card-head-btn" onclick="openGroupEdit(' + i + ')">编辑</button>' +
            '</div></div>';
    }
    document.getElementById('teamGroups').innerHTML = html;
}
function renderTeamMembers(users) {
    if (!users.length) {
        document.getElementById('teamMembers').innerHTML = '<div class="empty-tip">还没有成员</div>';
        return;
    }
    var html = users.map(function(u) {
        var skillTxt = renderSkillHtml(u.skill);
        return '<div class="member-bar">' +
            '<img class="mb-ava" src="' + avatarUrl(u) + '" alt="">' +
            '<div class="mb-main">' +
            '<div class="mb-name">' + esc(u.name) + ' ' + lvlBadge(u.level || 0) + '</div>' +
            '<div class="mb-mail">' + esc(u.email) + '</div>' +
            '<div class="mb-skill">' + skillTxt + '</div>' +
            '</div>' +
            '<button class="act-btn" onclick="openMemberDetail(' + u.id + ')">编辑</button>' +
            '</div>';
    }).join('');
    document.getElementById('teamMembers').innerHTML = html;
}
function renderTeamInvites(invites) {
    if (!invites.length) {
        document.getElementById('teamInvites').innerHTML = '<div class="empty-tip">还没有邀请码</div>';
        return;
    }
    var html = invites.map(function(iv) {
        var used = !!iv.used_at;
        var top = '<div class="iv-top"><span class="iv-code">#' + esc(iv.code) + '</span>' +
            (used ? '<span class="chip no">已被使用</span>' : '<span class="chip ok">未使用</span>') + '</div>';
        var creator = iv.creator_name ? '创建者: ' + esc(iv.creator_name) : '创建者: 系统';
        var mid = used
            ? '<div class="iv-user"><img src="' + avatarUrl({avatar: iv.used_avatar}) + '" alt=""><div><div class="iv-un">' + esc(iv.used_name || '--') + '</div><div class="iv-ue">' + esc(iv.used_email || '--') + '</div></div></div>' +
              '<div class="iv-date">' + creator + '<br>创建: ' + esc(iv.created_at) + '<br>使用: ' + esc(iv.used_at) + '</div>'
            : '<div class="iv-date">' + creator + '<br>创建: ' + esc(iv.created_at) + '</div>' +
              '<div style="margin-top:10px"><button class="act-btn" style="width:100%;justify-content:center" onclick="copyText(\'' + esc(iv.code) + '\', this)">复制邀请码</button></div>';
        return '<div class="invite-box">' + top + mid + '</div>';
    }).join('');
    document.getElementById('teamInvites').innerHTML = html;
}
function renderTeamStats(s) {
    var items = [
        ['注册用户', s.users], ['API调用总数', s.api_total], ['今日API', s.api_today],
        ['近7天API', s.api_week], ['访问总数', s.visits_total], ['今日访问', s.visits_today],
        ['近7天访问', s.visits_week], ['通知数', s.notices], ['项目数', s.projects],
        ['待办数', s.todos], ['邀请码', s.invites], ['已用邀请码', s.invites_used], ['在线会话', s.sessions]
    ];
    document.getElementById('teamStats').innerHTML = '<div class="stat-block">' + items.map(function(it) {
        return '<div class="sb"><div class="n">' + esc(it[1]) + '</div><div class="l">' + esc(it[0]) + '</div></div>';
    }).join('') + '</div>';
}
function renderTeamLogs(logs) {
    if (!logs.length) {
        document.getElementById('teamLogs').innerHTML = '<div class="empty-tip">还没有日志</div>';
        return;
    }
    var html = logs.map(function(l) {
        return '<div class="trow"><div class="t-body"><div class="t-line"><span class="t-title">' + esc(l.path || '--') + '</span></div>' +
            '<div class="t-meta">' + esc(l.user_name || '未知') + ' · IP: ' + esc(l.ip || '未知') + ' · ' + esc(l.created_at) + '</div></div></div>';
    }).join('');
    document.getElementById('teamLogs').innerHTML = html;
}
async function openMemberDetail(uid) {
    var SMALL_SPIN = '<div style="display:flex;align-items:center;justify-content:center;padding:28px 12px;color:#999;gap:10px;font-size:13px"><svg xmlns="http://www.w3.org/2000/svg" class="spin" viewBox="0 0 24 24" style="width:18px;height:18px;color:#ef5777"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3a9 9 0 1 0 9 9"/></svg> 正在加载成员信息…</div>';
    openModal('成员详情', SMALL_SPIN);
    try {
        var ret = await getJson('/api/admin_users?id=' + uid);
        if (ret.code !== 0 || !ret.data) {
            closeModal();
            return;
        }
        var d = ret.data;
        var u = d.user;
        var s = d.stats || {};
        var pages = d.pages || [];
        var avatarHtml = '<div class="mem-avatar-row"><img src="' + avatarUrl(u) + '" alt=""><div>' +
            '<div class="ma-name">' + esc(u.name) + ' ' + lvlBadge(u.level || 0) + '</div>' +
            '<div class="ma-mail">' + esc(u.email) + '</div></div></div>';
        var infoHtml = '<div class="md-section"><div class="md-label">基础信息</div>' +
            '<div class="md-row"><div class="md-k">昵称</div><div class="md-v"><input id="mm_name" value="' + esc(u.name || '') + '"></div></div>' +
            '<div class="md-row"><div class="md-k">邮箱</div><div class="md-v">' + esc(u.email) + '</div></div>' +
            '<div class="md-row"><div class="md-k">账号ID</div><div class="md-v">' + esc(u.id) + '</div></div>' +
            '<div class="md-row"><div class="md-k">核心能力</div><div class="md-v"><div class="picker-wrap"><div class="picker" id="mmSkillPicker" onclick="document.getElementById(\'mmSkillInput\').focus()"><input id="mmSkillInput" placeholder="选择核心能力" autocomplete="off" onfocus="skillPickerSearch(this.value,\'mm\')" oninput="skillPickerSearch(this.value,\'mm\')" onkeydown="skillPickerKey(event,\'mm\')"></div><div class="picker-drop hide" id="mmSkillDrop"></div></div></div></div>' +
            '<div class="md-row"><div class="md-k">权限组</div><div class="md-v"><select id="mm_level">' + levelOptions(u.level || 0) + '</select></div></div>' +
            '<div class="md-row"><div class="md-k">面板节点</div><div class="md-v"><input id="mm_host" value="' + esc(u.panel_host || '') + '"></div></div>' +
            '<div class="md-row"><div class="md-k">注册时间</div><div class="md-v">' + esc(u.created_at || '--') + '</div></div></div>';
        var statsHtml = '<div class="md-section"><div class="md-label">API 与访问统计</div><div class="sec-grid">' +
            '<div class="ss"><div class="n">' + esc(s.api_total || 0) + '</div><div class="l">API总数</div></div>' +
            '<div class="ss"><div class="n">' + esc(s.api_today || 0) + '</div><div class="l">今日API</div></div>' +
            '<div class="ss"><div class="n">' + esc(s.api_week || 0) + '</div><div class="l">近7天</div></div>' +
            '<div class="ss"><div class="n">' + esc(s.visits_total || 0) + '</div><div class="l">访问总数</div></div>' +
            '<div class="ss"><div class="n">' + esc(s.visits_today || 0) + '</div><div class="l">今日访问</div></div>' +
            '</div></div>';
        var ses = d.sessions || [];
        var sesHtml = '<div class="md-section"><div class="md-label">登录会话 (' + ses.length + ')</div>';
        if (!ses.length) {
            sesHtml += '<div class="empty-tip">无活跃会话</div>';
        } else {
            sesHtml += ses.map(function(si) {
                return '<div class="dev-row">' + DESKTOP_SVG +
                    '<div class="dv-main"><div class="dv-ip">' + esc(si.ip || '未知IP') + '</div>' +
                    '<div class="dv-ua">' + esc(si.ua || '未知设备') + '</div>' +
                    '<div class="dv-time">创建: ' + esc(si.created_at || '--') + ' · 到期: ' + esc(si.expire_time || '--') + '</div></div>' +
                    '<button class="act-btn" onclick="btnRun(this, function(btn){ return mmKillSession(' + u.id + ',' + si.id + ',btn); })">' + LOGOUT_SVG + ' 踢下线</button></div>';
            }).join('');
        }
        sesHtml += '</div>';
        var inv = d.invites_created || [];
        var invHtml = '<div class="md-section"><div class="md-label">创建的邀请码 (' + inv.length + ')</div>';
        if (!inv.length) {
            invHtml += '<div class="empty-tip">尚未创建邀请码</div>';
        } else {
            invHtml += inv.map(function(iv) {
                var used = !!iv.used_at;
                var tag = used ? '<span class="chip no">已使用</span>' : '<span class="chip ok">未使用</span>';
                var ux = used ? '<div class="iv-user" style="margin-top:6px"><img src="' + avatarUrl({avatar: iv.used_avatar}) + '" style="width:22px;height:22px" alt=""><span>' + esc(iv.used_name || '--') + ' · ' + esc(iv.used_email || '--') + '</span></div>' : '';
                return '<div class="invite-box" style="margin-bottom:8px"><div class="iv-top"><span class="iv-code">#' + esc(iv.code) + '</span>' + tag + '</div>' +
                    '<div class="iv-date">创建: ' + esc(iv.created_at || '--') + (used ? '<br>使用: ' + esc(iv.used_at || '--') : '') + '</div>' + ux + '</div>';
            }).join('');
        }
        if (d.invite_used) {
            var iu = d.invite_used;
            invHtml += '<div class="md-label" style="margin-top:14px">注册用邀请码</div><div class="invite-box"><div class="iv-top"><span class="iv-code">#' + esc(iu.code) + '</span><span class="chip ok">已使用</span></div>' +
                '<div class="iv-date">' + (iu.creator_name ? '创建者: ' + esc(iu.creator_name) : '创建者: 系统') + '<br>创建: ' + esc(iu.created_at || '--') + '<br>使用: ' + esc(iu.used_at || '--') + '</div></div>';
        }
        invHtml += '</div>';
        var pgsHtml = '<div class="md-section"><div class="md-label">页面访问权限</div>';
        var ftrHtml = '';
        pages.forEach(function(p) {
            var pk = p.page_key;
            var label = PAGE_LABEL[pk] || pk;
            var ok = (u.level || 0) >= (p.min_level || 0);
            var chip = ok ? '<span class="chip ok">可访问</span>' : '<span class="chip no">不足权限</span>';
            var kind = PAGE_KIND[pk] || 'page';
            var row;
            if (kind === 'feature') {
                row = '<div class="pg-edit-row"><div class="pen"><span class="pf-tag">功能</span>' + esc(label) + '</div>' +
                    '<select class="pes" disabled>' + levelOptions(p.min_level || 0) + '</select>' + chip + '</div>';
                ftrHtml += row;
            } else {
                row = '<div class="pg-edit-row"><div class="pen">' + esc(label) + '</div>' +
                    '<select class="pes" disabled>' + levelOptions(p.min_level || 0) + '</select>' +
                    '<label class="pecb"><input type="checkbox" disabled ' + (p.show_in_nav ? 'checked' : '') + '> 侧栏</label>' + chip + '</div>';
                pgsHtml += row;
            }
        });
        pgsHtml += '</div>';
        if (ftrHtml) {
            pgsHtml += '<div class="md-section" style="margin-top:14px"><div class="md-label">功能操作权限</div>' + ftrHtml + '</div>';
        }
        var logsHtml = '';
        var lg = d.recent_logs || [];
        if (lg.length) {
            logsHtml = '<div class="md-section"><div class="md-label">最近操作日志</div><div class="mini-logs">' +
                lg.map(function(l) {
                    return '<div class="ml"><span class="mp">' + esc(l.path || '--') + '</span><span class="mi">' + esc(l.ip || '') + '</span><span class="mt">' + esc(l.created_at || '--') + '</span></div>';
                }).join('') + '</div></div>';
        }
        var foot = '<button class="act-btn" onclick="closeModal()">关闭</button>' +
            '<button class="add-todo-btn" onclick="btnRun(this, function(btn){ return mmSave(' + u.id + ',btn); })">保存修改</button>';
        openModal('成员详情 · ' + u.name, avatarHtml + infoHtml + statsHtml + sesHtml + invHtml + pgsHtml + logsHtml, foot);
        setTimeout(function() { initSkillPicker('mm', u.skill || ''); }, 0);
    } catch (e) {
        closeModal();
    }
}
var __skillCtx = {};
function initSkillPicker(ctx, skillRaw) {
    var list = String(skillRaw || '').split(/[,，]/).map(function(x) { return x.trim(); }).filter(Boolean);
    var arr = [];
    var meta = window.__SKILL_META || {};
    list.forEach(function(nm) {
        var hit = null;
        for (var k in meta) { if (meta[k].name === nm) { hit = meta[k]; break; } }
        if (hit) arr.push({ id: hit.id, name: hit.name, color: hit.color });
    });
    __skillCtx[ctx] = { skills: arr };
    renderSkillPickerChips(ctx);
    var drop = document.getElementById(ctx + 'SkillDrop');
    if (drop) drop.classList.add('hide');
}
function renderSkillPickerChips(ctx) {
    var c = __skillCtx[ctx];
    if (!c) return;
    var pk = document.getElementById(ctx + 'SkillPicker');
    if (!pk) return;
    pk.querySelectorAll('.u-chip.skill').forEach(function(el) { el.remove(); });
    var input = document.getElementById(ctx + 'SkillInput');
    c.skills.forEach(function(s, idx) {
        var chip = document.createElement('span');
        chip.className = 'u-chip skill';
        chip.style.color = s.color;
        chip.style.borderColor = hexA(s.color, .45);
        chip.style.background = hexA(s.color, .08);
        chip.innerHTML = '<span>' + esc(s.name) + '</span><span class="rm" data-idx="' + idx + '">' + X_SVG + '</span>';
        chip.querySelector('.rm').onclick = function(e) {
            e.stopPropagation();
            var i = parseInt(this.dataset.idx || '0');
            c.skills.splice(i, 1);
            renderSkillPickerChips(ctx);
        };
        pk.insertBefore(chip, input);
    });
}
var __skillSearchTimer = null;
function skillPickerSearch(kw, ctx) {
    var c = __skillCtx[ctx];
    if (!c) return;
    kw = (kw || '').trim();
    var drop = document.getElementById(ctx + 'SkillDrop');
    if (!drop) return;
    if (__skillSearchTimer) clearTimeout(__skillSearchTimer);
    __skillSearchTimer = setTimeout(function() {
        var meta = window.__SKILL_META || {};
        var all = [];
        for (var k in meta) all.push(meta[k]);
        var filtered = all.filter(function(x) {
            return !c.skills.some(function(y) { return y.name === x.name; });
        });
        if (kw) filtered = filtered.filter(function(x) { return x.name.indexOf(kw) !== -1; });
        _renderSkillDrop(ctx, filtered, kw);
    }, kw ? 120 : 30);
}
function _renderSkillDrop(ctx, arr, kw) {
    var drop = document.getElementById(ctx + 'SkillDrop');
    if (!drop) return;
    if (!arr.length) {
        drop.innerHTML = '<div class="drop-empty">' + (kw ? '没有匹配的能力' : '暂无可选能力') + '</div>';
        drop.classList.remove('hide');
        return;
    }
    var html = arr.map(function(x) {
        return '<div class="drop-row" onclick="addMetaSkill(\'' + ctx + '\',' + x.id + ',\'' + escAttr(x.name) + '\',\'' + escAttr(x.color || '#ef5777') + '\')"><div style="display:flex;align-items:center;gap:8px"><span class="skill-tag sm" style="color:' + x.color + ';border-color:' + hexA(x.color,.45) + ';background:' + hexA(x.color,.08) + '">' + esc(x.name) + '</span><div class="de">' + esc(x.name) + '</div></div></div>';
    }).join('');
    drop.innerHTML = html;
    drop.classList.remove('hide');
}
function skillPickerKey(e, ctx) {
    var c = __skillCtx[ctx];
    if (!c) return;
    if (e.key === 'Backspace' && !e.target.value && c.skills.length) {
        c.skills.pop();
        renderSkillPickerChips(ctx);
    }
    if (e.key === 'Enter') { e.preventDefault(); }
}
function addMetaSkill(ctx, id, name, color) {
    var c = __skillCtx[ctx];
    if (!c) return;
    if (c.skills.some(function(x) { return x.name === name; })) return;
    c.skills.push({ id: id, name: name, color: color || '#ef5777' });
    renderSkillPickerChips(ctx);
    var inp = document.getElementById(ctx + 'SkillInput');
    if (inp) { inp.value = ''; inp.focus(); }
    var drop = document.getElementById(ctx + 'SkillDrop');
    if (drop) drop.classList.add('hide');
}
function getSkillPickerValues(ctx) {
    var c = __skillCtx[ctx];
    return c ? c.skills.map(function(x) { return x.name; }).join(',') : '';
}
async function mmSave(uid, btn) {
    var body = {
        id: uid,
        name: document.getElementById('mm_name').value.trim(),
        skill: getSkillPickerValues('mm'),
        level: parseInt(document.getElementById('mm_level').value) || 0,
        panel_host: document.getElementById('mm_host').value.trim()
    };
    if (!body.name) {
        markErr(document.getElementById('mm_name'), '昵称不能为空');
        return;
    }
    var ret = await postJson('/api/admin_users', body);
    if (ret.code === 0) {
        closeModal();
        await loadTeam();
    }
}
async function mmKillSession(uid, sid, btn) {
    await postJson('/api/admin_users', { id: uid, kill_session: sid });
    var row = btn.closest('.dev-row');
    if (row) row.remove();
}
async function openGroupEdit(lv) {
    var color = levelColor(lv);
    var name = levelName(lv);
    var members = ALL_USERS.filter(function(u) { return (u.level || 0) === lv; });
    var pages = [];
    var defKeys = Object.keys(DEFAULT_PAGE_ACCESS);
    defKeys.forEach(function(k) {
        var cfg = pageCfg(k);
        pages.push({ page_key: k, min_level: cfg.min_level, show_in_nav: cfg.show_in_nav });
    });
    var head = '<div style="margin-bottom:18px">当前权限组: ' + lvlBadge(lv) + ' · 共 ' + members.length + ' 人</div>';
    var basic = '<div class="md-section"><div class="md-label">基础设置</div>' +
        '<div class="md-row"><div class="md-k">组名称</div><div class="md-v"><input id="ge_name" value="' + esc(name) + '"></div></div>' +
        '<div class="md-row"><div class="md-k">标识颜色</div><div class="md-v"><input type="color" class="color-in" id="ge_color" value="' + esc(color) + '"></div></div>' +
        '</div>';
    var pgEdit = '<div class="md-section"><div class="md-label">页面访问权限</div>';
    var ftrEdit = '';
    pages.forEach(function(p) {
        var pk = p.page_key;
        var label = PAGE_LABEL[pk] || pk;
        var kind = PAGE_KIND[pk] || 'page';
        if (kind === 'feature') {
            ftrEdit += '<div class="pg-edit-row" data-page="' + pk + '">' +
                '<div class="pen"><span class="pf-tag">功能</span>' + esc(label) + '</div>' +
                '<select class="pes" data-f="min">' + levelOptions(p.min_level || 0) + '</select>' +
                '<div style="width:92px"></div>' + // 占位对齐侧栏 checkbox 列
                '</div>';
        } else {
            pgEdit += '<div class="pg-edit-row" data-page="' + pk + '">' +
                '<div class="pen">' + esc(label) + '</div>' +
                '<select class="pes" data-f="min">' + levelOptions(p.min_level || 0) + '</select>' +
                '<label class="pecb"><input type="checkbox" data-f="nav" ' + (p.show_in_nav ? 'checked' : '') + '> 侧栏显示</label>' +
                '</div>';
        }
    });
    pgEdit += '</div>';
    if (ftrEdit) {
        pgEdit += '<div class="md-section" style="margin-top:14px"><div class="md-label">功能操作权限</div>' + ftrEdit + '</div>';
    }
    var foot = '<button class="act-btn" onclick="closeModal()">关闭</button>' +
        '<button class="add-todo-btn" onclick="btnRun(this, function(btn){ return geSave(' + lv + ',btn); })">保存配置</button>';
    openModal('编辑权限组 · ' + name, head + basic + pgEdit, foot);
}
async function geSave(lv, btn) {
    var nm = document.getElementById('ge_name').value.trim();
    var col = document.getElementById('ge_color').value;
    if (!nm) { markErr(document.getElementById('ge_name'), '组名不能为空'); return; }
    await postJson('/api/admin_levels', { level: lv, name: nm, color: col });
    levelMeta[lv] = { name: nm, color: col };
    var pages = {};
    document.querySelectorAll('.pg-edit-row[data-page]').forEach(function(r) {
        var pk = r.dataset.page;
        var ml = parseInt(r.querySelector('[data-f="min"]').value) || 0;
        var navBox = r.querySelector('[data-f="nav"]');
        var sn = navBox && navBox.checked ? 1 : 0;
        pages[pk] = { min_level: ml, show_in_nav: sn };
        pageAccess[pk] = { min_level: ml, show_in_nav: sn };
    });
    await postJson('/api/admin_levels', { level: lv, pages: pages });
    applyNavFilter();
    closeModal();
    await loadTeam();
}
var __gmMembers = [];
var __gmLevel = 0;
var __gmTimer = null;
async function openGroupMembers(lv) {
    __gmLevel = lv;
    var members = ALL_USERS.filter(function(u) { return (u.level || 0) === lv; });
    var head = '<div style="margin-bottom:10px">' + lvlBadge(lv) + ' · 共 <span id="gmCount">' + members.length + '</span> 人</div>';
    var addBox = '<div style="margin-bottom:16px;padding:12px 14px;border:1px dashed #2b2b2e;border-radius:10px;background:#0d0d0f">' +
        '<div style="font-size:12px;color:#777;margin-bottom:8px">添加成员到该组 (输入昵称搜索)</div>' +
        '<div class="picker-wrap"><div class="picker" id="gmPicker" onclick="document.getElementById(\'gmInput\').focus()"><input id="gmInput" placeholder="搜索或选择用户" autocomplete="off" onfocus="gmSearch(this.value)" oninput="gmSearch(this.value)" onkeydown="gmKey(event)"></div><div class="picker-drop hide" id="gmDrop"></div></div>' +
        '<div style="margin-top:10px;display:flex;gap:10px;align-items:center">' +
        '<button class="add-todo-btn" style="margin:0" onclick="btnRun(this, gmAddLevel)">把所选成员加入该组</button>' +
        '<button class="act-btn" style="margin:0" onclick="gmClear()">清空选择</button>' +
        '<span id="gmTip" style="color:#777;font-size:12px"></span>' +
        '</div></div>';
    var html = head + addBox + '<div class="group-members" id="gmList">';
    html += renderGroupMemberList(members);
    html += '</div>';
    var foot = '<button class="add-todo-btn" onclick="closeModal()">关闭</button>';
    openModal('组内成员 · ' + levelName(lv), html, foot);
    __gmMembers = [];
    setTimeout(function() { renderGmChips(); document.getElementById('gmDrop').classList.add('hide'); }, 0);
}
function renderGroupMemberList(list) {
    if (!list || !list.length) return '<div class="empty-tip">该组暂无成员</div>';
    return list.map(function(u) {
        return '<div class="member-bar">' +
            '<img class="mb-ava" src="' + avatarUrl(u) + '" alt=""><div class="mb-main">' +
            '<div class="mb-name">' + esc(u.name) + ' ' + lvlBadge(u.level || 0) + '</div>' +
            '<div class="mb-mail">' + esc(u.email) + '</div>' +
            '<div class="mb-skill">' + renderSkillHtml(u.skill) + '</div></div>' +
            '<button class="act-btn" onclick="openMemberDetail(' + u.id + ')">详情</button></div>';
    }).join('');
}
function renderGmChips() {
    var pk = document.getElementById('gmPicker');
    if (!pk) return;
    pk.querySelectorAll('.u-chip').forEach(function(c) { c.remove(); });
    var input = document.getElementById('gmInput');
    __gmMembers.forEach(function(u, idx) {
        var chip = document.createElement('span');
        chip.className = 'u-chip';
        chip.innerHTML = '<img src="' + avatarUrl(u) + '" alt=""><span>' + esc(u.name) + '</span><span class="rm" data-idx="' + idx + '">' + X_SVG + '</span>';
        chip.querySelector('.rm').onclick = function(e) {
            e.stopPropagation();
            var i = parseInt(this.dataset.idx || '0');
            __gmMembers.splice(i, 1);
            renderGmChips();
        };
        pk.insertBefore(chip, input);
    });
}
function gmSearch(kw) {
    kw = (kw || '').trim();
    var drop = document.getElementById('gmDrop');
    if (!drop) return;
    if (__gmTimer) clearTimeout(__gmTimer);
    if (!kw) {
        var list = (ALL_USERS || []).slice(0, 30).filter(function(u) {
            return !__gmMembers.some(function(x) { return x.id === u.id; });
        });
        gmRenderDrop(list);
        return;
    }
    __gmTimer = setTimeout(async function() {
        try {
            var ret = await getJson('/api/user_search?q=' + encodeURIComponent(kw));
            var list = (ret.data || []).filter(function(u) {
                return !__gmMembers.some(function(x) { return x.id === u.id; });
            });
            gmRenderDrop(list, kw);
        } catch (e) {}
    }, 160);
}
function gmRenderDrop(list, kw) {
    var drop = document.getElementById('gmDrop');
    if (!drop) return;
    if (!list || !list.length) {
        drop.innerHTML = '<div class="drop-empty">没有匹配的用户</div>';
    } else {
        drop.innerHTML = '';
        list.forEach(function(u) {
            var row = document.createElement('div');
            row.className = 'drop-row';
            row.innerHTML = '<img src="' + avatarUrl(u) + '" alt=""><div><div class="dn">' + esc(u.name) + (u.level != null ? ' <span style="font-size:11px;color:#777">当前' + esc(levelName(u.level)) + '</span>' : '') + '</div><div class="de">' + esc(u.email) + '</div></div>';
            row.onclick = function() { gmAddChip(u); };
            drop.appendChild(row);
        });
    }
    drop.classList.remove('hide');
}
function gmKey(e) {
    if (e.key === 'Backspace' && !e.target.value && __gmMembers.length) {
        __gmMembers.pop();
        renderGmChips();
    }
}
function gmAddChip(u) {
    if (__gmMembers.some(function(x) { return x.id === u.id; })) return;
    __gmMembers.push({ id: u.id, name: u.name, email: u.email, level: u.level || 0 });
    var inp = document.getElementById('gmInput');
    if (inp) { inp.value = ''; inp.focus(); }
    document.getElementById('gmDrop').classList.add('hide');
    renderGmChips();
}
function gmClear() {
    __gmMembers = [];
    renderGmChips();
    document.getElementById('gmTip').textContent = '';
}
async function gmAddLevel(btn) {
    if (!__gmMembers.length) {
        document.getElementById('gmTip').textContent = '请先选择要加入的成员';
        return;
    }
    var ok = 0, fail = 0;
    for (var i = 0; i < __gmMembers.length; i++) {
        var u = __gmMembers[i];
        var r = await postJson('/api/admin_users', { id: u.id, level: __gmLevel });
        if (r && r.code === 0) ok++; else fail++;
    }
    document.getElementById('gmTip').textContent = '已加入 ' + ok + ' 人' + (fail ? '，失败 ' + fail + ' 人' : '');
    __gmMembers = [];
    renderGmChips();
    await loadTeam();
    var list = (ALL_USERS || []).filter(function(u) { return (u.level || 0) === __gmLevel; });
    var el = document.getElementById('gmList');
    if (el) el.innerHTML = renderGroupMemberList(list);
    var cc = document.getElementById('gmCount');
    if (cc) cc.textContent = list.length;
}
async function saveUserField(id, field, value) {
    var body = { id: id };
    body[field] = value;
    await postJson('/api/admin_users', body);
}
function toggleNoticeForm() {
    document.getElementById('noticeFormBox').classList.toggle('hide');
}
async function submitNotice() {
    var title = document.getElementById('noticeTitle').value.trim();
    if (!title) return;
    var content = document.getElementById('noticeContent').value.trim();
    var ret = await postJson('/api/notice', { title: title, content: content });
    if (ret.code === 0) {
        document.getElementById('noticeTitle').value = '';
        document.getElementById('noticeContent').value = '';
        document.getElementById('noticeFormBox').classList.add('hide');
        await loadNotice();
    }
}
function toggleProjectForm() {
    document.getElementById('projectFormBox').classList.toggle('hide');
}
async function submitProject() {
    var name = document.getElementById('projectName').value.trim();
    if (!name) return;
    var ret = await postJson('/api/project', {
        name: name,
        info: document.getElementById('projectInfo').value.trim(),
        link: document.getElementById('projectLink').value.trim(),
        members: document.getElementById('projectMembers').value.trim()
    });
    if (ret.code === 0) {
        ['projectName','projectInfo','projectLink','projectMembers'].forEach(function(id) { document.getElementById(id).value = ''; });
        document.getElementById('projectFormBox').classList.add('hide');
        await loadProject();
    }
}
(async function boot() {
    var start = pageFromPath();
    showPage(start);
    initMeteors();
    document.addEventListener('click', function(e) {
        ['#assignDrop','#mmSkillDrop','#gmDrop'].forEach(function(sel) {
            var d = document.querySelector(sel);
            if (!d || d.classList.contains('hide')) return;
            if (!e.target.closest('.picker-wrap')) d.classList.add('hide');
        });
    });
    try {
        await loadSkillsMeta();
        var jobs = [loadMe(), loadPagesConfig(), loadTodo(), loadNotice(), loadProject(), document.fonts.ready];
        if (start === 'overview') jobs.push(loadOverview());
        if (start === 'apis') jobs.push(loadApis());
        if (start === 'logs') jobs.push(loadLogs());
        if (start === 'mcsm') jobs.push(loadMcsm());
        if (start === 'team') jobs.push(loadTeam());
        await Promise.all(jobs);
        applyNavFilter();
        if (!canAccess(start)) {
            history.replaceState(null, '', '/');
            showPage('home');
        }
    } finally {
        document.getElementById('loadMask').style.display = 'none';
    }
    var m = location.pathname.match(/^\/todos\/(\d+)$/);
    if (m) { await loadTodoDetail(m[1]); showPage('tododetail'); }
})();
function initMeteors() {
    var layer = document.getElementById('meteorsLayer');
    if (!layer) return;
    var total = 10;
    function spawnOnce(i) {
        var el = document.createElement('div');
        el.className = 'meteor';
        var top = -10 + Math.random() * 70;
        var left = 20 + Math.random() * 100;
        var dur = 5500 + Math.random() * 6500;
        var delay = Math.random() * 7000;
        el.style.top = top + 'vh';
        el.style.left = left + 'vw';
        el.style.animation = 'meteorFly ' + dur + 'ms linear ' + delay + 'ms forwards';
        layer.appendChild(el);
        setTimeout(function() {
            if (el.parentNode) el.parentNode.removeChild(el);
            spawnOnce(i);
        }, dur + delay + 200);
    }
    for (var i = 0; i < total; i++) spawnOnce(i);
}
function pathToPage(p) {
    if (p === '/todos/add') return 'addtodo';
    if (p === '/todos' || p.indexOf('/todos/') === 0) return 'todo';
    for (var k in PAGE_PATH) { if (PAGE_PATH[k] === p) return k; }
    return null;
}
var TOAST_DEFAULT_ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 5a2 2 0 1 1 4 0a7 7 0 0 1 4 6v3a4 4 0 0 0 2 3H4a4 4 0 0 0 2-3v-3a7 7 0 0 1 4-6M9 17v1a3 3 0 0 0 6 0v-1"/></svg>';
function flipToast(items, firstPos) {
    items.forEach(function(c, i) {
        var last = c.getBoundingClientRect().top;
        var delta = last - firstPos[i];
        if (delta !== 0) {
            c.style.transform = 'translateY(' + (-delta) + 'px)';
            c.style.transition = 'none';
            requestAnimationFrame(function() {
                c.style.transition = 'transform .35s cubic-bezier(.21,1.02,.73,1)';
                c.style.transform = '';
            });
        }
    });
}
function notify(icon, title, message, duration, link, inApp) {
    duration = Math.max(0, Number(duration) || 0);
    var msg = String(message || '');
    if (msg.length > 100) msg = msg.slice(0, 100) + '…';
    var box = document.getElementById('toastBox');
    var existing = Array.prototype.filter.call(box.children, function(c) { return !c.dataset.closing; });
    var firstPos = existing.map(function(c) { return c.getBoundingClientRect().top; });
    var el = document.createElement('div');
    el.className = 'toast' + (link ? ' clickable' : '');
    el.innerHTML =
        '<div class="toast-icon">' + (icon || TOAST_DEFAULT_ICON) + '</div>' +
        '<div class="toast-body">' +
            '<div class="toast-title">' + esc(title || '') + '</div>' +
            '<div class="toast-msg">' + esc(msg) + '</div>' +
        '</div>' +
        '<button class="toast-close" title="关闭">' + X_SVG + '</button>' +
        (duration > 0 ? '<div class="toast-bar"><div class="toast-bar-fill"></div></div>' : '');
    if (link) {
        el.addEventListener('click', function(e) {
            if (e.target.closest('.toast-close')) return;
            if (inApp && link.charAt(0) === '/') {
                var pg = pathToPage(link);
                if (pg) { switchPage(pg); }
                else { history.pushState(null, '', link); showPage(pageFromPath()); }
            } else {
                window.open(link, '_blank');
            }
            dismissToast(el);
        });
    }
    el.querySelector('.toast-close').addEventListener('click', function(e) {
        e.stopPropagation();
        dismissToast(el);
    });
    box.prepend(el);
    flipToast(existing, firstPos);
    if (duration > 0) {
        var bar = el.querySelector('.toast-bar-fill');
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                bar.style.transition = 'width ' + duration + 'ms linear';
                bar.style.width = '0%';
            });
        });
        el._toastTimer = setTimeout(function() { dismissToast(el); }, duration);
    }
    return el;
}
function dismissToast(el) {
    if (!el || el.dataset.closing) return;
    el.dataset.closing = '1';
    if (el._toastTimer) clearTimeout(el._toastTimer);
    var box = el.parentNode;
    if (!box) return;
    var siblings = Array.prototype.filter.call(box.children, function(c) {
        return c !== el && !c.dataset.closing;
    });
    var firstPos = siblings.map(function(c) { return c.getBoundingClientRect().top; });
    el.style.animation = 'none';
    el.style.transition = 'transform .28s ease, opacity .28s ease';
    el.style.transform = 'translateX(120%)';
    el.style.opacity = '0';
    setTimeout(function() {
        if (el.parentNode) el.parentNode.removeChild(el);
        flipToast(siblings, firstPos);
    }, 280);
}
