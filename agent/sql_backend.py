"""One SQL door for the agent.

The agent never touches a payment API, a database driver or a log file directly.
It asks a single SQL endpoint. In production that endpoint is Zetaris, which federates
the four sources without moving the data. For offline development and tests the same
queries run against the synthetic CSVs through DuckDB with identical table names.

  ZETARIS_JDBC_URL + ZETARIS_JDBC_JAR  -> ZetarisJDBCBackend (bundled Lightning driver)
  ZETARIS_SQL_URL / ZETARIS_API_KEY    -> ZetarisBackend (REST SQL)
  otherwise                            -> DuckDBBackend (local CSV, tests)
"""
from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import Any

TABLES = ["payments", "orders", "grants", "server_logs", "mail_events"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "out"


class DuckDBBackend:
    name = "duckdb-local"

    def __init__(self, data_dir: Path = DATA_DIR):
        import duckdb  # local import keeps the Zetaris path dependency-free
        self.con = duckdb.connect(database=":memory:")
        self.lock = threading.RLock()  # one connection, many request threads
        for t in TABLES:
            p = data_dir / f"{t}.csv"
            if not p.exists():
                raise FileNotFoundError(f"{p} missing — run `python data/gen_synthetic.py` first")
            cols = 'email_id, "to" AS to_address, event, ts, order_tag' if t == "mail_events" else "*"
            # TABLE (not VIEW) so approved fixes can write rows; CSVs stay the seed.
            self.con.execute(f"CREATE TABLE {t} AS SELECT {cols} FROM read_csv_auto('{p}', header=true, all_varchar=true)")
        self.con.execute(
            "CREATE TABLE actions (action_id VARCHAR, order_id VARCHAR, kind VARCHAR, "
            "detail VARCHAR, approved_by VARCHAR, ts VARCHAR)"
        )

    def query(self, sql: str) -> list[dict[str, Any]]:
        with self.lock:
            cur = self.con.execute(sql)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def execute(self, sql: str) -> None:
        """Run a write statement (INSERT / UPDATE). Offline demo only."""
        with self.lock:
            self.con.execute(sql)


class ZetarisBackend:
    """Minimal REST client. The exact path/payload is confirmed against the Zetaris
    OpenAPI spec of the supplied instance (see docs/HANDOVER.md, step Z-1)."""
    name = "zetaris"

    def __init__(self, url: str, api_key: str, schema: str = ""):
        import httpx
        self.url, self.schema = url.rstrip("/"), schema
        self.http = httpx.Client(timeout=60, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})

    def query(self, sql: str) -> list[dict[str, Any]]:
        if self.schema:
            for t in TABLES:
                sql = sql.replace(f" {t} ", f" {self.schema}.{t} ").replace(f" {t}\n", f" {self.schema}.{t}\n")
        r = self.http.post(f"{self.url}/sql", json={"sql": sql})
        r.raise_for_status()
        body = r.json()
        rows = body.get("rows") or body.get("data") or body
        cols = body.get("columns")
        if cols and rows and isinstance(rows[0], list):
            return [dict(zip(cols, row)) for row in rows]
        return rows


class ZetarisJDBCBackend:
    """Official path for the local Zetaris platform: the bundled Lightning JDBC driver
    (jdbc:zetaris:lightning@localhost:10000), one statement per call."""
    name = "zetaris-jdbc"

    def __init__(self, jdbc_url: str, user: str, password: str, jar: str, schema: str = ""):
        import jaydebeapi
        self.con = jaydebeapi.connect("com.zetaris.lightning.jdbc.LightningDriver", jdbc_url, [user, password], jar)
        self.schema = schema
        self._lock = threading.RLock()

    def query(self, sql: str) -> list[dict[str, Any]]:
        if self.schema:
            for t in TABLES:
                sql = sql.replace(f" {t} ", f" {self.schema}.{t} ").replace(f" {t}\n", f" {self.schema}.{t}\n")
        with self._lock:
            return self._query(sql)

    def _query(self, sql: str) -> list[dict[str, Any]]:
        cur = self.con.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [dict(zip(cols, [None if v is None else str(v) for v in row])) for row in cur.fetchall()] if cols else []
        cur.close()
        return rows


_CACHE: dict[str, Any] = {}


def get_backend():
    """Resolver: JDBC (local platform) > REST > DuckDB over the synthetic CSVs. One connection per process."""
    if "backend" in _CACHE:
        return _CACHE["backend"]
    _CACHE["backend"] = _make_backend()
    return _CACHE["backend"]


def _make_backend():
    jdbc = os.getenv("ZETARIS_JDBC_URL")
    if jdbc and os.getenv("ZETARIS_JDBC_JAR"):
        try:
            return ZetarisJDBCBackend(jdbc, os.getenv("ZETARIS_USER", ""), os.getenv("ZETARIS_PASSWORD", ""), os.environ["ZETARIS_JDBC_JAR"], os.getenv("ZETARIS_SCHEMA", ""))
        except Exception as e:  # platform not running: say so, and keep the agent usable on the local CSVs
            print(f"[sql_backend] Zetaris JDBC unavailable ({type(e).__name__}); falling back to DuckDB", flush=True)
            return DuckDBBackend()
    url, key = os.getenv("ZETARIS_SQL_URL"), os.getenv("ZETARIS_API_KEY")
    if url and key:
        return ZetarisBackend(url, key, os.getenv("ZETARIS_SCHEMA", ""))
    return DuckDBBackend()
