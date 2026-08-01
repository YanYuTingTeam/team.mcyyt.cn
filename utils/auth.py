import secrets
import hmac
import hashlib
import time
from utils.db import get_db
from config import MCSM_CONFIG

_avatar_col_ensured = False
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

def make_token():
    return secrets.token_hex(32)

def get_client_info(request):
    ip = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    if not ip:
        ip = (request.headers.get('X-Real-IP') or '').strip()
    if not ip:
        ip = request.remote_addr or ''
    ua = (request.headers.get('User-Agent') or '')[:255]
    return ip[:64], ua

def check_login(request):
    token = request.cookies.get('yyt_token')
    if not token:
        return None
    _ensure_avatar_col()
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT u.id, u.email, u.name, u.role, u.level, u.skill, u.apikey, u.panel_host, u.avatar, u.bio, u.created_at "
                "FROM yyt_session s JOIN yyt_user u ON s.user_id = u.id "
                "WHERE s.token = %s AND s.expire_time > NOW()",
                (token,)
            )
            return cur.fetchone()
    finally:
        db.close()

def calc_sign(apikey, a, path, salt):
    msg = (apikey + a + path).encode('utf-8')
    return hmac.new(salt.encode('utf-8'), msg, hashlib.md5).hexdigest()

def verify_sign(request):
    apikey = (request.headers.get('X-API-Key') or request.args.get('apikey') or request.cookies.get('mcsm_proxy_key') or '').strip()
    a = (request.headers.get('a') or request.args.get('a') or '').strip()
    b = (request.headers.get('b') or request.args.get('b') or '').strip()
    if not apikey or not a or not b or not a.isdigit():
        return None
    now = int(time.time() * 1000)
    window = MCSM_CONFIG.get('sign_window', 300) * 1000
    if abs(now - int(a)) > window:
        return None
    expect = calc_sign(apikey, a, request.path, MCSM_CONFIG.get('salt', ''))
    if not hmac.compare_digest(expect, b):
        return None
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
    if not row or (row.get('level') or 0) < 1:
        return None
    return row

def log_api_call(request, user):
    ip, _ = get_client_info(request)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_api_log (user_id, ip, path) VALUES (%s, %s, %s)",
                (user['id'], ip, request.path[:128])
            )
        db.commit()
    finally:
        db.close()
