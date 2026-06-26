CREATE TABLE IF NOT EXISTS crm_users (
                                         user_id SERIAL PRIMARY KEY,
                                         username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    full_name VARCHAR(150)
    );

INSERT INTO crm_users (username, email, full_name) VALUES
                                                       ('john.doe', 'john@example.com', 'John Doe'),
                                                       ('jane.smith', 'jane@example.com', 'Jane Smith'),
                                                       ('alex.johnson', 'alex@example.com', 'Alex Johnson');