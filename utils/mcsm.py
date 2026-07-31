import json
import urllib.request
import urllib.error
from urllib.parse import urlencode
from flask import Response
from config import MCSM_CONFIG
from utils.auth import check_apikey

def proxy(request, subpath):
    user = check_apikey(request)
    if not user:
        return Response(
            json.dumps({"status": 403, "data": None, "message": "apikey 无效或未提供"}, ensure_ascii=False),
            status=403, mimetype="application/json"
        )
    real_key = MCSM_CONFIG.get('apikey') or ''
    args = {k: v for k, v in request.args.items() if k != 'apikey'}
    args['apikey'] = real_key
    target = MCSM_CONFIG['base'].rstrip('/') + '/' + subpath + '?' + urlencode(args)

    body = request.get_data() if request.method in ('POST', 'PUT', 'DELETE') else None
    req = urllib.request.Request(target, data=body, method=request.method)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            ctype = resp.headers.get('Content-Type', 'application/json')
            return Response(data, status=resp.status, mimetype=ctype.split(';')[0])
    except urllib.error.HTTPError as e:
        return Response(e.read(), status=e.code, mimetype="application/json")
    except Exception as e:
        return Response(
            json.dumps({"status": 500, "data": None, "message": "代理请求失败: " + str(e)}, ensure_ascii=False),
            status=502, mimetype="application/json"
        )
