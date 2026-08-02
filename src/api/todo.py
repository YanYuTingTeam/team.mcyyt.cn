from utils.auth import check_login
from utils.db import get_db

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS yyt_todo_tag_rel (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    todo_id INT NOT NULL,
                    tag_id INT NOT NULL,
                    UNIQUE KEY uq_todo_tag (todo_id, tag_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            db.commit()
    except Exception:
        pass
    _col_ensured = True

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
                if 'id' in data:
                    todo_id = int(data['id'])
                    is_done = 1 if data.get('done') else 0
                    # 对于全局待办, 用户可能还没有 assign 记录, 需要先创建
                    cur.execute(
                        "SELECT id FROM yyt_todo_assign WHERE todo_id = %s AND user_id = %s",
                        (todo_id, user['id'])
                    )
                    row = cur.fetchone()
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
                    db.commit()
                    return {"code": 0, "message": "ok"}
                title = (data.get('title') or '').strip()
                if not title:
                    return {"code": 400, "message": "事项标题不能为空"}
                link = (data.get('link') or '').strip()
                content = (data.get('content') or '').strip()
                is_global = 1 if data.get('is_global') else 0
                tag_ids = data.get('tag_ids') or []
                clean_tag_ids = []
                for t in tag_ids:
                    try:
                        clean_tag_ids.append(int(t))
                    except (ValueError, TypeError):
                        pass
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
                for tid in clean_tag_ids:
                    cur.execute(
                        "INSERT IGNORE INTO yyt_todo_tag_rel (todo_id, tag_id) VALUES (%s, %s)",
                        (new_id, tid)
                    )
                if not is_global:
                    assignees = data.get('assignees') or []
                    clean_ids = []
                    for a in assignees:
                        try:
                            clean_ids.append(int(a))
                        except (ValueError, TypeError):
                            pass
                    if not clean_ids:
                        clean_ids = [user['id']]
                    clean_ids = list(dict.fromkeys(clean_ids))
                    for uid in clean_ids:
                        cur.execute(
                            "INSERT INTO yyt_todo_assign (todo_id, user_id) VALUES (%s, %s)",
                            (new_id, uid)
                        )
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            tag_filter = request.args.get('tag') or ''
            sql = (
                "SELECT t.id, t.title, t.link, t.content, t.created_at, t.is_global, "
                "COALESCE(a.is_done, 0) AS is_done, a.done_at AS my_done_at, u.name AS creator_name, u.avatar AS creator_avatar "
                "FROM yyt_todo t "
                "JOIN yyt_user u ON t.creator_id = u.id "
                "LEFT JOIN yyt_todo_assign a ON a.todo_id = t.id AND a.user_id = %s "
                "WHERE (t.is_global = 1 OR a.user_id = %s)"
            )
            params = [user['id'], user['id']]
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
                    "WHERE ta.todo_id IN (" + placeholders + ") AND ta.is_done = 1",
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
                    r['done_users'] = done_map.get(r['id'], [])
                    r['tags'] = tag_map.get(r['id'], [])
        return {"code": 0, "data": rows}
    finally:
        db.close()
