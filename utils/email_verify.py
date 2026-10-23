import hmac
from utils.db import get_db
from utils.security import _incr_counter, _reset_counter

FAIL_MAX = 5

def verify_email_code(email, code, purpose):
    """验证邮箱验证码, 成功返回 (True, None), 失败返回 (False, msg)"""
    if not email or not code:
        return False, '请输入验证码'
    if not (code.isdigit() and len(code) == 6):
        return False, '验证码格式错误'
    fail_key = f"email_code_fail:{email}:{purpose}"
    cnt, _ = _incr_counter(fail_key, 86400, FAIL_MAX)
    if cnt >= FAIL_MAX:
        return False, '验证码错误或已过期'
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, code FROM yyt_email_code "
                "WHERE email = %s AND purpose = %s AND used = 0 AND expire_at > NOW() "
                "ORDER BY id DESC LIMIT 1",
                (email, purpose)
            )
            row = cur.fetchone()
            if not row or not hmac.compare_digest(str(row.get('code') or ''), code):
                return False, '验证码错误或已过期'
            cur.execute("UPDATE yyt_email_code SET used = 1 WHERE id = %s", (row['id'],))
            cur.execute(
                "DELETE FROM yyt_email_code WHERE email = %s AND purpose = %s",
                (email, purpose)
            )
        _reset_counter(fail_key)
        db.commit()
        return True, None
    finally:
        db.close()
