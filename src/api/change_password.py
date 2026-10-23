import bcrypt
import re
from utils.auth import check_login
from utils.db import get_db
from utils.email_verify import verify_email_code

def _check_pw_strong(pw):
    return (len(pw) >= 12 and re.search(r'[A-Z]', pw) and re.search(r'[a-z]', pw)
            and re.search(r'\d', pw) and re.search(r'[^A-Za-z0-9]', pw))

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    old_pwd = data.get('old_password') or ''
    new_pwd = data.get('new_password') or ''
    code = (data.get('email_code') or '').strip()
    if not old_pwd or not new_pwd:
        return {"code": 400, "message": "密码不能为空"}
    if not _check_pw_strong(new_pwd):
        return {"code": 400, "message": "新密码需至少12位, 含大小写字母/数字/特殊字符"}
    vok, vmsg = verify_email_code(user['email'], code, 'change_pwd')
    if not vok:
        return {"code": 400, "message": vmsg or '验证码错误'}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT password_hash FROM yyt_user WHERE id = %s", (user['id'],))
            row = cur.fetchone()
            if not row or not bcrypt.checkpw(old_pwd.encode(), row['password_hash'].encode()):
                return {"code": 403, "message": "原密码错误"}
            new_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt()).decode()
            cur.execute("UPDATE yyt_user SET password_hash = %s WHERE id = %s", (new_hash, user['id']))
            cur.execute(
                "DELETE FROM yyt_session WHERE user_id = %s AND token != %s",
                (user['id'], request.cookies.get('yyt_token') or '')
            )
        db.commit()
        return {"code": 0, "message": "密码修改成功"}
    finally:
        db.close()
