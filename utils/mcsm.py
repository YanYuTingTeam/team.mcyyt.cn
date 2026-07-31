import json
import time
import secrets
import urllib.request
import urllib.error
from flask import Response
from config import MCSM_CONFIG
from utils.auth import verify_sign, log_api_call

PANEL_SESSIONS = {}
SESSION_TTL = 6 * 3600
SKIP_REQ_HEADERS = {'host', 'a', 'b', 'x-api-key', 'content-length', 'connection'}

def _deny(msg):
    return Response(
        #json.dumps({"status": 403, "data": None, "message": msg}, ensure_ascii=False),
        #status=403, mimetype="application/json"
    )

def _clean_sessions():
    now = time.time()
    for sid in [k for k, v in PANEL_SESSIONS.items() if v < now]:
        PANEL_SESSIONS.pop(sid, None)

def _forward(request, subpath, extra_set_cookie=None):
    base = MCSM_CONFIG['base'].rstrip('/')
    target = base + '/' + subpath
    if request.query_string:
        target += '?' + request.query_string.decode('utf-8', 'ignore')
    body = request.get_data() if request.method in ('POST', 'PUT', 'DELETE') else None
    req = urllib.request.Request(target, data=body, method=request.method)
    for k, v in request.headers.items():
        if k.lower() in SKIP_REQ_HEADERS:
            continue
        req.add_header(k, v)
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
        return Response(e.read(), status=e.code, mimetype="application/json")
    except Exception as e:
        return Response(
            #json.dumps({"status": 502, "data": None, "message": "代理请求失败: " + str(e)}, ensure_ascii=False),
            #status=502, mimetype="application/json"
        )

def proxy_api(request, subpath):
    user = verify_sign(request)
    if not user:
        return _deny("签名无效、已过期或权限不足")
    log_api_call(request, user)
    return _forward(request, subpath)

def proxy_panel(request, subpath):
    _clean_sessions()
    sid = request.cookies.get('mcsm_sid')
    if sid and PANEL_SESSIONS.get(sid, 0) > time.time():
        return _forward(request, subpath)
    user = verify_sign(request)
    if not user:
        return _deny("签名无效、已过期或权限不足")
    host_prefix = (request.host or '').split(':')[0].split('.')[0]
    if not user.get('panel_host') or host_prefix != user['panel_host']:
        return _deny("该入口不属于此 apikey")
    new_sid = secrets.token_hex(16)
    PANEL_SESSIONS[new_sid] = time.time() + SESSION_TTL
    cookie = 'mcsm_sid=' + new_sid + '; Path=/; Max-Age=' + str(SESSION_TTL) + '; HttpOnly; SameSite=Lax; Secure'
    return _forward(request, subpath, extra_set_cookie=cookie)

def proxy(request, subpath):
    if subpath == 'api' or subpath.startswith('api/'):
        return proxy_api(request, subpath)
    return proxy_panel(request, subpath)
