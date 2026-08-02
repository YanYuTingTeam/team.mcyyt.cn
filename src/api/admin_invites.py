from utils.auth import check_login
from utils.db import get_db
from utils.todo_notify import _init_table, add_user_notice

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if (user.get('level') or 0) < 5:
        return {"code": 403, "message": "仅服主可查看全部邀请码"}
    db = get_db()
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            action = data.get('action') or ''
            code = (data.get('code') or '').strip()
            if not code:
                return {"code": 400, "message": "缺少邀请码"}
            if action == 'disable':
                with db.cursor() as cur:
                    _init_table(cur)
                    cur.execute(
                        "SELECT code, created_by, used_by FROM yyt_invite WHERE code = %s",
                        (code,)
                    )
                    inv = cur.fetchone()
                    if not inv:
                        return {"code": 404, "message": "邀请码不存在"}
                    if inv.get('used_by'):
                        return {"code": 400, "message": "该邀请码已被使用, 无法标记失效"}
                    cur.execute("UPDATE yyt_invite SET disabled = 1 WHERE code = %s", (code,))
                    db.commit()
                    if inv.get('created_by'):
                        try:
                            add_user_notice(
                                inv['created_by'],
                                '邀请码被标记为失效',
                                f'邀请码 #{code} 已被管理员标记为失效, 不可再使用.'
                            )
                        except Exception:
                            pass
                return {"code": 0, "message": "ok"}
            return {"code": 400, "message": "未知操作"}
        with db.cursor() as cur:
            _init_table(cur)
            cur.execute(
                "SELECT i.code, i.created_at, i.used_at, i.disabled, "
                "cu.id AS creator_id, cu.name AS creator_name, cu.avatar AS creator_avatar, "
                "uu.name AS used_name, uu.email AS used_email, uu.avatar AS used_avatar "
                "FROM yyt_invite i "
                "LEFT JOIN yyt_user cu ON i.created_by = cu.id "
                "LEFT JOIN yyt_user uu ON i.used_by = uu.id "
                "ORDER BY i.created_at DESC"
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
