CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE crm_users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id TEXT UNIQUE NOT NULL,
    full_name   TEXT NOT NULL
);

CREATE TABLE crm_prostheses (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES crm_users(id),
    serial_number TEXT NOT NULL
);

-- seed users
INSERT INTO crm_users (id, external_id, full_name) VALUES
  ('2661e18f-5fa2-45f5-9aa6-d25548783904', 'jane.smith', 'Jane Smith'),
  ('470d4af0-7e11-4270-a8e7-5b2999058c84', 'john.doe', 'John Doe');

-- seed prostheses (по два на пользователя)
INSERT INTO crm_prostheses (id, user_id, serial_number) VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2661e18f-5fa2-45f5-9aa6-d25548783904', 'P-USER1-001'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2661e18f-5fa2-45f5-9aa6-d25548783904', 'P-USER1-002'),
  ('cccccccc-cccc-cccc-cccc-cccccccccccc', '470d4af0-7e11-4270-a8e7-5b2999058c84', 'P-USER2-001'),
  ('dddddddd-dddd-dddd-dddd-dddddddddddd', '470d4af0-7e11-4270-a8e7-5b2999058c84', 'P-USER2-002');
