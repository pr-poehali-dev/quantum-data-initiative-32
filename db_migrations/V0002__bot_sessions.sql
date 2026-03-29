CREATE TABLE IF NOT EXISTS bot_sessions (
    chat_id VARCHAR(50) PRIMARY KEY,
    state VARCHAR(50) DEFAULT 'start',
    data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);