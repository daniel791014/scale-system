"""
最小驗證腳本：
1) 初始化資料庫
2) upsert 一筆測試產品到 products
3) 直接查詢 SQLite，確認資料存在

執行：
python verify_products_upsert.py
"""

import sqlite3
import pandas as pd

import db_schema
from data_loader import upsert_products


def main():
    db_schema.init_database()

    df = pd.DataFrame(
        [
            [
                "TEST-UNIQ-001",
                "test_client",
                "1260",
                "BL",
                96,
                1.0,
                2.0,
                3.0,
                0.1,
                0.2,
                0.3,
                "n1",
                "n2",
                "n3",
            ]
        ],
        columns=[
            "產品ID",
            "客戶名",
            "溫度等級",
            "品種",
            "密度",
            "長",
            "寬",
            "高",
            "下限",
            "準重",
            "上限",
            "備註1",
            "備註2",
            "備註3",
        ],
    )

    upsert_products(df)

    conn = sqlite3.connect(db_schema.DB_FILE)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products WHERE 產品ID = ?", ("TEST-UNIQ-001",))
        exists = cur.fetchone()[0]
        print("DB_FILE =", db_schema.DB_FILE)
        print("exists_in_db =", exists)
        if exists != 1:
            raise SystemExit("驗證失敗：products 找不到 TEST-UNIQ-001")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()







