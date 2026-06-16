import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).with_name("hard_drive_inventory.db")


PROFILE_VIEWS = {
    "hgst_oracle": {
        "profile": "hgst_oracle",
        "fields": ["Firmware", "Config", "Serial Number", "Model Number", "Part Number", "WWN"],
    },
    "hitachi_oracle": {
        "profile": "hitachi_oracle",
        "fields": ["Firmware", "Config", "Serial Number", "Model Number", "Part Number", "WWN"],
    },
    "savvio": {
        "profile": "savvio",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "savvio_10k2": {
        "profile": "savvio_10k2",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "savvio_15k1": {
        "profile": "savvio_15k1",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "savvio_15k3": {
        "profile": "savvio_15k3",
        "fields": ["Model Number", "Lot Number", "Part Number", "Serial Number", "Factory Number", "Firmware", "Config"],
    },
    "western_digital": {
        "profile": "western_digital",
        "fields": ["Model Number", "Serial Number", "Part Number", "WWN", "Date Code", "DCM", "Firmware", "Config"],
    },
    "dell_constellation_es3": {
        "profile": "dell_constellation_es3",
        "fields": ["Model Number", "Part Number", "Serial Number", "WWN", "Date Code", "Firmware", "Config"],
    },
    "dell_constellation_es": {
        "profile": "dell_constellation_es",
        "fields": ["Model Number", "Part Number", "Serial Number", "Date Code", "WWN", "Firmware", "Config"],
    },
    "misc": {
        "profile": "misc",
        "fields": [
            "Model Number",
            "Serial Number",
            "Part Number",
            "Lot Number",
            "Factory Number",
            "Firmware",
            "Config",
            "WWN",
            "Date Code",
            "DCM",
            "Asset Tag",
            "Oracle/Sun Part Number",
        ],
    },
}


LEGACY_PROFILE_VIEWS = [
    "inventory_hgst_oracle",
    "inventory_hitachi_oracle",
    "inventory_savvio",
    "inventory_savvio_10k2",
    "inventory_savvio_15k1",
    "inventory_savvio_15k3",
    "inventory_western_digital",
    "inventory_dell_constellation_es3",
    "inventory_dell_constellation_es",
    "inventory_misc",
]


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = MEMORY")
    return conn


def create_tables():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS drives (
                drive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT,
                model TEXT,
                capacity TEXT,
                drive_type TEXT,
                profile TEXT,
                notes TEXT,
                date_added TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS barcodes (
                barcode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_id INTEGER,
                barcode_value TEXT,
                barcode_type TEXT,
                date_scanned TEXT,
                UNIQUE (drive_id, barcode_value, barcode_type),
                FOREIGN KEY (drive_id) REFERENCES drives(drive_id)
            )
            """
        )
        migrate_drive_profile_column(conn)
        migrate_barcode_uniqueness(conn)
        create_profile_views(conn)


def migrate_drive_profile_column(conn):
    drive_columns = [column[1] for column in conn.execute("PRAGMA table_info(drives)").fetchall()]
    if "profile" not in drive_columns:
        conn.execute("ALTER TABLE drives ADD COLUMN profile TEXT")


def migrate_barcode_uniqueness(conn):
    barcode_columns = conn.execute("PRAGMA table_info(barcodes)").fetchall()
    if not barcode_columns:
        return

    index_rows = conn.execute("PRAGMA index_list(barcodes)").fetchall()
    has_global_value_unique = False
    for index_row in index_rows:
        index_name = index_row[1]
        is_unique = bool(index_row[2])
        if not is_unique:
            continue

        indexed_columns = [
            column_row[2]
            for column_row in conn.execute(f"PRAGMA index_info({index_name})").fetchall()
        ]
        if indexed_columns == ["barcode_value"]:
            has_global_value_unique = True
            break

    if not has_global_value_unique:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_barcodes_drive_value_type
            ON barcodes (drive_id, barcode_value, barcode_type)
            """
        )
        return

    conn.execute("ALTER TABLE barcodes RENAME TO barcodes_old")
    conn.execute(
        """
        CREATE TABLE barcodes (
            barcode_id INTEGER PRIMARY KEY AUTOINCREMENT,
            drive_id INTEGER,
            barcode_value TEXT,
            barcode_type TEXT,
            date_scanned TEXT,
            UNIQUE (drive_id, barcode_value, barcode_type),
            FOREIGN KEY (drive_id) REFERENCES drives(drive_id)
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO barcodes (
            barcode_id, drive_id, barcode_value, barcode_type, date_scanned
        )
        SELECT barcode_id, drive_id, barcode_value, barcode_type, date_scanned
        FROM barcodes_old
        """
    )
    conn.execute("DROP TABLE barcodes_old")


def create_profile_views(conn):
    for legacy_view in LEGACY_PROFILE_VIEWS:
        conn.execute(f"DROP VIEW IF EXISTS {legacy_view}")

    for view_name, config in PROFILE_VIEWS.items():
        profile = config["profile"]
        field_columns = []
        for field in config["fields"]:
            field_columns.append(
                f"""
                GROUP_CONCAT(
                    CASE WHEN b.barcode_type = '{sql_string(field)}' THEN b.barcode_value END,
                    ', '
                ) AS {sql_identifier(field)}
                """
            )

        columns_sql = ",\n".join(field_columns)
        if columns_sql:
            columns_sql = ",\n" + columns_sql

        conn.execute(f"DROP VIEW IF EXISTS {view_name}")
        conn.execute(
            f"""
            CREATE VIEW {view_name} AS
            SELECT
                d.drive_id,
                d.brand,
                d.model,
                d.capacity,
                d.drive_type,
                d.profile,
                d.notes,
                d.date_added
                {columns_sql}
            FROM drives d
            LEFT JOIN barcodes b ON b.drive_id = d.drive_id
            WHERE d.profile = '{sql_string(profile)}'
            GROUP BY
                d.drive_id,
                d.brand,
                d.model,
                d.capacity,
                d.drive_type,
                d.profile,
                d.notes,
                d.date_added
            """
        )


def sql_string(value):
    return str(value).replace("'", "''")


def sql_identifier(value):
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "value"


def add_drive(brand, model, capacity, drive_type, notes="", profile=""):
    date_added = datetime.now().isoformat(timespec="seconds")
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO drives (brand, model, capacity, drive_type, profile, notes, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (brand, model, capacity, drive_type, profile, notes, date_added),
        )
        return cursor.lastrowid


def add_barcode(drive_id, barcode_value, barcode_type="Unknown"):
    date_scanned = datetime.now().isoformat(timespec="seconds")
    try:
        with connect_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO barcodes (drive_id, barcode_value, barcode_type, date_scanned)
                VALUES (?, ?, ?, ?)
                """,
                (drive_id, barcode_value, barcode_type, date_scanned),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def search_by_barcode(barcode_value):
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT
                d.drive_id,
                d.brand,
                d.model,
                d.capacity,
                d.drive_type,
                d.profile,
                d.notes,
                d.date_added,
                b.barcode_value,
                b.barcode_type,
                b.date_scanned
            FROM barcodes b
            JOIN drives d ON d.drive_id = b.drive_id
            WHERE b.barcode_value = ?
            """,
            (barcode_value,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def view_all_drives():
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT drive_id, brand, model, capacity, drive_type, profile, notes, date_added
            FROM drives
            ORDER BY drive_id
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def view_barcodes_for_drive(drive_id):
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT barcode_id, drive_id, barcode_value, barcode_type, date_scanned
            FROM barcodes
            WHERE drive_id = ?
            ORDER BY barcode_id
            """,
            (drive_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def view_inventory_by_profile(profile):
    if profile not in PROFILE_VIEWS:
        return []

    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(f"SELECT * FROM {profile} ORDER BY drive_id")
        return [dict(row) for row in cursor.fetchall()]
