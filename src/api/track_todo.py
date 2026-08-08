from utils.auth import check_login
from utils.db import get_db
from utils.todo_notify import _init_table

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        with db.cursor() as cur:
            _init_table(cur)
            if request.method == 'POST':
                data = request.get_json(silent=True) or {}
                todo_id = data.get('todo_id')
                if data.get('clear') or not todo_id:
                    cur.execute("UPDATE yyt_user SET track_todo_id = NULL WHERE id = %s", (user['id'],))
                else:
                    todo_id = int(todo_id)
                    cur.execute(
                        "SELECT id FROM yyt_todo WHERE id = %s AND (is_global = 1 OR "
                        "EXISTS (SELECT 1 FROM yyt_todo_assign WHERE todo_id = %s AND user_id = %s) OR creator_id = %s)",
                        (todo_id, todo_id, user['id'], user['id'])
                    )
                    if not cur.fetchone():
                        return {"code": 403, "message": "无权追踪此待办"}
                    cur.execute("UPDATE yyt_user SET track_todo_id = %s WHERE id = %s", (todo_id, user['id']))
                db.commit()
                return {"code": 0, "message": "ok"}
            cur.execute("SELECT track_todo_id FROM yyt_user WHERE id = %s", (user['id'],))
            row = cur.fetchone()
            tid = row['track_todo_id'] if row else None
            track = None
            if tid:
                cur.execute(
                    "SELECT t.id, t.title, t.link, t.content, t.created_at, t.is_global, "
                    "u.id AS creator_id, u.name AS creator_name, u.avatar AS creator_avatar, u.status AS creator_status "
                    "FROM yyt_todo t JOIN yyt_user u ON t.creator_id = u.id WHERE t.id = %s AND t.deleted_at IS NULL",
                    (tid,)
                )
                track = cur.fetchone()
                if track:
                    track['creator_deactivated'] = (track.get('creator_status') == 3)
                    cur.execute(
                        "SELECT r.tag_id AS id, tg.name, tg.color "
                        "FROM yyt_todo_tag_rel r JOIN yyt_todo_tag tg ON r.tag_id = tg.id WHERE r.todo_id = %s",
                        (tid,)
                    )
                    track['tags'] = cur.fetchall()
                    cur.execute(
                        "SELECT a.user_id, a.is_done, a.done_at, u.name, u.avatar, u.status AS user_status "
                        "FROM yyt_todo_assign a JOIN yyt_user u ON a.user_id = u.id "
                        "WHERE a.todo_id = %s ORDER BY a.is_done DESC, u.name ASC",
                        (tid,)
                    )
                    assigns = cur.fetchall()
                    track['assignees'] = [{'id': r['user_id'], 'name': r['name'], 'avatar': r['avatar'], 'deactivated': r['user_status'] == 3} for r in assigns]
                    track['done_users'] = [{'id': r['user_id'], 'name': r['name'], 'avatar': r['avatar'], 'done_at': str(r['done_at']) if r['done_at'] else None, 'deactivated': r['user_status'] == 3} for r in assigns if r['is_done']]
                    my_assign = next((r for r in assigns if r['user_id'] == user['id']), None)
                    track['my_done'] = bool(my_assign and my_assign['is_done']) if my_assign else False
                    total = len(assigns)
                    done_cnt = sum(1 for r in assigns if r['is_done'])
                    track['progress'] = f"{done_cnt}/{total}" if total else '-'
        return {"code": 0, "data": {"track_todo_id": tid, "track": track}}
    finally:
        db.close()
