from utils.auth import check_login
from utils.db import get_db

PAGE_DEFAULTS = {
    'home': (0, 1), 'overview': (0, 1), 'todo': (1, 1), 'notice': (1, 1),
    'project': (1, 1), 'apis': (1, 1), 'logs': (1, 1),
    'datatools': (1, 1), 'mcsm': (4, 1), 'team': (5, 1),
    'invite_create': (4, 0), 'settings': (0, 1)
}

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        if request.method == 'POST':
            if (user.get('level') or 0) < 5:
                return {"code": 403, "message": "仅服主可配置页面访问"}
            data = request.get_json(silent=True) or {}
            page_key = (data.get('page_key') or '').strip()
            if page_key not in PAGE_DEFAULTS:
                return {"code": 400, "message": "未知页面"}
            min_level = int(data.get('min_level') or 0)
            show_in_nav = 1 if data.get('show_in_nav') else 0
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO yyt_page_access (page_key, min_level, show_in_nav) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE min_level = VALUES(min_level), show_in_nav = VALUES(show_in_nav)",
                    (page_key, min_level, show_in_nav)
                )
            db.commit()
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            cur.execute("SELECT page_key, min_level, show_in_nav FROM yyt_page_access")
            rows = {r['page_key']: r for r in cur.fetchall()}
    finally:
        db.close()
    data = []
    for k, (ml, sn) in PAGE_DEFAULTS.items():
        r = rows.get(k)
        data.append({
            "page_key": k,
            "min_level": int(r['min_level']) if r else ml,
            "show_in_nav": int(r['show_in_nav']) if r else sn
        })
    return {"code": 0, "data": data}
