"""Run a Lightning SQL file against the local Zetaris platform, one statement per call,
through the bundled JDBC driver (the documented path). Prints each statement's first rows.

Usage: .venv/bin/python zetaris/run_sql.py zetaris/register.sql
Env (from .env.local): ZETARIS_JDBC_URL, ZETARIS_JDBC_JAR, ZETARIS_USER, ZETARIS_PASSWORD, JAVA_HOME, POSTGRES_PASSWORD
"""
from __future__ import annotations
import os, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env.local")
import jaydebeapi  # noqa: E402


def statements(text: str) -> list[str]:
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
    out, buf = [], []
    for line in text.splitlines():
        buf.append(line)
        # COMPILE USL ... DDL carries several CREATE TABLE statements separated by ';' — keep it whole until a blank line after the last ')'
        joined = "\n".join(buf)
        if joined.lstrip().upper().startswith("COMPILE USL"):
            if line.strip() == "" and joined.rstrip().endswith(")"):
                out.append(joined.strip()); buf = []
        elif line.rstrip().endswith(";"):
            out.append(joined.strip().rstrip(";")); buf = []
    if "".join(buf).strip():
        out.append("\n".join(buf).strip().rstrip(";"))
    return [s for s in out if s]


def main(path: str) -> None:
    sql = Path(path).read_text().replace("${POSTGRES_PASSWORD}", os.getenv("POSTGRES_PASSWORD", ""))
    con = jaydebeapi.connect("com.zetaris.lightning.jdbc.LightningDriver", os.environ["ZETARIS_JDBC_URL"],
                             [os.getenv("ZETARIS_USER", ""), os.getenv("ZETARIS_PASSWORD", "")], os.environ["ZETARIS_JDBC_JAR"])
    cur = con.cursor()
    for i, st in enumerate(statements(sql), 1):
        head = re.sub(r"\s+", " ", st)[:90]
        try:
            cur.execute(st)
            rows = cur.fetchmany(5) if cur.description else []
            print(f"[{i}] OK  {head}" + (f" -> {rows}" if rows else ""))
        except Exception as e:  # report and continue so one bad statement does not hide the rest
            print(f"[{i}] ERR {head}\n      {str(e)[:300]}")
    cur.close(); con.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "zetaris/register.sql"))
