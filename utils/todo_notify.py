from utils.db import get_db
from utils.mailer import send_template_email
import threading, time

_notify_inited = False
_poller_started = False

NOTIFY_KEYS = ('todo_done', 'todo_new', 'online', 'invite_used')
DEFAULT_NOTIFY = {k: 1 for k in NOTIFY_KEYS}

def get_base_url():
    try:
        from config import BASE_URL
        b = BASE_URL or ''
        if b:
            return b.rstrip('/')
    except Exception:
        pass
    return 'https://team.mcyyt.cn'

def _ensure_notice_cols(cur):
    try:
        cur.execute("SHOW COLUMNS FROM yyt_notice LIKE 'user_id'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE yyt_notice ADD COLUMN user_id INT DEFAULT NULL, ADD KEY idx_user (user_id)")
    except Exception:
        pass
    try:
        cur.execute("SHOW COLUMNS FROM yyt_notice LIKE 'content'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE yyt_notice ADD COLUMN content TEXT")
    except Exception:
        pass

def _ensure_invite_cols(cur):
    try:
        cur.execute("SHOW COLUMNS FROM yyt_invite LIKE 'disabled'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE yyt_invite ADD COLUMN disabled TINYINT DEFAULT 0")
    except Exception:
        pass

def _init_table(cur):
    global _notify_inited
    if _notify_inited:
        return
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS yyt_notify_setting (
                user_id INT PRIMARY KEY,
                todo_done TINYINT DEFAULT 1,
                todo_new TINYINT DEFAULT 1,
                online TINYINT DEFAULT 1,
                invite_used TINYINT DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    except Exception:
        pass
    try:
        cur.execute("SHOW COLUMNS FROM yyt_user LIKE 'track_todo_id'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE yyt_user ADD COLUMN track_todo_id INT DEFAULT NULL")
    except Exception:
        pass
    _ensure_notice_cols(cur)
    _ensure_invite_cols(cur)
    _notify_inited = True

def _done_notify_poller():
    while True:
        time.sleep(60)
        try:
            db = get_db()
            try:
                with db.cursor() as cur:
                    try_send_done_emails(cur)
                db.commit()
            finally:
                db.close()
        except Exception:
            pass

def ensure_poller():
    global _poller_started
    if _poller_started:
        return
    _poller_started = True
    t = threading.Thread(target=_done_notify_poller, daemon=True)
    t.start()

def add_user_notice(user_id, title, content=None):
    if not user_id:
        return False
    ensure_poller()
    ok = False
    db = get_db()
    try:
        with db.cursor() as cur:
            _init_table(cur)
            cur.execute(
                "INSERT INTO yyt_notice (user_id, title, content) VALUES (%s, %s, %s)",
                (int(user_id), (title or '').strip()[:255], (content or '').strip() or None)
            )
            db.commit()
            nid = cur.lastrowid
            ok = True
        try:
            cur2 = None
            with db.cursor() as cur2:
                cur2.execute("SELECT email, name FROM yyt_user WHERE id = %s AND email IS NOT NULL AND status != 3", (int(user_id),))
                u = cur2.fetchone()
            if u and u.get('email'):
                vars = {
                    'NOTICE_TITLE': (title or '').strip()[:255],
                    'NOTICE_CONTENT': (content or '')[:2000],
                    'NOTICE_CREATED_AT': '-',
                    'BASE_URL': get_base_url(),
                    'USER_NAME': u.get('name') or '',
                }
                send_template_email(u['email'], '[@team] 通知动态: ' + vars['NOTICE_TITLE'], 'user_notice.html', vars)
        except Exception:
            pass
    finally:
        db.close()
    return ok

def get_user_notify(cur, user_id):
    _init_table(cur)
    cur.execute("SELECT * FROM yyt_notify_setting WHERE user_id = %s", (user_id,))
    r = cur.fetchone()
    if not r:
        cur.execute(
            "INSERT IGNORE INTO yyt_notify_setting (user_id) VALUES (%s)",
            (user_id,)
        )
        return dict(DEFAULT_NOTIFY)
    return {k: (1 if r.get(k) else 0) for k in NOTIFY_KEYS}

def should_notify(cur, user_id, key):
    if key not in NOTIFY_KEYS:
        return True
    s = get_user_notify(cur, user_id)
    return bool(s.get(key, 1))

def _tag_chips_html(tags):
    if not tags:
        return ''
    parts = []
    for t in tags:
        c = t.get('color') or '#ef5777'
        r, g, b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
        bd = f'rgba({r},{g},{b},.45)'
        bg = f'rgba({r},{g},{b},.08)'
        parts.append(
            f'<span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;'
            f'border:1px solid {bd};background:{bg};color:{c};margin-right:6px;margin-bottom:4px">{t.get("name","")}</span>'
        )
    return ''.join(parts)

def _avatar_img(u):
    name = (u.get('name') or '?')[:1].upper()
    palette = ['#ef5777','#4dabf7','#4caf7d','#cc5de8','#f59f00','#ff6b6b','#748ffc','#098b78','#f06595','#7048e8']
    h = 0
    for ch in (u.get('name') or ''):
        h = ord(ch) + ((h<<5)-h)
    color = palette[abs(h)%len(palette)]
    avatar = u.get('avatar')
    if avatar:
        return f'<img src="{avatar}" style="width:32px;height:32px;border-radius:50%;background:#1c1c1f" title="{u.get("name","")}">'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" rx="16" fill="{color}"/><text x="16" y="17" text-anchor="middle" dominant-baseline="central" font-size="14" fill="#fff" font-family="sans-serif" font-weight="bold">{name}</text></svg>'
    import base64
    b64 = base64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:32px;height:32px;border-radius:50%;background:#1c1c1f" title="{u.get("name","")}">'

def _load_todo_basic(cur, todo_id):
    cur.execute(
        "SELECT t.id, t.title, t.link, t.content, t.created_at, "
        "u.id AS creator_id, u.name AS creator_name, u.email AS creator_email "
        "FROM yyt_todo t JOIN yyt_user u ON t.creator_id = u.id WHERE t.id = %s",
        (todo_id,)
    )
    t = cur.fetchone()
    if not t:
        return None
    cur.execute(
        "SELECT r.tag_id AS id, tg.name, tg.color "
        "FROM yyt_todo_tag_rel r JOIN yyt_todo_tag tg ON r.tag_id = tg.id WHERE r.todo_id = %s",
        (todo_id,)
    )
    tags = cur.fetchall()
    t['tags'] = tags
    return t

def notify_new_todo(todo_id, creator_id, assignee_ids):
    ensure_poller()
    db = get_db()
    try:
        with db.cursor() as cur:
            _init_table(cur)
            t = _load_todo_basic(cur, todo_id)
            if not t:
                return
            cur.execute(
                "SELECT id, name, email FROM yyt_user WHERE id IN (" + ','.join(['%s']*len(assignee_ids)) + ") AND status != 3",
                list(assignee_ids)
            )
            users = cur.fetchall()
            base_url = get_base_url()
            link = t.get('link') or ('/todos/' + str(t['id']))
            if not link.startswith('http'):
                link = base_url + link
            for u in users:
                if u['id'] == creator_id:
                    continue
                if not should_notify(cur, u['id'], 'todo_new'):
                    continue
                vars = {
                    'CREATOR_NAME': t['creator_name'],
                    'CREATED_AT': str(t['created_at'])[:19],
                    'TODO_URL': link,
                    'TODO_TITLE': t['title'] or '',
                    'TODO_CONTENT': (t['content'] or '')[:400],
                    'TODO_TAGS': _tag_chips_html(t.get('tags')),
                    'BASE_URL': base_url,
                }
                subject = f'[@team] 新待办: {t["title"]}'
                send_template_email(u['email'], subject, 'todo_new_assignee.html', vars)
    finally:
        db.close()

def try_send_done_emails(cur):
    _init_table(cur)
    cur.execute(
        "SELECT t.id FROM yyt_todo t WHERE t.all_done_at IS NOT NULL AND t.done_notify_sent = 0 "
        "AND t.all_done_at < DATE_SUB(NOW(), INTERVAL 5 MINUTE) "
        "LIMIT 20"
    )
    rows = cur.fetchall()
    for r in rows:
        send_done_notify(r['id'], cur)

def send_done_notify(todo_id, cur=None):
    own_cur = cur is None
    db = None
    if own_cur:
        db = get_db()
        cur = db.cursor()
    try:
        _init_table(cur)
        cur.execute(
            "SELECT t.id, t.done_notify_sent, t.all_done_at, t.creator_id, u.email AS creator_email "
            "FROM yyt_todo t JOIN yyt_user u ON t.creator_id = u.id "
            "WHERE t.id = %s AND t.deleted_at IS NULL",
            (todo_id,)
        )
        r = cur.fetchone()
        if not r or r['done_notify_sent'] or not r['all_done_at']:
            return
        if not should_notify(cur, r['creator_id'], 'todo_done'):
            cur.execute("UPDATE yyt_todo SET done_notify_sent = 1 WHERE id = %s", (todo_id,))
            return
        t = _load_todo_basic(cur, todo_id)
        if not t:
            return
        cur.execute(
            "SELECT a.user_id, a.is_done, a.done_at, u.name, u.avatar, u.email "
            "FROM yyt_todo_assign a JOIN yyt_user u ON a.user_id = u.id "
            "WHERE a.todo_id = %s ORDER BY a.done_at ASC",
            (todo_id,)
        )
        assigns = cur.fetchall()
        done_list = [x for x in assigns if x['is_done']]
        all_done = len(assigns) > 0 and len(done_list) == len(assigns)
        if not all_done:
            return
        base_url = get_base_url()
        link = t.get('link') or ('/todos/' + str(t['id']))
        if not link.startswith('http'):
            link = base_url + link
        vars = {
            'TODO_URL': link,
            'TODO_TITLE': t['title'] or '',
            'TODO_TAGS': _tag_chips_html(t.get('tags')),
            'ALL_DONE_AT': str(r['all_done_at'])[:19],
            'DONE_COUNT': len(done_list),
            'ASSIGN_COUNT': len(assigns),
            'DONE_AVATARS': ''.join([_avatar_img({'name': x['name'], 'avatar': x['avatar']}) for x in done_list]),
            'BASE_URL': base_url,
        }
        subject = f'[@team] 待办已完成: {t["title"]}'
        send_template_email(r['creator_email'], subject, 'todo_all_done.html', vars)
        cur.execute("UPDATE yyt_todo SET done_notify_sent = 1 WHERE id = %s", (todo_id,))
    except Exception:
        pass
    finally:
        if own_cur:
            try:
                db.commit()
            except Exception:
                pass
            try:
                cur.close()
            except Exception:
                pass
            try:
                db.close()
            except Exception:
                pass
