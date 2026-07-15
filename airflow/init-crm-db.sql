CREATE TABLE IF NOT EXISTS user_prostheses
(
    user_id           varchar(255),
    prosthesis_serial varchar(255),
    CONSTRAINT user_prostheses_pk PRIMARY KEY (user_id, prosthesis_serial)
);

INSERT INTO user_prostheses (user_id, prosthesis_serial)
VALUES ('user1', '05d488c1-da0f-4955-8c1e-07633b524464'),
       ('user1', '4b7d0b00-7ccc-44d2-815c-1a23e6f3ae9e'),
       ('user2', 'cf7ef2c3-fa64-47b5-809d-727dcdf28fa9');

ALTER TABLE user_prostheses
    REPLICA IDENTITY FULL;

CREATE USER debezium_user WITH REPLICATION ENCRYPTED PASSWORD 'dbz_secret';
CREATE PUBLICATION dbz_publication FOR TABLE user_prostheses;
GRANT SELECT ON TABLE user_prostheses TO debezium_user;
