from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            with db.cursor() as cur:
                if 'id' in data:
                    if data.get('done'):
                        cur.execute(
                            "UPDATE yyt_todo_assign SET is_done = 1, done_at = NOW() WHERE todo_id = %s AND user_id = %s",
                            (data['id'], user['id'])
                        )
                    else:
                        cur.execute(
                            "UPDATE yyt_todo_assign SET is_done = 0, done_at = NULL WHERE todo_id = %s AND user_id = %s",
                            (data['id'], user['id'])
                        )
                    db.commit()
                    return {"code": 0, "message": "ok"}
                title = (data.get('title') or '').strip()
                if not title:
                    return {"code": 400, "message": "事项标题不能为空"}
                link = (data.get('link') or '').strip()
                content = (data.get('content') or '').strip()
                cur.execute(
                    "INSERT INTO yyt_todo (creator_id, title, link, content) VALUES (%s, %s, %s, %s)",
                    (user['id'], title, link or None, content or None)
                )
                new_id = cur.lastrowid
                if not link:
                    cur.execute(
                        "UPDATE yyt_todo SET link = %s WHERE id = %s",
                        ('/todos/' + str(new_id), new_id)
                    )
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
            cur.execute(
                "SELECT t.id, t.title, t.link, t.content, t.created_at, a.is_done, u.name AS creator_name "
                "FROM yyt_todo_assign a "
                "JOIN yyt_todo t ON a.todo_id = t.id "
                "JOIN yyt_user u ON t.creator_id = u.id "
                "WHERE a.user_id = %s ORDER BY a.is_done ASC, t.id DESC",
                (user['id'],)
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
