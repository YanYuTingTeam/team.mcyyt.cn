from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        if request.method == 'POST':
            if (user.get('level') or 0) < 4:
                return {"code": 403, "message": "仅管理员及以上可添加项目"}
            data = request.get_json(silent=True) or {}
            name = (data.get('name') or '').strip()
            if not name:
                return {"code": 400, "message": "项目名不能为空"}
            info = (data.get('info') or '').strip()
            link = (data.get('link') or '').strip()
            members = (data.get('members') or '').strip()
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO yyt_project (name, info, link, members) VALUES (%s, %s, %s, %s)",
                    (name, info or None, link or None, members or None)
                )
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            cur.execute("SELECT id, name, info, link, members, created_at FROM yyt_project ORDER BY id DESC")
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
