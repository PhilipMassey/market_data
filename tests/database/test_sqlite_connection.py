import os
import sqlite3
import database.sqlite_connection as sqlite_conn


def test_default_sqlite_db_path_uses_home_dir():
    """
    Verify that SQLITE_DB_PATH resolves relative to the user's home directory
    even when SQLITE_DB_PATH is unset or contains a literal '~', ensuring portability
    between macOS (/Users/...) and Linux GCE VMs (/home/...).
    """
    expected_suffix = os.path.join("projects", ".data", "market_data.db")
    assert sqlite_conn.SQLITE_DB_PATH.endswith(expected_suffix)
    assert sqlite_conn.SQLITE_DB_PATH.startswith(os.path.expanduser("~"))
    assert "~" not in sqlite_conn.SQLITE_DB_PATH


def test_get_sqlite_conn_enables_wal_and_busy_timeout(tmp_path, monkeypatch):
    """
    Verify that get_sqlite_conn sets WAL journal mode and busy_timeout for safe
    concurrent VM access.
    """
    db_file = tmp_path / "test_vm.db"
    monkeypatch.setattr(sqlite_conn, "SQLITE_DB_PATH", str(db_file))

    sqlite_conn.init_sqlite_db()

    with sqlite_conn.get_sqlite_conn() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert journal_mode.lower() == "wal"
        assert busy_timeout == 5000

        # Ensure expected tables were initialized
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "market_data_close",
            "fidelity_positions",
            "ticker_meta_profile",
            "period_rank_filter",
        }.issubset(tables)

