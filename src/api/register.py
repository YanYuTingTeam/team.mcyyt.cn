import re
import bcrypt
from flask import jsonify
from utils.db import get_db
from utils.auth import make_token, get_client_info

def check_pw_strong(pw):
    return (len(pw) >= 12 and re.search(r'[A-Z]', pw) and re.search(r'[a-z]', pw)
            and re.search(r'\d', pw) and re.search(r'[^A-Za-z0-9]', pw))

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
    if not check_pw_strong(password):
        return {"code": 400, "message": "密码不符合要求: 至少 12 位, 含大小写字母、数字和符号"}
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
            ip, ua = get_client_info(request)
            cur.execute(
                "INSERT INTO yyt_session (token, user_id, ip, ua, expire_time) VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 7 DAY))",
                (token, user_id, ip, ua)
            )
        db.commit()
    finally:
        db.close()
    resp = jsonify({"code": 0, "message": "ok"})
    resp.set_cookie('yyt_token', token, max_age=7 * 24 * 3600, httponly=True, samesite='Lax')
    return resp
