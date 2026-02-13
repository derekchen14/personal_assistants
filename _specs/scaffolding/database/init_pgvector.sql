-- Initial "migration" to enable vector extension. Only relevant when running pgvector with docker


CREATE USER local_user WITH ENCRYPTED PASSWORD 'secret_postgres_password';

CREATE DATABASE soleda_db;

GRANT ALL PRIVILEGES ON DATABASE soleda_db TO local_user;

\c soleda_db
CREATE EXTENSION vector;
GRANT ALL ON SCHEMA public TO local_user;
