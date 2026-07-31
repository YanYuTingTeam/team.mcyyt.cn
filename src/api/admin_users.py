from utils.auth import check_login
from utils.db import get_db

def _one(cur, sql, args=None):
    cur.execute(sql, args or ())
    r = cur.fetchone()
    return int((r or {}).get('c') or 0)

def _detail(db, uid):
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, email, name, role, level, skill, apikey, panel_host, created_at "
            "FROM yyt_user WHERE id = %s", (uid,)
        )
        user = cur.fetchone()
        if not user:
            return None
        sessions = cur.execute(
            "SELECT id, token, ip, ua, expire_time, created_at "
            "FROM yyt_session WHERE user_id = %s ORDER BY expire_time DESC LIMIT 20",
            (uid,)
        )
        sessions = cur.fetchall()
        invites_created = cur.execute(
            "SELECT i.code, i.created_at, i.used_at, "
            "uu.name AS used_name, uu.email AS used_email "
            "FROM yyt_invite i LEFT JOIN yyt_user uu ON i.used_by = uu.id "
            "WHERE i.created_by = %s ORDER BY i.created_at DESC",
            (uid,)
        )
        invites_created = cur.fetchall()
        cur.execute(
            "SELECT i.code, i.created_at, i.used_at, "
            "cu.name AS creator_name "
            "FROM yyt_invite i LEFT JOIN yyt_user cu ON i.created_by = cu.id "
            "WHERE i.used_by = %s LIMIT 1", (uid,)
        )
        invite_used = cur.fetchone()
        stats = {
            "api_total": _one(cur, "SELECT COUNT(*) AS c FROM yyt_api_log WHERE user_id = %s", (uid,)),
            "api_today": _one(cur, "SELECT COUNT(*) AS c FROM yyt_api_log WHERE user_id = %s AND DATE(created_at) = CURDATE()", (uid,)),
            "api_week": _one(cur, "SELECT COUNT(*) AS c FROM yyt_api_log WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)", (uid,)),
            "visits_total": _one(cur, "SELECT COUNT(*) AS c FROM yyt_visit WHERE user_id = %s", (uid,)),
            "visits_today": _one(cur, "SELECT COUNT(*) AS c FROM yyt_visit WHERE user_id = %s AND DATE(created_at) = CURDATE()", (uid,))
        }
        cur.execute(
            "SELECT ip, path, created_at FROM yyt_api_log "
            "WHERE user_id = %s ORDER BY id DESC LIMIT 30",
            (uid,)
        )
        recent_logs = cur.fetchall()
        cur.execute(
            "SELECT page_key, min_level, show_in_nav FROM yyt_page_access"
        )
        pages = cur.fetchall()
    return {
        "user": user,
        "sessions": sessions,
        "invites_created": invites_created,
        "invite_used": invite_used,
        "stats": stats,
        "recent_logs": recent_logs,
        "pages": pages
    }

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
                if 'name' in data:
                    nm = (data.get('name') or '').strip()
                    if nm:
                        cur.execute("UPDATE yyt_user SET name = %s WHERE id = %s", (nm, uid))
                if 'panel_host' in data:
                    ph = (data.get('panel_host') or '').strip()
                    cur.execute("UPDATE yyt_user SET panel_host = %s WHERE id = %s", (ph or None, uid))
                if 'kill_session' in data:
                    cur.execute("DELETE FROM yyt_session WHERE id = %s AND user_id = %s", (data['kill_session'], uid))
            db.commit()
            return {"code": 0, "message": "ok"}
        args = request.args if hasattr(request, 'args') else {}
        detail_id = args.get('id')
        if detail_id:
            d = _detail(db, detail_id)
            if not d:
                return {"code": 404, "message": "用户不存在"}
            return {"code": 0, "data": d}
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, level, skill, apikey, panel_host, created_at "
                "FROM yyt_user ORDER BY level DESC, id ASC"
            )
            rows = cur.fetchall()
        return {"code": 0, "data": rows}
    finally:
        db.close()
