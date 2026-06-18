CREATE TABLE IF NOT EXISTS users (
    id       SERIAL PRIMARY KEY,
    name     VARCHAR(100) NOT NULL,
    email    VARCHAR(120) NOT NULL UNIQUE,
    phone    VARCHAR(20),
    password VARCHAR(100) NOT NULL,
    role     VARCHAR(20)  NOT NULL DEFAULT 'viewer'
);

INSERT INTO users (name, email, phone, password, role) VALUES ('Admin Bot', 'admin@kcg.edu', '090-0000-0000', '12345678', 'admin');