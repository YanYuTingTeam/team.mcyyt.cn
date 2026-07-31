from utils.auth import check_login
from utils.db import get_db

def _one(cur, sql, args=None):
    cur.execute(sql, args or ())
    r = cur.fetchone()
    return int((r or {}).get('c') or 0)

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if (user.get('level') or 0) < 5:
        return {"code": 403, "message": "仅服主可查看统计"}
    db = get_db()
    try:
        with db.cursor() as cur:
            stats = {
                "users": _one(cur, "SELECT COUNT(*) AS c FROM yyt_user"),
                "api_total": _one(cur, "SELECT COUNT(*) AS c FROM yyt_api_log"),
                "api_today": _one(cur, "SELECT COUNT(*) AS c FROM yyt_api_log WHERE DATE(created_at) = CURDATE()"),
                "api_week": _one(cur, "SELECT COUNT(*) AS c FROM yyt_api_log WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),
                "visits_total": _one(cur, "SELECT COUNT(*) AS c FROM yyt_visit"),
                "visits_today": _one(cur, "SELECT COUNT(*) AS c FROM yyt_visit WHERE DATE(created_at) = CURDATE()"),
                "visits_week": _one(cur, "SELECT COUNT(*) AS c FROM yyt_visit WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),
                "notices": _one(cur, "SELECT COUNT(*) AS c FROM yyt_notice"),
                "projects": _one(cur, "SELECT COUNT(*) AS c FROM yyt_project"),
                "todos": _one(cur, "SELECT COUNT(*) AS c FROM yyt_todo"),
                "invites": _one(cur, "SELECT COUNT(*) AS c FROM yyt_invite"),
                "invites_used": _one(cur, "SELECT COUNT(*) AS c FROM yyt_invite WHERE used_by IS NOT NULL"),
                "sessions": _one(cur, "SELECT COUNT(*) AS c FROM yyt_session WHERE expire_time > NOW()")
            }
        return {"code": 0, "data": stats}
    finally:
        db.close()
