from utils.db import get_db
from utils.mailer import send_template_email

_notify_inited = False

NOTIFY_KEYS = ('todo_done', 'todo_new', 'online', 'invite_used')
DEFAULT_NOTIFY = {k: 1 for k in NOTIFY_KEYS}

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
    _notify_inited = True

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
    db = get_db()
    try:
        with db.cursor() as cur:
            _init_table(cur)
            t = _load_todo_basic(cur, todo_id)
            if not t:
                return
            cur.execute(
                "SELECT id, name, email FROM yyt_user WHERE id IN (" + ','.join(['%s']*len(assignee_ids)) + ")",
                list(assignee_ids)
            )
            users = cur.fetchall()
            base_url = ''
            try:
                from config import BASE_URL
                base_url = BASE_URL or ''
            except Exception:
                pass
            link = t.get('link') or ('/todos/' + str(t['id']))
            if not link.startswith('http'):
                link = base_url.rstrip('/') + link
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
                }
                subject = f'[@team] 新待办: {t["title"]}'
                send_template_email(u['email'], subject, 'todo_new_assignee.html', vars)
    finally:
        db.close()

def try_send_done_emails(cur):
    _init_table(cur)
    cur.execute(
        "SELECT t.id, t.done_notify_sent, t.all_done_at, t.creator_id, u.email AS creator_email "
        "FROM yyt_todo t JOIN yyt_user u ON t.creator_id = u.id "
        "WHERE t.all_done_at IS NOT NULL AND t.done_notify_sent = 0 "
        "AND t.all_done_at < DATE_SUB(NOW(), INTERVAL 5 MINUTE) "
        "LIMIT 20"
    )
    rows = cur.fetchall()
    if not rows:
        return
    for r in rows:
        tid = r['id']
        try:
            if not should_notify(cur, r['creator_id'], 'todo_done'):
                cur.execute("UPDATE yyt_todo SET done_notify_sent = 1 WHERE id = %s", (tid,))
                continue
            t = _load_todo_basic(cur, tid)
            if not t:
                continue
            cur.execute(
                "SELECT a.user_id, a.is_done, a.done_at, u.name, u.avatar, u.email "
                "FROM yyt_todo_assign a JOIN yyt_user u ON a.user_id = u.id "
                "WHERE a.todo_id = %s",
                (tid,)
            )
            assigns = cur.fetchall()
            done_list = [x for x in assigns if x['is_done']]
            base_url = ''
            try:
                from config import BASE_URL
                base_url = BASE_URL or ''
            except Exception:
                pass
            link = t.get('link') or ('/todos/' + str(t['id']))
            if not link.startswith('http'):
                link = base_url.rstrip('/') + link
            vars = {
                'TODO_URL': link,
                'TODO_TITLE': t['title'] or '',
                'TODO_TAGS': _tag_chips_html(t.get('tags')),
                'ALL_DONE_AT': str(r['all_done_at'])[:19],
                'DONE_COUNT': len(done_list),
                'ASSIGN_COUNT': len(assigns),
                'DONE_AVATARS': ''.join([_avatar_img({'name': x['name'], 'avatar': x['avatar']}) for x in done_list]),
            }
            subject = f'[@team] 待办已完成: {t["title"]}'
            send_template_email(r['creator_email'], subject, 'todo_all_done.html', vars)
            cur.execute("UPDATE yyt_todo SET done_notify_sent = 1 WHERE id = %s", (tid,))
        except Exception:
            pass
