import os
from flask import Response, redirect
from utils.auth import check_login

def serve_space(request):
    if not check_login(request):
        return redirect('/')
    page_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pages', 'space.html')
    with open(page_path, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html')
