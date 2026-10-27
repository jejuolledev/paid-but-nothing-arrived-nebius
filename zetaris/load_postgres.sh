#!/usr/bin/env bash
# Load the synthetic CSVs into a `demo` database on the Zetaris bundle's Postgres so that
# Zetaris can register them as a JDBC datasource (the local platform reads files only from S3).
# Usage: ZETARIS_BUNDLE=../zetaris-platform ./zetaris/load_postgres.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE="${ZETARIS_BUNDLE:-$HERE/../zetaris-platform}"
DATA="$HERE/data/out"
cd "$BUNDLE"
PG="docker compose exec -T postgres psql -U zetaris -v ON_ERROR_STOP=1"
# Three separate databases stand in for three separate systems, each registered in Zetaris as its own datasource:
#   demo     — the shop's app database (orders, credit grants, server-log export)
#   psp      — the payment provider's ledger export
#   mailprov — the mail provider's event export
for db in demo psp mailprov; do
  $PG -d metastore -tc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 || $PG -d metastore -c "CREATE DATABASE $db"
done
$PG -d demo <<'SQL'
DROP TABLE IF EXISTS payments, orders, grants, server_logs, mail_events;
CREATE TABLE orders (order_id text, payment_id text, email text, reward_key text, amount text, status text, credited text, created_at text, updated_at text);
CREATE TABLE grants (grant_id text, email text, reward_key text, credits text, status text, order_id text, created_at text);
CREATE TABLE server_logs (ts text, route text, order_id text, http_status text, message text);
SQL
$PG -d psp <<'SQL'
DROP TABLE IF EXISTS payments;
CREATE TABLE payments (payment_id text, amount text, currency text, status text, card_last4 text, customer_email text, created_at text);
SQL
$PG -d mailprov <<'SQL'
DROP TABLE IF EXISTS mail_events;
CREATE TABLE mail_events (email_id text, to_address text, event text, ts text, order_tag text);
SQL
load() { docker compose exec -T postgres psql -U zetaris -d "$1" -c "\\copy $2 FROM STDIN WITH (FORMAT csv, HEADER true)" < "$DATA/$2.csv"; }
for t in orders grants server_logs; do load demo $t; done
load psp payments
load mailprov mail_events
$PG -d demo -c "SELECT (SELECT count(*) FROM orders) orders, (SELECT count(*) FROM grants) grants, (SELECT count(*) FROM server_logs) server_logs"
$PG -d psp -c "SELECT count(*) payments FROM payments"
$PG -d mailprov -c "SELECT count(*) mail_events FROM mail_events"
