"""Database layer - SQLite persistence for test runs and steps.

Schema changes from the original:
  test_steps: added retry_count INTEGER, recovery_info TEXT

Migration is performed with ALTER TABLE so existing databases are upgraded
automatically on the next startup without data loss.
"""
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict


class Database:
    def __init__(self, db_path: str = "web_tester.db"):
        self.db_path = db_path

    def init(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id             TEXT PRIMARY KEY,
                url            TEXT NOT NULL,
                goal           TEXT NOT NULL,
                status         TEXT NOT NULL,
                final_verdict  TEXT,
                duration       REAL,
                total_steps    INTEGER DEFAULT 0,
                passed_steps   INTEGER DEFAULT 0,
                failed_steps   INTEGER DEFAULT 0,
                error          TEXT,
                created_at     TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_steps (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                test_run_id     TEXT NOT NULL,
                step_number     INTEGER NOT NULL,
                action          TEXT,
                target          TEXT,
                value           TEXT,
                reasoning       TEXT,
                status          TEXT,
                error_message   TEXT,
                screenshot_path TEXT,
                retry_count     INTEGER DEFAULT 0,
                recovery_info   TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (test_run_id) REFERENCES test_runs(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_runs_created_at
            ON test_runs (created_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_steps_run_id
            ON test_steps (test_run_id)
        """)

        conn.commit()

        # Safe migration: add new columns to existing databases
        self._migrate(conn)

        conn.close()

    def _migrate(self, conn: sqlite3.Connection):
        """Add new columns to an existing DB without breaking old rows."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(test_steps)")
        existing = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("retry_count",   "INTEGER DEFAULT 0"),
            ("recovery_info", "TEXT"),
        ]
        for col, definition in migrations:
            if col not in existing:
                cursor.execute(f"ALTER TABLE test_steps ADD COLUMN {col} {definition}")

        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def save_test_run(self, url: str, goal: str, result: dict) -> str:
        test_id = str(uuid.uuid4())
        conn = self._connect()
        cursor = conn.cursor()

        report = result.get("report", {})
        cursor.execute(
            """
            INSERT INTO test_runs
            (id, url, goal, status, final_verdict, duration,
             total_steps, passed_steps, failed_steps, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                test_id,
                url,
                goal,
                result.get("status", "unknown"),
                result.get("final_verdict"),
                result.get("duration"),
                report.get("total_steps", 0),
                report.get("passed_steps", 0),
                report.get("failed_steps", 0),
                result.get("error"),
                datetime.now().isoformat(),
            ),
        )

        for step in result.get("steps", []):
            cursor.execute(
                """
                INSERT INTO test_steps
                (test_run_id, step_number, action, target, value, reasoning,
                 status, error_message, screenshot_path, retry_count, recovery_info, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    test_id,
                    step.get("step"),
                    step.get("action"),
                    step.get("target"),
                    step.get("value"),
                    step.get("reasoning"),
                    step.get("status"),
                    step.get("error"),
                    step.get("screenshot"),
                    step.get("retry_count", 0),
                    step.get("recovery"),
                    datetime.now().isoformat(),
                ),
            )

        conn.commit()
        conn.close()
        return test_id

    def get_test_runs(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM test_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_test_run(self, test_id: str) -> Optional[Dict]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM test_runs WHERE id = ?", (test_id,))
        run = cursor.fetchone()
        if not run:
            conn.close()
            return None

        run_dict = dict(run)
        cursor.execute(
            "SELECT * FROM test_steps WHERE test_run_id = ? ORDER BY step_number",
            (test_id,),
        )
        run_dict["steps"] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return run_dict

    def delete_test_run(self, test_id: str) -> bool:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_steps WHERE test_run_id = ?", (test_id,))
        cursor.execute("DELETE FROM test_runs WHERE id = ?", (test_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
