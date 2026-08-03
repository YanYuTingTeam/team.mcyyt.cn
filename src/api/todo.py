from utils.auth import check_login
from utils.db import get_db
import threading

_col_ensured = False
def _ensure_col(db):
    global _col_ensured
    if _col_ensured:
        return
    try:
        with db.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM yyt_todo LIKE 'is_global'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE yyt_todo ADD COLUMN is_global TINYINT DEFAULT 0 AFTER content")
                cur.execute("ALTER TABLE yyt_todo ADD KEY idx_global (is_global)")
            cur.execute("SHOW COLUMNS FROM yyt_todo LIKE 'updated_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE yyt_todo ADD COLUMN updated_at DATETIME DEFAULT NULL AFTER created_at")
            cur.execute("SHOW COLUMNS FROM yyt_todo LIKE 'all_done_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE yyt_todo ADD COLUMN all_done_at DATETIME DEFAULT NULL")
                cur.execute("ALTER TABLE yyt_todo ADD COLUMN done_notify_sent TINYINT DEFAULT 0")
            cur.execute("SHOW COLUMNS FROM yyt_todo LIKE 'deleted_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE yyt_todo ADD COLUMN deleted_at DATETIME DEFAULT NULL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS yyt_todo_tag_rel (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    todo_id INT NOT NULL,
                    tag_id INT NOT NULL,
                    UNIQUE KEY uq_todo_tag (todo_id, tag_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            try:
                cur.execute("INSERT IGNORE INTO yyt_page_access (page_key, min_level, show_in_nav) VALUES ('delete_todo', 4, 0)")
            except Exception:
                pass
            db.commit()
    except Exception:
        pass
    _col_ensured = True

def _clean_tag_ids(raw):
    clean = []
    for t in (raw or []):
        try:
            clean.append(int(t))
        except (ValueError, TypeError):
            pass
    return clean

def _clean_user_ids(raw):
    clean = []
    for a in (raw or []):
        try:
            clean.append(int(a))
        except (ValueError, TypeError):
            pass
    return list(dict.fromkeys(clean))

def _refresh_all_done_state(cur, todo_id):
    cur.execute("SELECT is_global FROM yyt_todo WHERE id = %s", (todo_id,))
    t = cur.fetchone()
    if not t:
        return
    if t['is_global']:
        return
    cur.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN is_done = 1 THEN 1 ELSE 0 END) AS done_cnt "
        "FROM yyt_todo_assign WHERE todo_id = %s",
        (todo_id,)
    )
    s = cur.fetchone()
    if s and s['total'] > 0 and s['total'] == s['done_cnt']:
        cur.execute(
            "UPDATE yyt_todo SET all_done_at = NOW(), done_notify_sent = 0 WHERE id = %s AND all_done_at IS NULL",
            (todo_id,)
        )
        threading.Timer(300, _delayed_done_notify, args=(todo_id,)).start()
    else:
        cur.execute(
            "UPDATE yyt_todo SET all_done_at = NULL WHERE id = %s",
            (todo_id,)
        )

def _delayed_done_notify(todo_id):
    try:
        from utils.todo_notify import send_done_notify
        send_done_notify(todo_id)
    except Exception:
        pass

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        _ensure_col(db)
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            with db.cursor() as cur:
                if 'edit_todo_id' in data:
                    todo_id = int(data['edit_todo_id'])
                    cur.execute("SELECT creator_id, is_global FROM yyt_todo WHERE id = %s", (todo_id,))
                    t = cur.fetchone()
                    if not t:
                        return {"code": 404, "message": "待办不存在"}
                    if t['creator_id'] != user['id']:
                        return {"code": 403, "message": "只有创建者可以编辑"}
                    title = (data.get('title') or '').strip()
                    if not title:
                        return {"code": 400, "message": "事项标题不能为空"}
                    link = (data.get('link') or '').strip()
                    content = (data.get('content') or '').strip()
                    is_global = 1 if data.get('is_global') else 0
                    tag_ids = _clean_tag_ids(data.get('tag_ids'))
                    cur.execute(
                        "UPDATE yyt_todo SET title = %s, link = %s, content = %s, is_global = %s, updated_at = NOW() WHERE id = %s",
                        (title, link or None, content or None, is_global, todo_id)
                    )
                    cur.execute("DELETE FROM yyt_todo_tag_rel WHERE todo_id = %s", (todo_id,))
                    for tid in tag_ids:
                        cur.execute(
                            "INSERT IGNORE INTO yyt_todo_tag_rel (todo_id, tag_id) VALUES (%s, %s)",
                            (todo_id, tid)
                        )
                    if not is_global:
                        assignees = None
                        if 'assignees' in data:
                            assignees = _clean_user_ids(data.get('assignees'))
                            if not assignees:
                                assignees = [user['id']]
                        elif t['is_global']:
                            assignees = [user['id']]
                        if assignees is not None:
                            cur.execute("SELECT user_id FROM yyt_todo_assign WHERE todo_id = %s", (todo_id,))
                            old_assigns = {r['user_id'] for r in cur.fetchall()}
                            new_set = set(assignees)
                            for rm_uid in (old_assigns - new_set):
                                cur.execute("DELETE FROM yyt_todo_assign WHERE todo_id = %s AND user_id = %s", (todo_id, rm_uid))
                            for add_uid in (new_set - old_assigns):
                                cur.execute(
                                    "INSERT INTO yyt_todo_assign (todo_id, user_id) VALUES (%s, %s)",
                                    (todo_id, add_uid)
                                )
                        if not t['is_global'] or assignees is not None:
                            _refresh_all_done_state(cur, todo_id)
                    else:
                        cur.execute("DELETE FROM yyt_todo_assign WHERE todo_id = %s", (todo_id,))
                        cur.execute("UPDATE yyt_todo SET all_done_at = NULL WHERE id = %s", (todo_id,))
                    db.commit()
                    return {"code": 0, "message": "ok"}
                if 'id' in data:
                    todo_id = int(data['id'])
                    is_done = 1 if data.get('done') else 0
                    cur.execute("SELECT is_global, deleted_at FROM yyt_todo WHERE id = %s", (todo_id,))
                    tr = cur.fetchone()
                    if not tr:
                        return {"code": 404, "message": "待办不存在"}
                    cur.execute(
                        "SELECT id FROM yyt_todo_assign WHERE todo_id = %s AND user_id = %s",
                        (todo_id, user['id'])
                    )
                    row = cur.fetchone()
                    if not tr['is_global'] and not row:
                        return {"code": 403, "message": "你不在该待办的负责人中"}
                    if row:
                        if is_done:
                            cur.execute(
                                "UPDATE yyt_todo_assign SET is_done = 1, done_at = NOW() WHERE id = %s",
                                (row['id'],)
                            )
                        else:
                            cur.execute(
                                "UPDATE yyt_todo_assign SET is_done = 0, done_at = NULL WHERE id = %s",
                                (row['id'],)
                            )
                    else:
                        if is_done:
                            cur.execute(
                                "INSERT INTO yyt_todo_assign (todo_id, user_id, is_done, done_at) VALUES (%s, %s, 1, NOW())",
                                (todo_id, user['id'])
                            )
                        else:
                            cur.execute(
                                "INSERT INTO yyt_todo_assign (todo_id, user_id, is_done, done_at) VALUES (%s, %s, 0, NULL)",
                                (todo_id, user['id'])
                            )
                    if not tr['is_global']:
                        _refresh_all_done_state(cur, todo_id)
                    db.commit()
                    return {"code": 0, "message": "ok"}
                if data.get('action') == 'delete':
                    todo_id = int(data.get('todo_id') or data.get('id') or 0)
                    if not todo_id:
                        return {"code": 400, "message": "缺少待办ID"}
                    cur.execute(
                        "SELECT page_key FROM yyt_page_access WHERE page_key = 'delete_todo'"
                    )
                    pa = cur.fetchone()
                    min_lv = pa['min_level'] if pa else 4
                    if (user.get('level') or 0) < min_lv:
                        return {"code": 403, "message": "无权删除待办"}
                    cur.execute(
                        "SELECT t.id, t.title, t.creator_id, t.deleted_at, u.name AS creator_name "
                        "FROM yyt_todo t JOIN yyt_user u ON t.creator_id = u.id WHERE t.id = %s",
                        (todo_id,)
                    )
                    td = cur.fetchone()
                    if not td:
                        return {"code": 404, "message": "待办不存在"}
                    if td['deleted_at']:
                        return {"code": 400, "message": "待办已被删除"}
                    cur.execute("UPDATE yyt_todo SET deleted_at = NOW() WHERE id = %s", (todo_id,))
                    db.commit()
                    if td['creator_id'] != user['id']:
                        try:
                            from utils.todo_notify import add_user_notice, get_base_url
                            deleter_avatar = ''
                            try:
                                cur.execute("SELECT avatar FROM yyt_user WHERE id = %s", (user['id'],))
                                du = cur.fetchone()
                                deleter_avatar = du['avatar'] if du else ''
                            except Exception:
                                pass
                            deleter_ava_html = ''
                            if deleter_avatar:
                                deleter_ava_html = f'<img src="{deleter_avatar}" style="width:20px;height:20px;border-radius:50%;vertical-align:middle">'
                            content = f'{td["creator_name"]} 你好！你创建的待办 #{todo_id} | {td["title"]} 已被 {deleter_ava_html} {user.get("name","")} 删除.'
                            add_user_notice(td['creator_id'], f'待办 #{todo_id} 已被删除', content)
                        except Exception:
                            pass
                    return {"code": 0, "message": "ok"}
                title = (data.get('title') or '').strip()
                if not title:
                    return {"code": 400, "message": "事项标题不能为空"}
                link = (data.get('link') or '').strip()
                content = (data.get('content') or '').strip()
                is_global = 1 if data.get('is_global') else 0
                tag_ids = _clean_tag_ids(data.get('tag_ids'))
                cur.execute(
                    "INSERT INTO yyt_todo (creator_id, title, link, content, is_global) VALUES (%s, %s, %s, %s, %s)",
                    (user['id'], title, link or None, content or None, is_global)
                )
                new_id = cur.lastrowid
                if not link:
                    cur.execute(
                        "UPDATE yyt_todo SET link = %s WHERE id = %s",
                        ('/todos/' + str(new_id), new_id)
                    )
                for tid in tag_ids:
                    cur.execute(
                        "INSERT IGNORE INTO yyt_todo_tag_rel (todo_id, tag_id) VALUES (%s, %s)",
                        (new_id, tid)
                    )
                assignee_ids = []
                if not is_global:
                    assignees = _clean_user_ids(data.get('assignees'))
                    if not assignees:
                        assignees = [user['id']]
                    for uid in assignees:
                        cur.execute(
                            "INSERT INTO yyt_todo_assign (todo_id, user_id) VALUES (%s, %s)",
                            (new_id, uid)
                        )
                    assignee_ids = assignees
            db.commit()
            ret = {"code": 0, "message": "ok"}
            try:
                if not is_global and assignee_ids:
                    from utils.todo_notify import notify_new_todo
                    notify_new_todo(new_id, user['id'], assignee_ids)
            except Exception:
                pass
            return ret
        with db.cursor() as cur:
            try:
                from utils.todo_notify import try_send_done_emails
                try_send_done_emails(cur)
                db.commit()
            except Exception:
                pass
            tag_filter = request.args.get('tag') or ''
            scope = (request.args.get('scope') or '').strip()
            sql = (
                "SELECT t.id, t.title, t.link, t.content, t.created_at, t.updated_at, t.is_global, t.creator_id, "
                "COALESCE(a.is_done, 0) AS is_done, a.done_at AS my_done_at, "
                "(a.user_id IS NOT NULL) AS is_assigned, u.name AS creator_name, u.avatar AS creator_avatar "
                "FROM yyt_todo t "
                "JOIN yyt_user u ON t.creator_id = u.id "
                "LEFT JOIN yyt_todo_assign a ON a.todo_id = t.id AND a.user_id = %s "
                "WHERE t.deleted_at IS NULL AND 1 = 1"
            )
            params = [user['id']]
            if scope == 'all':
                pass
            elif scope == 'created':
                sql += " AND t.creator_id = %s"
                params.append(user['id'])
            elif scope == 'assigned':
                sql += " AND EXISTS (SELECT 1 FROM yyt_todo_assign a2 WHERE a2.todo_id = t.id AND a2.user_id = %s)"
                params.append(user['id'])
            else:
                sql += " AND (t.is_global = 1 OR a.user_id = %s)"
                params.append(user['id'])
            if tag_filter:
                sql += " AND EXISTS (SELECT 1 FROM yyt_todo_tag_rel r WHERE r.todo_id = t.id AND r.tag_id = %s)"
                params.append(int(tag_filter))
            sql += " ORDER BY t.id DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()
            if rows:
                ids = [r['id'] for r in rows]
                placeholders = ','.join(['%s'] * len(ids))
                cur.execute(
                    "SELECT ta.todo_id, u.id, u.name, u.avatar "
                    "FROM yyt_todo_assign ta JOIN yyt_user u ON ta.user_id = u.id "
                    "WHERE ta.todo_id IN (" + placeholders + ") AND ta.is_done = 1 ORDER BY ta.done_at ASC",
                    ids
                )
                done_map = {}
                for r in cur.fetchall():
                    tid = r['todo_id']
                    if tid not in done_map:
                        done_map[tid] = []
                    done_map[tid].append({'id': r['id'], 'name': r['name'], 'avatar': r['avatar']})
                cur.execute(
                    "SELECT r.todo_id, r.tag_id, t.name, t.color "
                    "FROM yyt_todo_tag_rel r JOIN yyt_todo_tag t ON r.tag_id = t.id "
                    "WHERE r.todo_id IN (" + placeholders + ")",
                    ids
                )
                tag_map = {}
                for r in cur.fetchall():
                    tid = r['todo_id']
                    if tid not in tag_map:
                        tag_map[tid] = []
                    tag_map[tid].append({'id': r['tag_id'], 'name': r['name'], 'color': r['color']})
                for r in rows:
                    r['is_creator'] = (r.get('creator_id') == user['id'])
                    r['done_users'] = done_map.get(r['id'], [])
                    r['tags'] = tag_map.get(r['id'], [])
        return {"code": 0, "data": rows}
    finally:
        db.close()
