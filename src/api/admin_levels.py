from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if (user.get('level') or 0) < 5:
        return {"code": 403, "message": "仅服主可管理等级"}
    db = get_db()
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            lv = int(data.get('level') or -1)
            if lv < 0 or lv > 5:
                return {"code": 400, "message": "等级范围 0-5"}
            with db.cursor() as cur:
                if 'color' in data or 'name' in data:
                    color = data.get('color')
                    nm = data.get('name')
                    fields, vals = [], []
                    if color is not None:
                        fields.append("color = %s")
                        vals.append(color.strip() or None)
                    if nm is not None:
                        fields.append("name = %s")
                        vals.append(nm.strip() or None)
                    vals.append(lv)
                    cur.execute(
                        "INSERT INTO yyt_level_meta (level" +
                        (", color" if color is not None else "") +
                        (", name" if nm is not None else "") +
                        ") VALUES (%s" +
                        (", %s" if color is not None else "") +
                        (", %s" if nm is not None else "") +
                        ") ON DUPLICATE KEY UPDATE " + ", ".join(fields),
                        [lv] + vals[:-1]
                    )
                if 'pages' in data:
                    pages = data['pages'] or {}
                    for pk, pv in pages.items():
                        ml = int(pv.get('min_level') or 0)
                        sn = 1 if pv.get('show_in_nav') else 0
                        cur.execute(
                            "INSERT INTO yyt_page_access (page_key, min_level, show_in_nav) VALUES (%s, %s, %s) "
                            "ON DUPLICATE KEY UPDATE min_level = VALUES(min_level), show_in_nav = VALUES(show_in_nav)",
                            (pk, ml, sn)
                        )
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            cur.execute("SELECT level, name, color FROM yyt_level_meta ORDER BY level DESC")
            metas = cur.fetchall()
            cur.execute("SELECT page_key, min_level, show_in_nav FROM yyt_page_access")
            pages = cur.fetchall()
        return {"code": 0, "data": {"levels": metas, "pages": pages}}
    finally:
        db.close()
