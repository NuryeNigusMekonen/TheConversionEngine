import sqlite3

from agent.config import settings


def ensure_data_dir() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dir()
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    ensure_data_dir()
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                prospect_id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                company_domain TEXT,
                contact_name TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                source TEXT NOT NULL,
                primary_segment TEXT,
                primary_segment_label TEXT,
                segment_confidence REAL NOT NULL DEFAULT 0,
                ai_maturity_score INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prospect_briefs (
                prospect_id TEXT PRIMARY KEY,
                hiring_signal_brief_json TEXT NOT NULL,
                competitor_gap_brief_json TEXT NOT NULL,
                initial_decision_json TEXT NOT NULL,
                trace_id TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (prospect_id) REFERENCES prospects (prospect_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prospect_tool_runs (
                prospect_id TEXT PRIMARY KEY,
                toolchain_report_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (prospect_id) REFERENCES prospects (prospect_id)
            )
            """
        )
        _ensure_column(connection, "prospects", "contact_phone", "TEXT")
        _ensure_column(connection, "prospects", "primary_segment_label", "TEXT")
        _ensure_column(connection, "prospects", "segment_confidence", "REAL NOT NULL DEFAULT 0")


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
