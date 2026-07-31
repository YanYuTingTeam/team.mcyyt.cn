from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        if request.method == 'POST':
            if (user.get('level') or 0) < 4:
                return {"code": 403, "message": "仅管理员及以上可发布通知"}
            data = request.get_json(silent=True) or {}
            title = (data.get('title') or '').strip()
            if not title:
                return {"code": 400, "message": "标题不能为空"}
            content = (data.get('content') or '').strip()
            with db.cursor() as cur:
                cur.execute("INSERT INTO yyt_notice (title, content) VALUES (%s, %s)", (title, content or None))
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            cur.execute("SELECT id, title, content, created_at FROM yyt_notice ORDER BY id DESC LIMIT 20")
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
