import uuid
from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    new_key = str(uuid.uuid4())
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE yyt_user SET apikey = %s WHERE id = %s", (new_key, user['id']))
        db.commit()
        return {"code": 0, "data": {"apikey": new_key}}
    finally:
        db.close()
