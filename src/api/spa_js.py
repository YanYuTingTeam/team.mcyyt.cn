import os
from flask import Response
from utils.auth import check_login

_KICK_PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'pages', 'bye.html')
_BANNED_PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'pages', 'banned.html')

def handle(request):
    user = check_login(request)
    if not user:
        if request.cookies.get('yyt_token'):
            with open(_BANNED_PAGE, 'r', encoding='utf-8') as f:
                return Response(f.read(), mimetype='text/html')
        return Response('', status=401)
    kick = user.get('_kick_reason', False)
    if kick:
        with open(_KICK_PAGE, 'r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='text/html')
    with open(_BANNED_PAGE, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html')
