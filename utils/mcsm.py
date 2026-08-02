import json
import time
import secrets
import urllib.request
import urllib.error
from urllib.parse import parse_qsl, urlencode
from flask import Response
from config import MCSM_CONFIG
from utils.auth import verify_sign, log_api_call

PANEL_SESSIONS = {}
SESSION_TTL = 6 * 3600
SKIP_REQ_HEADERS = {'host', 'a', 'b', 'x-api-key', 'api-key', 'api_key', 'content-length', 'connection'}
_STRIP_QUERY = {'sec', 'apikey', 'api_key', 'api-key', 'a', 'b'}
_NATIVE_APIKEY = (MCSM_CONFIG.get('apikey') or '').strip()

def _deny(msg):
    return Response(
        json.dumps({"status": 403, "data": None, "message": msg}, ensure_ascii=False),
        status=403, mimetype="application/json"
    )

def _clean_sessions():
    now = time.time()
    for sid in [k for k, v in PANEL_SESSIONS.items() if v < now]:
        PANEL_SESSIONS.pop(sid, None)

def _forward(request, subpath, extra_set_cookie=None):
    base = MCSM_CONFIG['base'].rstrip('/')
    target = base + '/' + subpath
    pairs = parse_qsl(request.query_string.decode('utf-8', 'ignore'), keep_blank_values=True) if request.query_string else []
    filtered = [(k, v) for k, v in pairs if k not in _STRIP_QUERY]
    filtered.insert(0, ('apikey', _NATIVE_APIKEY))
    target += '?' + urlencode(filtered)
    if not _NATIVE_APIKEY and subpath.startswith('api'):
        return Response(
            json.dumps({"status": 503, "data": None, "message": "服务端尚未配置 MCSManager 原生管理员 apikey, 请联系管理员在 config.py MCSM_CONFIG['apikey'] 填入后重启代理进程"}, ensure_ascii=False),
            status=503, mimetype="application/json"
        )
    body = request.get_data() if request.method in ('POST', 'PUT', 'DELETE') else None
    req = urllib.request.Request(target, data=body, method=request.method)
    for k, v in request.headers.items():
        if k.lower() in SKIP_REQ_HEADERS:
            continue
        req.add_header(k, v)
    if not req.has_header('X-Requested-With'):
        req.add_header('X-Requested-With', 'XMLHttpRequest')
    if not req.has_header('Accept'):
        req.add_header('Accept', 'application/json, text/plain, */*')
    if not req.has_header('Content-Type'):
        req.add_header('Content-Type', 'application/json; charset=utf-8')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ctype = resp.headers.get('Content-Type', 'application/octet-stream')
            out = Response(data, status=resp.status, mimetype=ctype.split(';')[0])
            set_cookie = resp.headers.get_all('Set-Cookie') if hasattr(resp.headers, 'get_all') else None
            if set_cookie:
                for sc in set_cookie:
                    out.headers.add('Set-Cookie', sc)
            if extra_set_cookie:
                out.headers.add('Set-Cookie', extra_set_cookie)
            return out
    except urllib.error.HTTPError as e:
        data = e.read()
        ctype = e.headers.get('Content-Type', 'application/json')
        return Response(data, status=e.code, mimetype=ctype.split(';')[0])
    except Exception as e:
        return Response(
            json.dumps({"status": 502, "data": None, "message": "代理请求失败: " + str(e)}, ensure_ascii=False),
            status=502, mimetype="application/json"
        )

def proxy_api(request, subpath):
    _clean_sessions()
    print(f"[proxy_api] host={request.host} path={request.path} method={request.method} subpath={subpath} sid={request.cookies.get('mcsm_sid') is not None} sec={bool(request.args.get('sec'))} has_X_API_Key={bool(request.headers.get('X-API-Key') or request.args.get('apikey'))}", flush=True)
    sid = request.cookies.get('mcsm_sid')
    if sid and PANEL_SESSIONS.get(sid, 0) > time.time():
        print(f"[proxy_api] auth=session sid={sid[:8]}... OK", flush=True)
        return _forward(request, subpath)
    sec = request.args.get('sec')
    if sec:
        from src.api.mcsm_info import consume_token
        data = consume_token(sec)
        print(f"[MCSM] api sec={sec} db_hit={bool(data)}", flush=True)
        if data:
            new_sid = secrets.token_hex(16)
            PANEL_SESSIONS[new_sid] = time.time() + SESSION_TTL
            cookie = 'mcsm_sid=' + new_sid + '; Path=/; Max-Age=' + str(SESSION_TTL) + '; HttpOnly; SameSite=Lax; Secure'
            return _forward(request, subpath, extra_set_cookie=cookie)
    user, reason = verify_sign(request, debug=True)
    if not user:
        msg = reason or "apikey或签名校验失败"
        print(f"[proxy_api] auth=sign FAIL msg={msg}", flush=True)
        return _deny(msg)
    print(f"[proxy_api] auth=sign OK user={user.get('name')} uid={user.get('id')}", flush=True)
    log_api_call(request, user)
    return _forward(request, subpath)

def proxy_panel(request, subpath):
    _clean_sessions()
    sid = request.cookies.get('mcsm_sid')
    if sid and PANEL_SESSIONS.get(sid, 0) > time.time():
        return _forward(request, subpath)
    sec = request.args.get('sec')
    if sec:
        from src.api.mcsm_info import consume_token
        data = consume_token(sec)
        print(f"[MCSM] sec={sec} db_hit={bool(data)}", flush=True)
        if not data:
            return _deny("令牌无效或已过期")
        host_prefix = (request.host or '').split(':')[0].split('.')[0]
        if not data['panel_host'] or host_prefix != data['panel_host']:
            print(f"[MCSM] host_mismatch req={host_prefix} sec_host={data['panel_host']}", flush=True)
            return _deny("该入口不属于此令牌")
        print(f"[MCSM] auth_ok host={data['panel_host']}", flush=True)
        new_sid = secrets.token_hex(16)
        PANEL_SESSIONS[new_sid] = time.time() + SESSION_TTL
        cookie = 'mcsm_sid=' + new_sid + '; Path=/; Max-Age=' + str(SESSION_TTL) + '; HttpOnly; SameSite=Lax; Secure'
        return _forward(request, subpath, extra_set_cookie=cookie)
    user, reason = verify_sign(request)
    if not user:
        return _deny("")
    host_prefix = (request.host or '').split(':')[0].split('.')[0]
    if not user.get('panel_host') or host_prefix != user['panel_host']:
        return _deny("")
    new_sid = secrets.token_hex(16)
    PANEL_SESSIONS[new_sid] = time.time() + SESSION_TTL
    cookie = 'mcsm_sid=' + new_sid + '; Path=/; Max-Age=' + str(SESSION_TTL) + '; HttpOnly; SameSite=Lax; Secure'
    return _forward(request, subpath, extra_set_cookie=cookie)

def proxy(request, subpath):
    if subpath == 'api' or subpath.startswith('api/'):
        return proxy_api(request, subpath)
    return proxy_panel(request, subpath)
