from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from app.config import settings


def safe_table_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean:
        clean = "dataset"
    if clean[0].isdigit():
        clean = f"t_{clean}"
    return clean


def sql_string_literal(value: str | Path) -> str:
    """Return a safely quoted SQL string literal."""
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def get_connection() -> duckdb.DuckDBPyConnection:
    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.duckdb_path))


def run_sql(sql: str) -> pd.DataFrame:
    with get_connection() as conn:
        return conn.execute(sql).df()


def run_select_sql(sql: str) -> pd.DataFrame:
    stripped = sql.strip().lower()
    allowed_starts = ("select", "with", "show", "describe", "pragma")
    if not stripped.startswith(allowed_starts):
        raise ValueError("Only SELECT/WITH/SHOW/DESCRIBE/PRAGMA queries are allowed from the UI.")
    return run_sql(sql)


def register_parquet_table(
    table_name: str,
    parquet_path: Path,
    source_id: str | None = None,
    dataset_name: str | None = None,
    as_view: bool = True,
) -> str:
    table_name = safe_table_name(table_name)
    parquet_path = Path(parquet_path)
    parquet_literal = sql_string_literal(parquet_path)

    with get_connection() as conn:
        if as_view:
            conn.execute(
                f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet({parquet_literal})"
            )
        else:
            conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet({parquet_literal})"
            )

        stats = conn.execute(f"SELECT COUNT(*) AS row_count FROM {table_name}").fetchone()
        columns = conn.execute(f"DESCRIBE {table_name}").df()

    if source_id and dataset_name:
        with sqlite3.connect(settings.metadata_db_path) as conn:
            conn.execute(
                """
                INSERT INTO duckdb_registered_tables (
                  id, source_id, dataset_name, table_name, parquet_path,
                  row_count, column_count, registered_at, status, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    source_id,
                    dataset_name,
                    table_name,
                    str(parquet_path),
                    int(stats[0]) if stats else None,
                    len(columns),
                    datetime.now(timezone.utc).isoformat(),
                    "registered_view" if as_view else "registered_table",
                    None,
                ),
            )
            conn.commit()

    return table_name


def load_csv_to_table(csv_path: Path, table_name: str) -> str:
    table_name = safe_table_name(table_name)
    csv_literal = sql_string_literal(csv_path)
    with get_connection() as conn:
        conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto({csv_literal})"
        )
    return table_name


def list_tables() -> pd.DataFrame:
    return run_sql("SHOW TABLES")


def describe_table(table_name: str) -> pd.DataFrame:
    table_name = safe_table_name(table_name)
    return run_sql(f"DESCRIBE {table_name}")
