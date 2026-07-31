import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request
from config import MCSM_CONFIG
from utils.mcsm import proxy

application = Flask(__name__)
app = application

@app.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
def forward_root():
    return proxy(request, '')

@app.route('/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def forward(subpath):
    return proxy(request, subpath)

if __name__ == "__main__":
    port = MCSM_CONFIG.get('proxy_port', 4998)
    print(f"MCSM proxy started on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
