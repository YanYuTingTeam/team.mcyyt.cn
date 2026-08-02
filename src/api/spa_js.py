import os
from flask import Response
from utils.auth import check_login

_js_cache = {'mtime': 0, 'content': ''}


def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'app.js')
    mtime = os.path.getmtime(path)
    if _js_cache['mtime'] == mtime and _js_cache['content']:
        content = _js_cache['content']
    else:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        _js_cache['mtime'] = mtime
        _js_cache['content'] = content
    return Response(content, mimetype='application/javascript')
