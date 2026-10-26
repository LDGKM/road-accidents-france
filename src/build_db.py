"""Build the DuckDB database from the raw CSV files.

    python src/build_db.py

Creates data/accidents.duckdb with the clean tables (sql/01_clean.sql),
the analysis views (sql/02_model.sql) and the INSEE population table.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "accidents.duckdb"


def run_sql_file(con: duckdb.DuckDBPyConnection, name: str) -> None:
    sql = (ROOT / "sql" / name).read_text(encoding="utf-8").replace("{RAW}", RAW.as_posix())
    con.execute(sql)


def load_population(con: duckdb.DuckDBPyConnection) -> None:
    """INSEE estimate of the population on 1 January 2023, by department,
    sex and five-year age group (sheet "2023" of the Excel file).

    The sheet has a two-row header: the first row gives the block
    (Ensemble / Hommes / Femmes), the second the age group. We keep the
    Hommes and Femmes blocks and reshape them into a long table:
    dep | sex | age_group | population.
    """
    raw = pd.read_excel(RAW / "insee_pop_dep.xls", sheet_name="2023", header=None)
    # locate the row that holds the age groups ("0 à 4 ans", ...)
    hdr = raw.index[raw.iloc[:, 2].astype(str).str.contains("0 à 4", na=False)][0]
    ages = raw.iloc[hdr].tolist()
    blocks = raw.iloc[hdr - 1].ffill().tolist()
    body = raw.iloc[hdr + 1:].copy()
    body = body[body.iloc[:, 0].astype(str).str.match(r"^(\d{2}|2A|2B)$")]
    rows = []
    for col, (block, age) in enumerate(zip(blocks, ages)):
        if not isinstance(age, str) or "ans" not in age or block not in ("Hommes", "Femmes"):
            continue
        lo = int(age.split()[0])
        for dep, val in zip(body.iloc[:, 0], body.iloc[:, col]):
            rows.append((str(dep), 1 if block == "Hommes" else 2, lo, float(val)))
    pop = pd.DataFrame(rows, columns=["dep", "sex", "age_lo", "population"])
    con.execute("CREATE OR REPLACE TABLE population AS SELECT * FROM pop")


def main() -> None:
    DB.unlink(missing_ok=True)
    con = duckdb.connect(DB.as_posix())
    run_sql_file(con, "01_clean.sql")
    run_sql_file(con, "02_model.sql")
    load_population(con)
    for t in ("accidents", "places", "vehicles", "users", "population"):
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"{t:<11} {n:>9,} rows")
    con.close()


if __name__ == "__main__":
    main()
