import json
import sqlite3
from pathlib import Path

ROOT = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\db_storage")
OUT_DIR = Path(r"C:\Users\Administrator\Documents\运营\work\ai_customer_replay")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def connect(path: Path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def schema(path: Path):
    try:
        with connect(path) as con:
            rows = con.execute(
                "select name, type, sql from sqlite_master where type in ('table','view') order by name"
            ).fetchall()
        return rows
    except Exception as exc:
        return [("__UNREADABLE__", "error", str(exc))]


def sample_table(path: Path, table: str, limit=5):
    with connect(path) as con:
        cols = [r[1] for r in con.execute(f"pragma table_info({table})").fetchall()]
        rows = con.execute(f"select * from {table} limit {limit}").fetchall()
    return cols, rows


def find_text_columns(path: Path):
    found = []
    try:
        con = connect(path)
    except Exception:
        return found
    with con:
        try:
            tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]
        except Exception:
            return found
        for t in tables:
            try:
                info = con.execute(f"pragma table_info({t})").fetchall()
            except Exception:
                continue
            text_cols = [r[1] for r in info if (r[2] or "").lower() in ("text", "varchar", "char", "nvarchar", "string") or r[2] == ""]
            if text_cols:
                found.append((t, text_cols, [(r[1], r[2]) for r in info]))
    return found


def search_like(path: Path, terms):
    results = []
    try:
        con = connect(path)
    except Exception:
        return results
    with con:
        try:
            tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]
        except Exception:
            return results
        for t in tables:
            try:
                info = con.execute(f"pragma table_info({t})").fetchall()
            except Exception:
                continue
            cols = [r[1] for r in info]
            text_cols = [r[1] for r in info if (r[2] or "").lower() in ("text", "varchar", "char", "nvarchar", "string") or r[2] == ""]
            for col in text_cols:
                for term in terms:
                    try:
                        q = f"select * from {t} where {col} like ? limit 50"
                        rows = con.execute(q, (f"%{term}%",)).fetchall()
                    except Exception:
                        continue
                    for row in rows:
                        item = dict(zip(cols, row))
                        results.append({"db": str(path), "table": t, "column": col, "term": term, "row": item})
    return results


def main():
    dbs = [
        ROOT / "contact" / "contact.db",
        ROOT / "contact" / "contact_fts.db",
        ROOT / "message" / "message_fts.db",
        ROOT / "session" / "session.db",
        ROOT / "message" / "message_0.db",
        ROOT / "message" / "message_1.db",
    ]
    report = {}
    for db in dbs:
        if not db.exists():
            continue
        db_key = str(db)
        report[db_key] = {
            "schema": [(name, typ, sql) for name, typ, sql in schema(db)],
            "text_columns": find_text_columns(db),
        }
    (OUT_DIR / "wechat_db_schema.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    terms = ["ai客服", "AI客服", "客户", "智能客服", "客服", "AI", "ai"]
    all_results = []
    for db in dbs:
        if db.exists():
            all_results.extend(search_like(db, terms))
    (OUT_DIR / "wechat_db_keyword_hits.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({"schema_dbs": len(report), "hits": len(all_results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
