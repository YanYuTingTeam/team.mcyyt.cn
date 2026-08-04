import os
from utils.auth import check_login
from utils.db import get_db

_VERSION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'version.txt')

def _read_version():
    try:
        with open(_VERSION_PATH, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return ''

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        since = request.args.get('since') or ''
        version = _read_version()
        notices = []
        if since and since.isdigit():
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, title, content, created_at FROM yyt_notice "
                    "WHERE (user_id = %s OR user_id IS NULL) AND id > %s "
                    "ORDER BY id DESC LIMIT 20",
                    (user['id'], int(since))
                )
                notices = cur.fetchall()
        return {"code": 0, "data": {"version": version, "notices": notices}}
    finally:
        db.close()
