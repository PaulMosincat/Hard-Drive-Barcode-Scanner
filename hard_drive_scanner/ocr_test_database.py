import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).with_name("barcode_ocr_test.db")


def set_database_profile(profile):
    global DB_PATH
    safe_profile = "".join(
        char if char.isalnum() or char in {"_", "-"} else "_"
        for char in profile.lower()
    ).strip("_")
    if not safe_profile or safe_profile == "unknown":
        DB_PATH = Path(__file__).with_name("barcode_ocr_test.db")
        return

    DB_PATH = Path(__file__).with_name(f"barcode_ocr_test_{safe_profile}.db")


def current_database_path():
    return DB_PATH


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = MEMORY")
    return conn


def create_tables():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_test_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile TEXT,
                image_path TEXT,
                date_created TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_test_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                barcode_value TEXT,
                barcode_format TEXT,
                barcode_type_suggested TEXT,
                nearby_ocr_text TEXT,
                profile_decision TEXT,
                match_status TEXT,
                crop_path TEXT,
                date_created TEXT,
                FOREIGN KEY (run_id) REFERENCES ocr_test_runs(run_id)
            )
            """
        )


def add_test_run(profile, image_path):
    date_created = datetime.now().isoformat(timespec="seconds")
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ocr_test_runs (profile, image_path, date_created)
            VALUES (?, ?, ?)
            """,
            (profile, str(image_path), date_created),
        )
        return cursor.lastrowid


def add_test_result(
    run_id,
    barcode_value,
    barcode_format,
    barcode_type_suggested,
    nearby_ocr_text,
    profile_decision,
    match_status,
    crop_path,
):
    date_created = datetime.now().isoformat(timespec="seconds")
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ocr_test_results (
                run_id,
                barcode_value,
                barcode_format,
                barcode_type_suggested,
                nearby_ocr_text,
                profile_decision,
                match_status,
                crop_path,
                date_created
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                barcode_value,
                barcode_format,
                barcode_type_suggested,
                nearby_ocr_text,
                profile_decision,
                match_status,
                str(crop_path),
                date_created,
            ),
        )
        return cursor.lastrowid


def view_runs():
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT run_id, profile, image_path, date_created
            FROM ocr_test_runs
            ORDER BY run_id
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def view_results_for_run(run_id):
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT
                result_id,
                run_id,
                barcode_value,
                barcode_format,
                barcode_type_suggested,
                nearby_ocr_text,
                profile_decision,
                match_status,
                crop_path,
                date_created
            FROM ocr_test_results
            WHERE run_id = ?
            ORDER BY result_id
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def update_test_result_type(result_id, barcode_type_suggested, profile_decision):
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE ocr_test_results
            SET barcode_type_suggested = ?,
                profile_decision = ?
            WHERE result_id = ?
            """,
            (barcode_type_suggested, profile_decision, result_id),
        )


def delete_test_result(result_id):
    with connect_db() as conn:
        conn.execute("DELETE FROM ocr_test_results WHERE result_id = ?", (result_id,))
        reset_autoincrement(conn, "ocr_test_results", "result_id")


def delete_test_run(run_id):
    with connect_db() as conn:
        conn.execute("DELETE FROM ocr_test_results WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM ocr_test_runs WHERE run_id = ?", (run_id,))
        reset_autoincrement(conn, "ocr_test_runs", "run_id")
        reset_autoincrement(conn, "ocr_test_results", "result_id")


def reset_autoincrement(conn, table_name, id_column):
    max_id = conn.execute(f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name}").fetchone()[0]
    conn.execute(
        "UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
        (max_id, table_name),
    )
