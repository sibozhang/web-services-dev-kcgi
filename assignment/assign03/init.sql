CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    phone VARCHAR(20)
);

INSERT INTO users (name, email, phone) VALUES ('Admin Bot', 'admin@kcg.edu', '090-0000-0000');