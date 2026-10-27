-- Zetaris Lightning SQL — run ONE statement per call (JDBC) or paste into the SQL editor.
-- Registers three datasources (shop app DB, payment-provider ledger, mail-provider events) and builds the `order_journey` unified semantic layer over their five tables.
-- Syntax per https://zetaris.github.io/getting-started/docs/guides/zetaris-lightning-sql-commands.html
--
-- Source layout for the local Docker platform: the synthetic CSVs are loaded into three databases on the
-- bundled Postgres (zetaris/load_postgres.sh): `demo` (shop app DB: orders, grants, server_logs), `psp`
-- (payment-provider ledger: payments) and `mailprov` (mail-provider events: mail_events). Zetaris reads them
-- in place over JDBC as three datasources; nothing is copied into Zetaris.

-- 1. datasource (administrator)
CREATE DATASOURCE demo_pg DESCRIBE BY "synthetic_seller_sources" OPTIONS (
  jdbcdriver "org.postgresql.Driver",
  jdbcurl "jdbc:postgresql://postgres:5432/demo",
  username "zetaris",
  password "${POSTGRES_PASSWORD}",
  fetchsize "1000"
);

REGISTER DATASOURCE TABLES FROM demo_pg;

-- the payment provider's ledger and the mail provider's events are separate systems: separate datasources
CREATE DATASOURCE psp_pg DESCRIBE BY "payment_provider_ledger" OPTIONS (
  jdbcdriver "org.postgresql.Driver",
  jdbcurl "jdbc:postgresql://postgres:5432/psp",
  username "zetaris",
  password "${POSTGRES_PASSWORD}",
  fetchsize "1000"
);

REGISTER DATASOURCE TABLES FROM psp_pg;

CREATE DATASOURCE mail_pg DESCRIBE BY "mail_provider_events" OPTIONS (
  jdbcdriver "org.postgresql.Driver",
  jdbcurl "jdbc:postgresql://postgres:5432/mailprov",
  username "zetaris",
  password "${POSTGRES_PASSWORD}",
  fetchsize "1000"
);

REGISTER DATASOURCE TABLES FROM mail_pg;

-- 2. namespace + semantic layer (send the whole COMPILE statement in one piece)
CREATE NAMESPACE IF NOT EXISTS lightning.metastore.demo;

COMPILE USL order_journey DEPLOY NAMESPACE lightning.metastore.demo DDL
CREATE TABLE orders (
  order_id varchar(32) NOT NULL PRIMARY KEY,
  payment_id varchar(32),
  email varchar(200),
  reward_key varchar(32),
  amount varchar(16),
  status varchar(16),
  credited varchar(4),
  created_at varchar(32),
  updated_at varchar(32)
);
CREATE TABLE payments (
  payment_id varchar(32) NOT NULL PRIMARY KEY,
  amount varchar(16),
  currency varchar(8),
  status varchar(16),
  card_last4 varchar(4),
  customer_email varchar(200),
  created_at varchar(32)
);
CREATE TABLE grants (
  grant_id varchar(48) NOT NULL PRIMARY KEY,
  email varchar(200),
  reward_key varchar(32),
  credits varchar(8),
  status varchar(16),
  order_id varchar(32) FOREIGN KEY REFERENCES orders(order_id),
  created_at varchar(32)
);
CREATE TABLE server_logs (
  ts varchar(32) NOT NULL PRIMARY KEY,
  route varchar(64),
  order_id varchar(32) FOREIGN KEY REFERENCES orders(order_id),
  http_status varchar(4),
  message varchar(200)
);
CREATE TABLE mail_events (
  email_id varchar(48) NOT NULL PRIMARY KEY,
  to_address varchar(200),
  event varchar(16),
  ts varchar(32),
  order_tag varchar(32) FOREIGN KEY REFERENCES orders(order_id)
)

-- 3. activate each table from the registered source
ACTIVATE USL TABLE lightning.metastore.demo.order_journey.orders AS SELECT COALESCE(order_id,'') AS order_id, payment_id, email, reward_key, amount, status, credited, created_at, updated_at FROM demo_pg.orders;
ACTIVATE USL TABLE lightning.metastore.demo.order_journey.payments AS SELECT COALESCE(payment_id,'') AS payment_id, amount, currency, status, card_last4, customer_email, created_at FROM psp_pg.payments;
ACTIVATE USL TABLE lightning.metastore.demo.order_journey.grants AS SELECT COALESCE(grant_id,'') AS grant_id, email, reward_key, credits, status, order_id, created_at FROM demo_pg.grants;
ACTIVATE USL TABLE lightning.metastore.demo.order_journey.server_logs AS SELECT COALESCE(ts,'') AS ts, route, order_id, http_status, message FROM demo_pg.server_logs;
ACTIVATE USL TABLE lightning.metastore.demo.order_journey.mail_events AS SELECT COALESCE(email_id,'') AS email_id, to_address, event, ts, order_tag FROM mail_pg.mail_events;

-- 4. smoke test: the journey join the agent sends (agent/tools.py order_journey, which selects every column with
--    aliases; the agent sets ZETARIS_SCHEMA=lightning.metastore.demo.order_journey). Five tables, three datasources.
SELECT o.order_id, o.email AS order_email, p.customer_email AS payer, p.status AS psp_status,
       g.grant_id, l.route, l.http_status, m.event AS mail_event
FROM lightning.metastore.demo.order_journey.orders o
LEFT JOIN lightning.metastore.demo.order_journey.payments p ON p.payment_id = o.payment_id
LEFT JOIN lightning.metastore.demo.order_journey.grants g ON g.order_id = o.order_id
LEFT JOIN lightning.metastore.demo.order_journey.server_logs l ON l.order_id = o.order_id
LEFT JOIN lightning.metastore.demo.order_journey.mail_events m ON m.order_tag = o.order_id
WHERE o.order_id = 'ord_0906';
