CREATE TABLE IF NOT EXISTS yyt_user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    name VARCHAR(64) NOT NULL,
    role VARCHAR(64) DEFAULT NULL,
    level INT DEFAULT 0,
    skill VARCHAR(255) DEFAULT NULL,
    apikey VARCHAR(64) DEFAULT NULL,
    panel_host VARCHAR(16) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_session (
    id INT AUTO_INCREMENT UNIQUE,
    token CHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    ip VARCHAR(64) DEFAULT NULL,
    ua VARCHAR(255) DEFAULT NULL,
    expire_time DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_invite (
    code VARCHAR(32) PRIMARY KEY,
    created_by INT DEFAULT NULL,
    used_by INT DEFAULT NULL,
    used_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_api_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ip VARCHAR(64) DEFAULT NULL,
    path VARCHAR(128) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_todo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    creator_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    link VARCHAR(255) DEFAULT NULL,
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_creator (creator_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_todo_assign (
    id INT AUTO_INCREMENT PRIMARY KEY,
    todo_id INT NOT NULL,
    user_id INT NOT NULL,
    is_done TINYINT DEFAULT 0,
    done_at DATETIME DEFAULT NULL,
    KEY idx_todo (todo_id),
    KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_notice (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_project (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    info VARCHAR(500) DEFAULT NULL,
    link VARCHAR(255) DEFAULT NULL,
    members VARCHAR(255) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_page_access (
    page_key VARCHAR(32) PRIMARY KEY,
    min_level INT DEFAULT 1,
    show_in_nav TINYINT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_visit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT NULL,
    ip VARCHAR(64) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_time (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO yyt_page_access (page_key, min_level, show_in_nav) VALUES
    ('home', 0, 1), ('overview', 0, 1), ('todo', 1, 1), ('notice', 1, 1),
    ('project', 1, 1), ('apis', 1, 1), ('mcsm', 4, 1), ('team', 5, 1)
ON DUPLICATE KEY UPDATE page_key = page_key;

INSERT INTO yyt_invite (code) VALUES ('YYT-WELCOME-001');
