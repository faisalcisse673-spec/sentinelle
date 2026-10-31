#!/bin/sh
# Cree les bases de Synapse (collation C obligatoire) et de Keycloak.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOSQL
CREATE USER synapse WITH PASSWORD '${SYNAPSE_DB_PASSWORD}';
CREATE DATABASE synapse WITH OWNER synapse ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C' TEMPLATE template0;
CREATE USER keycloak WITH PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE DATABASE keycloak WITH OWNER keycloak ENCODING 'UTF8';
EOSQL
