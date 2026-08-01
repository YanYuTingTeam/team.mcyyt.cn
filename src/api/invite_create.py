import secrets
from utils.auth import check_login
from utils.db import get_db

PAGE_DEFAULT = {'min_level': 4, 'show_in_nav': 0}
PAGE_KEY = 'invite_create'

def _min_level(db):
    try:
        with db.cursor() as cur:
            cur.execute("SELECT min_level FROM yyt_page_access WHERE page_key = %s", (PAGE_KEY,))
            r = cur.fetchone()
        if r:
            return int(r.get('min_level') or PAGE_DEFAULT['min_level'])
    except Exception:
        pass
    return PAGE_DEFAULT['min_level']

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    db = get_db()
    try:
        if (user.get('level') or 0) < _min_level(db):
            return {"code": 403, "message": "权限不足, 无法生成邀请码"}
        invite = 'YYT-' + secrets.token_hex(4).upper()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_invite (code, created_by) VALUES (%s, %s)",
                (invite, user['id'])
            )
        db.commit()
        return {"code": 0, "data": {"invite": invite}}
    finally:
        db.close()
