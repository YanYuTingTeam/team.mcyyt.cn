from utils.db import get_db
from utils.auth import check_login


def _list(db):
    with db.cursor() as cur:
        cur.execute("SELECT id, name, color FROM yyt_skill_meta ORDER BY id ASC")
        rows = cur.fetchall()
    return [
        {"id": r["id"], "name": r["name"], "color": r.get("color") or "#ef5777"}
        for r in rows
    ]


def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        return {"code": 0, "message": "ok", "data": _list(db)}
    finally:
        db.close()
