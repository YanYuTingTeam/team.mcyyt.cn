from utils.auth import check_login
from config import MCSM_CONFIG

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    return {"code": 0, "data": {
        "panel_suffix": MCSM_CONFIG.get('panel_suffix', ''),
        "panel_host": user.get('panel_host'),
        "salt": MCSM_CONFIG.get('salt', ''),
        "apikey": user.get('apikey'),
        "is_admin": (user.get('level') or 0) >= 1
    }}
