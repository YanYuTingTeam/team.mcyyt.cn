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
                    cur.execute(
                        "UPDATE yyt_todo SET is_done = %s WHERE id = %s AND user_id = %s",
                        (1 if data.get('done') else 0, data['id'], user['id'])
                    )
                else:
                    title = (data.get('title') or '').strip()
                    if not title:
                        return {"code": 400, "message": "事项内容不能为空"}
                    cur.execute(
                        "INSERT INTO yyt_todo (user_id, title, link) VALUES (%s, %s, %s)",
                        (user['id'], title, (data.get('link') or '').strip() or None)
                    )
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, title, link, is_done, created_at FROM yyt_todo WHERE user_id = %s ORDER BY is_done ASC, id DESC",
                (user['id'],)
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
