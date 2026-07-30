from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, title, content, created_at FROM yyt_notice ORDER BY id DESC LIMIT 20")
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
