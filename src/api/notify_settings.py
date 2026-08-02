from utils.auth import check_login
from utils.db import get_db
from utils.todo_notify import _init_table, get_user_notify, NOTIFY_KEYS

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        with db.cursor() as cur:
            _init_table(cur)
            if request.method == 'POST':
                data = request.get_json(silent=True) or {}
                sets = {}
                for k in NOTIFY_KEYS:
                    if k in data:
                        sets[k] = 1 if data.get(k) else 0
                if sets:
                    parts = ','.join([f"{k} = %s" for k in sets])
                    vals = list(sets.values()) + [user['id']]
                    cur.execute(
                        f"INSERT INTO yyt_notify_setting (user_id, {','.join(sets.keys())}) VALUES (%s, {','.join(['%s']*len(sets))}) "
                        f"ON DUPLICATE KEY UPDATE {parts}",
                        [user['id']] + list(sets.values()) + vals
                    )
                    db.commit()
                return {"code": 0, "message": "ok"}
            s = get_user_notify(cur, user['id'])
        return {"code": 0, "data": s}
    finally:
        db.close()
