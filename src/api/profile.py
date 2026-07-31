from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    skill = (data.get('skill') or '').strip()
    if not name:
        return {"code": 400, "message": "昵称不能为空"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE yyt_user SET name = %s, skill = %s WHERE id = %s",
                (name, skill or None, user['id'])
            )
        db.commit()
        return {"code": 0, "message": "ok"}
    finally:
        db.close()
