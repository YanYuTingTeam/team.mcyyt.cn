import time
import secrets
from utils.auth import check_login
from config import MCSM_CONFIG

_MCSM_TOKENS = {}
_TOKEN_TTL = 30

def issue_token(user):
    token = secrets.token_hex(24)
    _MCSM_TOKENS[token] = {
        'user_id': user['id'],
        'apikey': user.get('apikey'),
        'panel_host': user.get('panel_host'),
        'expire': time.time() + _TOKEN_TTL
    }
    _clean_tokens()
    return token

def consume_token(token):
    data = _MCSM_TOKENS.pop(token, None)
    if not data or data['expire'] < time.time():
        return None
    return data

def _clean_tokens():
    now = time.time()
    for k in [k for k, v in _MCSM_TOKENS.items() if v['expire'] < now]:
        _MCSM_TOKENS.pop(k, None)

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    token = issue_token(user)
    return {"code": 0, "data": {
        "panel_suffix": MCSM_CONFIG.get('panel_suffix', ''),
        "panel_host": user.get('panel_host'),
        "token": token,
        "is_admin": (user.get('level') or 0) >= 1
    }}
