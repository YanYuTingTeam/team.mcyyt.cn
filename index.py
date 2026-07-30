import os
from flask import Response
from utils.auth import check_login

def handle(request):
    user = check_login(request)
    page_name = 'space.html' if user else 'login.html'
    page_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pages', page_name)
    with open(page_path, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html')
