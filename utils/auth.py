import secrets
import hmac
import hashlib
import time
from utils.db import get_db
from config import MCSM_CONFIG

_avatar_col_ensured = False
_kick_users = set()

def _ensure_avatar_col():
    global _avatar_col_ensured
    if _avatar_col_ensured:
        return
    try:
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("SHOW COLUMNS FROM yyt_user LIKE 'avatar'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE yyt_user ADD COLUMN avatar VARCHAR(512) DEFAULT NULL AFTER panel_host")
                cur.execute("SHOW COLUMNS FROM yyt_user LIKE 'bio'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE yyt_user ADD COLUMN bio TEXT DEFAULT NULL AFTER avatar")
                cur.execute("SHOW COLUMNS FROM yyt_notice LIKE 'created_by'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE yyt_notice ADD COLUMN created_by INT DEFAULT NULL AFTER content")
                db.commit()
        finally:
            db.close()
    except Exception:
        pass
    _avatar_col_ensured = True

def _load_kicked_users():
    global _kick_users
    try:
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, name FROM yyt_user WHERE name = '账号已注销' AND apikey IS NULL AND banned_until IS NOT NULL"
                )
                rows = cur.fetchall()
                _kick_users = set(int(r['id']) for r in rows if r.get('name') == '账号已注销')
        finally:
            db.close()
    except Exception:
        pass

def is_kicked_user(uid):
    _load_kicked_users()
    return int(uid) in _kick_users

def check_login(request):
    token = request.cookies.get('yyt_token')
    if not token:
        return None
    _ensure_avatar_col()
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT u.id, u.email, u.name, u.role, u.level, u.skill, u.apikey, u.panel_host, u.avatar, u.bio, u.banned_until, u.created_at "
                "FROM yyt_session s JOIN yyt_user u ON s.user_id = u.id "
                "WHERE s.token = %s AND s.expire_time > NOW()",
                (token,)
            )
            user = cur.fetchone()
            if user:
                if user.get('name') == '账号已注销':
                    user['_kick_reason'] = True
                    return None
            return user
    finally:
        db.close()

def get_user_kick_reason(user):
    if user and isinstance(user, dict):
        return user.get('_kick_reason', False)
    return False

def calc_sign(apikey, a, path, salt):
    msg = (apikey + a + path).encode('utf-8')
    return hmac.new(salt.encode('utf-8'), msg, hashlib.md5).hexdigest()

def verify_sign(request, debug=False):
    apikey = (request.headers.get('X-API-Key') or request.headers.get('X-API-KEY') or request.headers.get('Api-Key') or request.args.get('apikey') or request.args.get('api_key') or request.args.get('api-key') or '').strip()
    a = (request.headers.get('a') or request.headers.get('A') or request.args.get('a') or '').strip()
    b = (request.headers.get('b') or request.headers.get('B') or request.args.get('b') or '').strip()
    if not apikey or not a or not b or not a.isdigit():
        reason = '缺少签名参数: ' + ','.join([
            'no-apikey' if not apikey else '',
            'no-a' if not a else '',
            'no-b' if not b else '',
            'a-not-digit' if a and not a.isdigit() else ''
        ]).strip(',')
        if debug:
            print(f'[verify_sign FAIL({reason})] host={request.host} path={request.path} method={request.method} apikey={apikey[:8] + "...(" + str(len(apikey)) + ")" if apikey else "empty"} a={a} b={'len='+str(len(b)) if b else 'empty'}', flush=True)
        return None, reason
    now = int(time.time() * 1000)
    window = MCSM_CONFIG.get('sign_window', 300) * 1000
    diff = now - int(a)
    if abs(diff) > window:
        reason = f'签名过期: a={a} now={now} diff_ms={diff} window={window}'
        if debug:
            print(f'[verify_sign FAIL({reason})] host={request.host} path={request.path} method={request.method}', flush=True)
        return None, reason
    salt = MCSM_CONFIG.get('salt', '')
    expect = calc_sign(apikey, a, request.path, salt)
    if not hmac.compare_digest(expect, b):
        reason = f'签名不匹配: host={request.host} path={request.path} method={request.method} expect={expect[:8]}... got={b[:8]}... len(expect)={len(expect)} len(b)={len(b)}'
        if debug:
            print('[verify_sign FAIL(sign-mismatch)] ' + reason, flush=True)
        return None, '签名校验失败'
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, level, skill, apikey, panel_host, avatar, bio, created_at FROM yyt_user WHERE apikey = %s",
                (apikey,)
            )
            row = cur.fetchone()
    finally:
        db.close()
    if not row:
        reason = f'apikey不存在: apikey_prefix={apikey[:8] + "..." if apikey else "empty"}'
        if debug:
            print(f'[verify_sign FAIL(db-no-user)] host={request.host} {reason}', flush=True)
        return None, '该APIKey未在系统中登记'
    if row.get('name') == '账号已注销':
        return None, 'kick'
    if (row.get('level') or 0) < 1:
        reason = f'用户等级不足: level={row.get("level")} user={row.get("name")}'
        if debug:
            print(f'[verify_sign FAIL(level<1)] host={request.host} {reason}', flush=True)
        return None, '用户无权调用API'
    if debug:
        print(f'[verify_sign OK] host={request.host} path={request.path} user={row.get("name")} uid={row.get("id")}', flush=True)
    return row, ''

def log_api_call(request, user):
    ip, _ = get_client_info(request)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_api_log (user_id, path, ip, user_agent) VALUES (%s, %s, %s, %s)",
                (user['id'], request.path, ip, (request.headers.get('User-Agent') or '')[:200])
            )
    finally:
        db.close()

def get_client_info(request):
    forward = request.headers.get('X-Forwarded-For', '')
    if forward:
        ip = forward.split(',')[0].strip()
    else:
        ip = request.headers.get('X-Real-IP', request.remote_addr or '')
    return ip, request.headers.get('User-Agent', '')[:500]

def login_success(db, user_id, ip, ua, token):
    from datetime import datetime
    db.execute(
        "INSERT INTO yyt_session (token, user_id, ip, ua, expire_time) VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 7 DAY))",
        (token, user_id, ip, ua[:500])
    )

def logout_by_token(db, token):
    db.execute("DELETE FROM yyt_session WHERE token = %s", (token,))
