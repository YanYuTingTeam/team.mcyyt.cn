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
    '/api/login', '/api/register',
}

def _is_public(path):
    if path in PUBLIC_PATHS:
        return True
    if path.startswith('/assets/') or path.startswith('/amusource/') or path.startswith('/storage/'):
        return True
    return False

@app.before_request
def security_guard():
    path = request.path or '/'
    banned, btype, exp, seg = check_ban(request, 'any')
    if banned:
        if is_ajax_api(request):
            return json_response("404 page not found", 404)
        return Response(
            f"<html><body style='background:#000;color:#eee;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0'><div style='text-align:center'><h2 style='color:#ef5777'>访问被拒绝</h2><p>{msg}</p></div></body></html>",
            status=404, mimetype='text/html'
        )
    is_logged_in = bool(request.cookies.get('yyt_token') and check_login(request))
    if not is_logged_in and not _is_public(path):
        r_banned, r_type, r_exp = rate_tick(request)
        if r_banned:
            return redirect('/')
        if is_ajax_api(request):
            return json_response("401 auth required", 401)
        if path != '/':
            return redirect('/')

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
    error_trace = traceback.format_exc()
    print(f"--- SERVER ERROR ---\n{error_trace}")
    return json_response({
        "code": 500,
        "message": str(e),
        "debug": {
            "type": e.__class__.__name__,
            "traceback": error_trace.split('\n')
        }
    }, 500)

@app.route('/amusource/img/<uuid>/<filename>')
def serve_image(uuid, filename):
    param = request.args.get('param')
    file_path = os.path.join(STORAGE_PATH, 'img', f"{uuid}_{filename}")
    
    if not os.path.exists(file_path):
        return json_response("404 page not found", 404)

    if param and 'y' in param:
        try:
            w, h = map(int, param.split('y'))
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
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'), filename)

@app.route('/todos/<tid>', methods=['GET'])
def todo_detail_page(tid):
    from utils.page import serve_space
    return serve_space(request)

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
    print("Server started on http://0.0.0.0:4999")
    app.run(host='0.0.0.0', port=4999, debug=False, use_reloader=False)