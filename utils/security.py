import ipaddress
from datetime import datetime, timedelta
from utils.db import get_db

def _is_private_ip(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True

def get_client_ip(request):
    ip = (request.remote_addr or '').strip()
    if ip and not _is_private_ip(ip):
        return ip
    real_ip = (request.headers.get('X-Real-IP') or '').strip()
    if real_ip and not _is_private_ip(real_ip):
        return real_ip
    xff = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    if xff and not _is_private_ip(xff):
        return xff
    return ip or real_ip or xff or '0.0.0.0'


def ip_segment(ip):
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv4Address):
            # /24 网段: a.b.c.*
            net = ipaddress.ip_network((ip, 24), strict=False)
            return str(net.network_address) + '/24'
        else:
            # IPv6: /64 前缀
            net = ipaddress.ip_network((ip, 64), strict=False)
            return str(net.network_address) + '/64'
    except ValueError:
        return ip


def _cleanup(db):
    with db.cursor() as cur:
        cur.execute("DELETE FROM yyt_sec_counter WHERE expire_at IS NOT NULL AND expire_at < NOW()")
        cur.execute("DELETE FROM yyt_sec_ban WHERE expire_at < NOW()")
    db.commit()


def check_ban(request, ban_type='any'):
    ip = get_client_ip(request)
    seg = ip_segment(ip)
    db = get_db()
    try:
        _cleanup(db)
        with db.cursor() as cur:
            cur.execute(
                "SELECT ban_type, expire_at FROM yyt_sec_ban "
                "WHERE (target = %s OR target = %s) AND expire_at > NOW() "
                "AND (ban_type = %s OR ban_type = 'any' OR %s = 'any') "
                "ORDER BY expire_at DESC LIMIT 1",
                (ip, seg, ban_type, ban_type)
            )
            row = cur.fetchone()
            if row:
                return True, row['ban_type'], row['expire_at'], seg
        return False, None, None, seg
    finally:
        db.close()


def add_ban(target, ban_type, hours):
    db = get_db()
    try:
        expire = datetime.now() + timedelta(hours=hours)
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_sec_ban (target, ban_type, expire_at) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE expire_at = GREATEST(expire_at, VALUES(expire_at)), ban_type = VALUES(ban_type)",
                (target, ban_type, expire)
            )
        db.commit()
    finally:
        db.close()


def _incr_counter(key, window_seconds, max_val=None):
    expire = datetime.now() + timedelta(seconds=window_seconds)
    db = get_db()
    try:
        _cleanup(db)
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_sec_counter (c_key, c_count, expire_at) VALUES (%s, 1, %s) "
                "ON DUPLICATE KEY UPDATE c_count = c_count + 1, expire_at = GREATEST(expire_at, VALUES(expire_at))",
                (key, expire)
            )
            cur.execute("SELECT c_count FROM yyt_sec_counter WHERE c_key = %s", (key,))
            row = cur.fetchone()
            cnt = int((row or {}).get('c_count') or 0)
        db.commit()
        over = (max_val is not None and cnt > max_val)
        return cnt, over
    finally:
        db.close()


def _get_counter(key):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT c_count, expire_at FROM yyt_sec_counter WHERE c_key = %s AND (expire_at IS NULL OR expire_at > NOW())", (key,))
            row = cur.fetchone()
        return int((row or {}).get('c_count') or 0)
    finally:
        db.close()


def _reset_counter(key):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM yyt_sec_counter WHERE c_key = %s", (key,))
        db.commit()
    finally:
        db.close()


# ===== 未登录限流: 1小时内超过 N 次请求 → 封禁 1 小时 =====
RATE_LIMIT_MAX = 3       # 1小时窗口内最大请求数
RATE_LIMIT_WINDOW = 3600   # w秒 = 1小时
RATE_BAN_HOURS = 1         # 触发后封禁1小时


def rate_tick(request):
    banned, btype, exp, seg = check_ban(request, 'rate')
    if banned:
        return True, 'rate', exp
    ip = get_client_ip(request)
    key = f"rl:{ip}"
    cnt, over = _incr_counter(key, RATE_LIMIT_WINDOW, RATE_LIMIT_MAX)
    if over:
        add_ban(ip, 'rate', RATE_BAN_HOURS)
        _reset_counter(key)
        return True, 'rate', datetime.now() + timedelta(hours=RATE_BAN_HOURS)
    return False, None, None


# ===== 登录/注册失败计数: 3次失败 → 封禁IP段24h =====
ATTEMPT_MAX = 3
ATTEMPT_WINDOW = 3600 * 2  # 2小时内累计，过期清零
ATTEMPT_BAN_HOURS = 24


def login_attempt_incr(request, success):
    seg = ip_segment(get_client_ip(request))
    key = f"fail_login:{seg}"
    if success:
        _reset_counter(key)
        return 0, False
    cnt, over = _incr_counter(key, ATTEMPT_WINDOW, ATTEMPT_MAX)
    if over:
        add_ban(seg, 'auth', ATTEMPT_BAN_HOURS)
        _reset_counter(key)
        return ATTEMPT_MAX, True
    return cnt, False


def login_attempt_remaining(request):
    seg = ip_segment(get_client_ip(request))
    key = f"fail_login:{seg}"
    used = _get_counter(key)
    return max(0, ATTEMPT_MAX - used)


def register_attempt_incr(request, success):
    seg = ip_segment(get_client_ip(request))
    key = f"fail_reg:{seg}"
    if success:
        _reset_counter(key)
        return 0, False
    cnt, over = _incr_counter(key, ATTEMPT_WINDOW, ATTEMPT_MAX)
    if over:
        add_ban(seg, 'auth', ATTEMPT_BAN_HOURS)
        _reset_counter(key)
        return ATTEMPT_MAX, True
    return cnt, False


def register_attempt_remaining(request):
    seg = ip_segment(get_client_ip(request))
    key = f"fail_reg:{seg}"
    used = _get_counter(key)
    return max(0, ATTEMPT_MAX - used)


def check_auth_ban(request):
    return check_ban(request, 'auth')


def is_ajax_api(request):
    accept = (request.headers.get('Accept') or '').lower()
    xreq = (request.headers.get('X-Requested-With') or '').lower()
    path = request.path or ''
    if path.startswith('/api/') or path.startswith('/mcsm_proxy/'):
        return True
    if 'application/json' in accept or 'xmlhttprequest' in xreq:
        return True
    return False

# 同一设备 120s 内只能发 1 次; 同一 IP 段 24h 内最多 3 次, 超出则封 24h
EMAIL_CODE_DEVICE_WINDOW = 120
EMAIL_CODE_SEG_MAX = 3
EMAIL_CODE_SEG_WINDOW = 86400
EMAIL_CODE_BAN_HOURS = 24


def check_email_rate(request):
    """返回 (ok, message)"""
    ip = get_client_ip(request)
    seg = ip_segment(ip)
    ua_hash = _ua_hash_from_request(request)
    db = get_db()
    try:
        _cleanup(db)
        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM yyt_email_code "
                "WHERE ua_hash = %s AND ip_seg = %s AND created_at > DATE_SUB(NOW(), INTERVAL %s SECOND) "
                "ORDER BY id DESC LIMIT 1",
                (ua_hash, seg, EMAIL_CODE_DEVICE_WINDOW)
            )
            if cur.fetchone():
                return False, 'badly request'
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM yyt_email_code "
                "WHERE ip_seg = %s AND created_at > DATE_SUB(NOW(), INTERVAL %s SECOND)",
                (seg, EMAIL_CODE_SEG_WINDOW)
            )
            row = cur.fetchone()
            cnt = int((row or {}).get('cnt') or 0)
            if cnt >= EMAIL_CODE_SEG_MAX:
                add_ban(seg, 'email', EMAIL_CODE_BAN_HOURS)
                return False, 'badly request'
        return True, 'ok'
    finally:
        db.close()


def _ua_hash_from_request(request):
    import hashlib
    ua = (request.headers.get('User-Agent') or '')[:255]
    return hashlib.md5(ua.encode()).hexdigest()[:16]
