from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if (user.get('level') or 0) < 5:
        return {"code": 403, "message": "仅服主可查看全部邀请码"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT i.code, i.created_at, i.used_at, "
                "cu.name AS creator_name, uu.name AS used_name, uu.email AS used_email "
                "FROM yyt_invite i "
                "LEFT JOIN yyt_user cu ON i.created_by = cu.id "
                "LEFT JOIN yyt_user uu ON i.used_by = uu.id "
                "ORDER BY i.created_at DESC"
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
