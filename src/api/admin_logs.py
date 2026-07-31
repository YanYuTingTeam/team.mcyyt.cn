from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if (user.get('level') or 0) < 5:
        return {"code": 403, "message": "仅服主可查看全部日志"}
    limit = request.args.get('limit') or '50'
    try:
        limit = max(1, min(500, int(limit)))
    except (ValueError, TypeError):
        limit = 50
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT l.id, l.user_id, l.ip, l.path, l.created_at, u.name AS user_name "
                "FROM yyt_api_log l LEFT JOIN yyt_user u ON l.user_id = u.id "
                "ORDER BY l.id DESC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
