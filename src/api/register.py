import bcrypt
from flask import jsonify
from utils.db import get_db
from utils.auth import make_token

def handle(request):
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip()
    invite_code = (data.get('invite_code') or '').strip()
    if not email or not password or not name or not invite_code:
        return {"code": 400, "message": "请把信息填完整"}
    if len(password) < 6:
        return {"code": 400, "message": "密码至少6位"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT code FROM yyt_invite WHERE code = %s AND used_by IS NULL", (invite_code,))
            if not cur.fetchone():
                return {"code": 403, "message": "邀请码无效或已被使用"}
            cur.execute("SELECT id FROM yyt_user WHERE email = %s", (email,))
            if cur.fetchone():
                return {"code": 409, "message": "该邮箱已注册"}
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO yyt_user (email, password_hash, name) VALUES (%s, %s, %s)",
                (email, pw_hash, name)
            )
            user_id = cur.lastrowid
            cur.execute(
                "UPDATE yyt_invite SET used_by = %s, used_at = NOW() WHERE code = %s",
                (user_id, invite_code)
            )
            token = make_token()
            cur.execute(
                "INSERT INTO yyt_session (token, user_id, expire_time) VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 7 DAY))",
                (token, user_id)
            )
        db.commit()
    finally:
        db.close()
    resp = jsonify({"code": 0, "message": "ok"})
    resp.set_cookie('yyt_token', token, max_age=7 * 24 * 3600, httponly=True, samesite='Lax')
    return resp
