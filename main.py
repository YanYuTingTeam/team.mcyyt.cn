import importlib
import os
import sys
import threading
import traceback
import json
import time
import mimetypes
from datetime import datetime, date
from flask import Flask, request, Response, send_from_directory, send_file, redirect
from io import BytesIO
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.security import (
    check_ban, rate_tick, is_ajax_api, check_auth_ban
)
from utils.auth import check_login
from utils.db import get_db
import traceback as _tb

application = Flask(__name__)
app = application

STORAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage')
import_lock = threading.Lock()

PUBLIC_PATHS = {
    '/', '/login', '/register', '/space.html', '/login.html',
    '/api/login', '/api/register', '/api/send_email_code', '/api/heartbeat',
    '/public/datatools',
}

PROTECTED_ASSETS = {'/assets/space_ui.html', '/assets/app.js'}

def _is_public(path):
    if path in PUBLIC_PATHS:
        return True
    if path in PROTECTED_ASSETS:
        return False
    if path.startswith('/assets/') or path.startswith('/amusource/') or path.startswith('/storage/'):
        return True
    return False

@app.before_request
def security_guard():
    path = request.path or '/'
    is_logged_in = bool(request.cookies.get('yyt_token') and check_login(request))
    if not is_logged_in:
        banned, btype, exp, seg = check_ban(request, 'auth')
        if not banned:
            banned, btype, exp, seg = check_ban(request, 'rate')
        if banned:
            return json_response("404 page not found", 404)
        if not _is_public(path):
            r_banned, r_type, r_exp = rate_tick(request)
            if r_banned:
                return json_response("404 page not found", 404)
            if is_ajax_api(request):
                return json_response("401 auth required", 401)
            if path != '/':
                return redirect('/')
    else:
        # 已登录用户：仅对 send_email_code 检查 email ban（邮件滥用防护）
        if path == '/api/send_email_code':
            banned, btype, exp, _ = check_ban(request, 'email')
            if banned:
                return json_response({"code": 429, "message": "请求过于频繁, 请稍后再试"}, 429)

@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "media-src 'self' https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://*.mcsm.mcyyt.cn; "
        "frame-src 'self' https://*.mcsm.mcyyt.cn"
    )
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Server'] = 'yyt'
    return response

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

def json_response(data, status=200):
    if isinstance(data, (dict, list)):
        body = json.dumps(data, cls=EnhancedJSONEncoder, ensure_ascii=False)
    else:
        body = data

    return Response(
        body,
        mimetype="application/json",
        status=status
    )

@app.errorhandler(Exception)
def handle_exception(e):
    print(e)
    # 生产环境只返回通用错误信息，防止信息泄露
    return json_response({
        "code": 500,
        "message": "服务器内部错误"
    }, 500)

@app.route('/amusource/img/<uuid>/<filename>')
def serve_image(uuid, filename):
    param = request.args.get('param')
    if os.path.basename(filename) != filename or '..' in filename or '\\' in filename:
        return json_response("404 page not found", 404)
    file_path = os.path.join(STORAGE_PATH, 'img', f"{uuid}_{filename}")

    if not os.path.exists(file_path):
        return json_response("404 page not found", 404)

    if param and 'y' in param:
        try:
            w, h = map(int, param.split('y'))
            # 限制宽高范围，防止资源耗尽攻击 (DoS)
            w = max(1, min(w, 2048))
            h = max(1, min(h, 2048))
            img = Image.open(file_path)
            img = img.resize((w, h), Image.Resampling.LANCZOS)
            img_io = BytesIO()
            img.convert('RGB').save(img_io, 'JPEG', quality=85)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')
        except Exception:
            pass

    return send_from_directory(os.path.join(STORAGE_PATH, 'img'), f"{uuid}_{filename}")

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    if filename in ('space_ui.html', 'app.js'):
        return Response('404', status=404, mimetype='text/plain')
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'), filename)

@app.route('/todos/<tid>', methods=['GET'])
def todo_detail_page(tid):
    from utils.page import serve_space
    return serve_space(request)

@app.route('/todos/tag/<tid>', methods=['GET'])
def todo_tag_page(tid):
    from utils.page import serve_space
    return serve_space(request)

@app.route('/public/datatools')
def public_datatools():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pages', 'datatools_public.html')
    with open(path, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html; charset=utf-8')

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        full_module = 'index'
        with import_lock:
            sys.modules.pop(full_module, None)
            module = importlib.import_module(full_module)
        if not hasattr(module, 'handle'):
            return json_response("404 page not found", 404)
        
        result = module.handle(request)
        if isinstance(result, (dict, list)):
            return json_response(result)
        return result

    except ModuleNotFoundError as e:
        print(e)
        return json_response("404 page not found", 404)
    except Exception as e:
        print(e)
        raise e

@app.route('/<path:path>', methods=['GET', 'POST'])
def src_router(path):
    try:
        parts = path.strip('/').split('/')
        module_path = '.'.join(parts)
        
        if parts[0] == 'storage':
            return json_response("404 page not found", 404)

        # 动态import route
        full_module = f"src.{module_path}"
        module_parts = full_module.split('.')
        with import_lock:
            for i in range(len(module_parts), 0, -1):
                temp_mod = '.'.join(module_parts[:i])
                if temp_mod in sys.modules:
                    del sys.modules[temp_mod]
            module = importlib.import_module(full_module)
        if not hasattr(module, 'handle'):
            return json_response("404 page not found", 404)
        
        result = module.handle(request)
        if isinstance(result, (dict, list)):
            return json_response(result)
        return result

    except ModuleNotFoundError as e:
        print(e)
        return json_response("404 page not found", 404)
    except Exception as e:
        print(e)
        raise e

@app.errorhandler(404)
def page_not_found(e):
    print(e)
    return json_response("404 page not found", 404)

if __name__ == "__main__":
    print("Server started on http://127.0.0.1:4999")
    app.run(host='127.0.0.1', port=4999, debug=False, use_reloader=False)