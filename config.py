import os

# 密钥一律从环境变量读取, 需配置: YYT_DB_PASSWORD / YYT_MCSM_APIKEY / YYT_MCSM_SALT / YYT_SMTP_PASSWORD / YYT_CCW_TOKEN
DB_CONFIG = {
    "host": "localhost",
    "user": "",
    "password": os.environ.get('YYT_DB_PASSWORD', ''),
    "database": "",
    "charset": "utf8mb4"
}

MCSM_CONFIG = {
    "base": "http://localhost:23333",
    "apikey": os.environ.get('YYT_MCSM_APIKEY', ''),
    "proxy_port": 8185,
    "salt": os.environ.get('YYT_MCSM_SALT', ''),
    "panel_suffix": "mcsm.mcyyt.cn",
    "sign_window": 300
}

SMTP_CONFIG = {
    "host": "smtp.feishu.cn",
    "port": 465,
    "user": "team@mcyyt.cn",
    "password": os.environ.get('YYT_SMTP_PASSWORD', ''),
    "from_name": "@team / YanYuTing",
    "from_addr": "team@mcyyt.cn"
}

CCW_CONFIG = {
    "token": os.environ.get('YYT_CCW_TOKEN', ''),
    "user_id": "",
    "default_prefix": "uploads"
}
