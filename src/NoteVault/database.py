from pathlib import Path
from typing import Optional

import sqlite3

DBFILENAME = "db.sqlite"


class Database:
    def __init__(self, storage_pth: Path):
        db_file = storage_pth / DBFILENAME
        db_existed = db_file.exists()

        self._conn = sqlite3.connect(db_file)
        self._cursor = self._conn.cursor()

        if not db_existed:
            self._cursor.execute(
                "CREATE TABLE records(name TEXT PRIMARY KEY, body TEXT)"
            )

    def close(self):
        self._conn.close()
        self._conn, self._cursor = None, None

    def fetch_record(self, title: str) -> Optional[str]:
        res = self._cursor.execute(
            "SELECT body FROM records WHERE name = (?)",
            (title,)
        ).fetchone()
        if res is None:
            return None
        else:
            return res[0]

    def add_record(self, title: str, body: str):
        self._cursor.execute(
            "INSERT INTO records VALUES(?, ?)",
            (title, body)
        )
        self._conn.commit()

    def del_record(self, title: str) -> None:
        self._cursor.execute(
            "DELETE FROM records WHERE name = (?)",
            (title,)
        )
        self._conn.commit()
