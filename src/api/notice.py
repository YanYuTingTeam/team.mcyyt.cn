from utils.auth import check_login
from utils.db import get_db
from utils.todo_notify import _init_table, get_base_url
from utils.mailer import send_template_email

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        if request.method == 'POST':
            if (user.get('level') or 0) < 4:
                return {"code": 403, "message": "仅管理员及以上可发布通知"}
            data = request.get_json(silent=True) or {}
            title = (data.get('title') or '').strip()
            if not title:
                return {"code": 400, "message": "标题不能为空"}
            content = (data.get('content') or '').strip()
            base_url = get_base_url()
            ids_to_notify = []
            with db.cursor() as cur:
                _init_table(cur)
                target_user_id = data.get('user_id')
                if target_user_id:
                    uid = int(target_user_id)
                    cur.execute("INSERT INTO yyt_notice (user_id, title, content) VALUES (%s, %s, %s)", (uid, title, content or None))
                    ids_to_notify.append(uid)
                else:
                    cur.execute("SELECT id, email, name FROM yyt_user WHERE email IS NOT NULL AND status != 3")
                    users = cur.fetchall()
                    for u in users:
                        cur.execute(
                            "INSERT INTO yyt_notice (user_id, title, content) VALUES (%s, %s, %s)",
                            (u['id'], title, content or None)
                        )
                    ids_to_notify = [u['id'] for u in users if u.get('email')]
                db.commit()
            if ids_to_notify:
                try:
                    with db.cursor() as cur2:
                        if ids_to_notify:
                            ph = ','.join(['%s'] * len(ids_to_notify))
                            cur2.execute(
                                f"SELECT id, email, name FROM yyt_user WHERE id IN ({ph}) AND status != 3",
                                ids_to_notify
                            )
                        else:
                            cur2.execute("SELECT id, email, name FROM yyt_user WHERE 1=0")
                        rows = cur2.fetchall()
                    for u in rows:
                        if not u.get('email'):
                            continue
                        vars = {
                            'NOTICE_TITLE': title,
                            'NOTICE_CONTENT': content or '',
                            'NOTICE_CREATED_AT': '-',
                            'BASE_URL': base_url,
                            'USER_NAME': u.get('name') or '',
                        }
                        send_template_email(u['email'], '[@team] 通知动态: ' + title, 'user_notice.html', vars)
                except Exception:
                    pass
            return {"code": 0, "message": "ok"}
        with db.cursor() as cur:
            _init_table(cur)
            since = request.args.get('since') or ''
            if since and since.isdigit():
                cur.execute(
                    "SELECT id, title, content, created_at FROM yyt_notice "
                    "WHERE (user_id = %s OR user_id IS NULL) AND id > %s "
                    "ORDER BY id DESC LIMIT 20",
                    (user['id'], int(since))
                )
            else:
                cur.execute(
                    "SELECT id, title, content, created_at FROM yyt_notice "
                    "WHERE user_id = %s OR user_id IS NULL "
                    "ORDER BY id DESC LIMIT 20",
                    (user['id'],)
                )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
