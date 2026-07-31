import uuid
import secrets
from utils.auth import check_login
from utils.db import get_db

def make_panel_host():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(secrets.choice(chars) for _ in range(8))

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    new_key = str(uuid.uuid4())
    panel_host = user.get('panel_host') or make_panel_host()
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE yyt_user SET apikey = %s, panel_host = %s WHERE id = %s",
                (new_key, panel_host, user['id'])
            )
        db.commit()
        return {"code": 0, "data": {"apikey": new_key, "panel_host": panel_host}}
    finally:
        db.close()
