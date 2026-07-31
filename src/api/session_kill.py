from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    sid = data.get('sid')
    if not sid:
        return {"code": 400, "message": "缺少会话id"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM yyt_session WHERE id = %s AND user_id = %s", (sid, user['id']))
        db.commit()
        return {"code": 0, "message": "ok"}
    finally:
        db.close()
