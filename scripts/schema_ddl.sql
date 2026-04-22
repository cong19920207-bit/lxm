-- 林小梦项目 MySQL 建表 DDL（由 SQLAlchemy 模型生成）


CREATE TABLE admin_config (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	config_key VARCHAR(100) NOT NULL, 
	config_value TEXT, 
	version INTEGER NOT NULL, 
	is_active BOOL NOT NULL, 
	is_draft BOOL NOT NULL, 
	updated_by VARCHAR(50), 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)

;

-- config_key 仅非唯一索引：同一 key 允许多行（草稿 + 生效 + 历史），勿建 UNIQUE(config_key)
CREATE INDEX ix_admin_config_config_key ON admin_config (config_key);


CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(20) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_login_at DATETIME, 
	relationship_level INTEGER NOT NULL, 
	growth_value INTEGER NOT NULL, 
	is_banned BOOL NOT NULL, 
	login_fail_count INTEGER NOT NULL, 
	locked_until DATETIME, 
	PRIMARY KEY (id)
)

;


CREATE TABLE agent_message (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	trigger_type VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	action_score FLOAT NOT NULL, 
	is_read BOOL NOT NULL, 
	sort_seq BIGINT NOT NULL DEFAULT 0, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_agent_message_sort_seq ON agent_message (sort_seq);



CREATE TABLE ai_diary (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	relationship_level_at_creation INTEGER NOT NULL, 
	is_read BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE conversation_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	content TEXT NOT NULL, 
	emotion_label VARCHAR(50), 
	emotion_confidence FLOAT, 
	memory_injected JSON, 
	persona_risk_flag BOOL NOT NULL, 
	persona_risk_type VARCHAR(50), 
	sort_seq BIGINT NOT NULL DEFAULT 0, 
	delivery_status VARCHAR(32), 
	skipped_in_prompt BOOL NOT NULL DEFAULT 0, 
	round_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_conversation_log_sort_seq ON conversation_log (sort_seq);



CREATE TABLE login_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	login_at DATETIME NOT NULL, 
	time_period VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE memory (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	importance_score FLOAT NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	dashvector_id VARCHAR(100), 
	is_deleted BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	expires_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE relationship (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	level INTEGER NOT NULL, 
	growth_value INTEGER NOT NULL, 
	last_interaction_at DATETIME, 
	consecutive_login_days INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE world_state (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	trigger_conversation_id INTEGER, 
	relevance_weight FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE emotion_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	emotion_label VARCHAR(50) NOT NULL, 
	confidence FLOAT NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	round_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES conversation_log (id) ON DELETE CASCADE
)

;


CREATE TABLE user_short_term_emotion (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	emotion_label VARCHAR(50) NOT NULL,
	confidence FLOAT NOT NULL,
	payload TEXT,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE user_timeline_seq (
	user_id INTEGER NOT NULL, 
	next_seq BIGINT NOT NULL DEFAULT 1, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

