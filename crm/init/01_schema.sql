-- Замена CRM DB Битрикс24 (в проде - Oracle) для локальной разработки.
-- Хранит записи о клиентах, с которыми ETL отчётности объединяет
-- телеметрию протезов.
CREATE TABLE customers (
    customer_id   VARCHAR(64) PRIMARY KEY,   -- совпадает с именем пользователя в Keycloak
    full_name     VARCHAR(255) NOT NULL,
    region        VARCHAR(128) NOT NULL,
    prosthesis_model VARCHAR(128) NOT NULL,
    signup_date   DATE NOT NULL
);

INSERT INTO customers (customer_id, full_name, region, prosthesis_model, signup_date) VALUES
    ('user1', 'User One', 'Moscow', 'BionicPRO Hand X1', '2025-01-15'),
    ('user2', 'User Two', 'Saint Petersburg', 'BionicPRO Hand X1', '2025-02-20'),
    ('prothetic1', 'Prothetic One', 'Kazan', 'BionicPRO Hand X2', '2025-03-05'),
    ('prothetic2', 'Prothetic Two', 'Novosibirsk', 'BionicPRO Leg L1', '2025-03-18'),
    ('prothetic3', 'Prothetic Three', 'Yekaterinburg', 'BionicPRO Hand X2', '2025-04-02'),
    ('john.doe', 'John Doe', 'Berlin (representative office)', 'BionicPRO Hand X1', '2025-05-10'),
    ('jane.smith', 'Jane Smith', 'Berlin (representative office)', 'BionicPRO Leg L1', '2025-05-22');
