from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if (user.get('level') or 0) < 5:
        return {"code": 403, "message": "仅服主可管理成员"}
    db = get_db()
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            uid = data.get('id')
            if not uid:
                return {"code": 400, "message": "缺少用户ID"}
            with db.cursor() as cur:
                if 'level' in data:
                    lv = int(data.get('level') or 0)
                    if lv < 0 or lv > 5:
                        return {"code": 400, "message": "等级范围 0-5"}
                    cur.execute("UPDATE yyt_user SET level = %s WHERE id = %s", (lv, uid))
                if 'skill' in data:
                    sk = (data.get('skill') or '').strip()
                    cur.execute("UPDATE yyt_user SET skill = %s WHERE id = %s", (sk or None, uid))
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, level, skill, apikey, panel_host, created_at "
                "FROM yyt_user ORDER BY level DESC, id ASC"
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
