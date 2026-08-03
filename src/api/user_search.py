from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    q = (request.args.get('q') or '').strip()
    db = get_db()
    try:
        with db.cursor() as cur:
            if q:
                cur.execute(
                    "SELECT id, name, avatar FROM yyt_user WHERE name LIKE %s ORDER BY name ASC LIMIT 8",
                    ('%' + q + '%',)
                )
            else:
                cur.execute(
                    "SELECT id, name, avatar FROM yyt_user ORDER BY name ASC LIMIT 8"
                )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
