import os

DB_CONFIG = {
    "host": os.environ.get('DB_HOST', 'localhost'),
    "user": os.environ.get('DB_USERNAME', ''),
    "password": os.environ.get('DB_PASSWORD', ''),
    "database": os.environ.get('DB_DATABASE', ''),
    "charset": os.environ.get('DB_CHARSET', 'utf8mb4')
}

MCSM_CONFIG = {
    "base": os.environ.get('MCSM_BASE', 'http://localhost:23333'),
    "apikey": os.environ.get('MCSM_APIKEY', ''),
    "proxy_port": os.environ.get('MCSM_PROXY_PORT', '8185'),
    "salt": os.environ.get('MCSM_SALT', ''),
    "panel_suffix": os.environ.get('MCSM_PANEL_BASEURL', 'mcsm.mcyyt.cn'),
    "sign_window": 300
}

SMTP_CONFIG = {
    "host": os.environ.get('SMTP_HOST', 'smtp.feishu.cn'),
    "port": os.environ.get('SMTP_PORT', 465),
    "user": os.environ.get('SMTP_USER', ''),
    "password": os.environ.get('SMTP_PASSWORD', ''),
    "from_name": os.environ.get('SMTP_FROM_NAME', '@team'),
    "from_addr": os.environ.get('SMTP_FROM_ADDR', '')
}

CCW_CONFIG = {
    "token": os.environ.get('CCW_TOKEN', ''),
    "user_id": os.environ.get('CCW_USER_ID', ''),
    "default_prefix": os.environ.get('CCW_DEFAULT_PREFIX', 'uploads')
}
