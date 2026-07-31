from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT ip, path, created_at FROM yyt_api_log WHERE user_id = %s ORDER BY id DESC LIMIT 500",
                (user['id'],)
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
