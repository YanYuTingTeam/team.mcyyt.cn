from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    token = request.cookies.get('yyt_token')
    db = get_db()
    try:
        with db.cursor() as cur:
            apikey = user['apikey']
            cur.execute(
                "SELECT SUM(DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)) AS yesterday, "
                "SUM(DATE(created_at) = CURDATE()) AS today, "
                "SUM(created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)) AS week, "
                "SUM(created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)) AS month "
                "FROM yyt_api_log WHERE user_id = %s",
                (user['id'],)
            )
            calls = cur.fetchone()
            calls = {k: int(v or 0) for k, v in calls.items()}
            cur.execute(
                "SELECT i.code, i.created_at, i.used_at, u.name AS used_name, u.email AS used_email, u.avatar AS used_avatar "
                "FROM yyt_invite i LEFT JOIN yyt_user u ON i.used_by = u.id "
                "WHERE i.created_by = %s ORDER BY i.created_at DESC",
                (user['id'],)
            )
            invites = cur.fetchall()
            cur.execute(
                "SELECT id, ip, ua, created_at, (token = %s) AS is_current "
                "FROM yyt_session WHERE user_id = %s AND expire_time > NOW() ORDER BY id DESC",
                (token, user['id'])
            )
            sessions = cur.fetchall()
            for s in sessions:
                s['is_current'] = int(s['is_current'] or 0)
        db.commit()
        return {"code": 0, "data": {"user": user, "apikey": apikey, "calls": calls, "invites": invites, "sessions": sessions}}
    finally:
        db.close()
