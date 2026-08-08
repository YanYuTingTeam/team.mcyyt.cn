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
    avatar VARCHAR(512) DEFAULT NULL,
    bio TEXT DEFAULT NULL,
    track_todo_id INT DEFAULT NULL,
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=正常 2=封禁 3=已注销',
    banned_until DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS yyt_datacollection (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dtype VARCHAR(16) NOT NULL DEFAULT 'survey' COMMENT 'survey=问卷  quiz=测验  doc=文档',
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    is_public TINYINT NOT NULL DEFAULT 1 COMMENT '0=私有 1=团队内共享 2=公开',
    view_count INT NOT NULL DEFAULT 0,
    submit_count INT NOT NULL DEFAULT 0,
    creator_id INT NOT NULL,
    updated_by_id INT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_creator (creator_id),
    KEY idx_public (is_public),
    KEY idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
