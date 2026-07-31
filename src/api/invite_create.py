import secrets
from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    invite = 'YYT-' + secrets.token_hex(4).upper()
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_invite (code, created_by) VALUES (%s, %s)",
                (invite, user['id'])
            )
        db.commit()
        return {"code": 0, "data": {"invite": invite}}
    finally:
        db.close()
