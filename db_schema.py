"""
SQL 資料庫結構定義
使用 SQLite 作為資料庫引擎
"""

import sqlite3
import os
import sys
import config

# 設定標準輸出編碼為 UTF-8（解決 Windows 命令提示字元中文顯示問題）
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Python 3.6 或更早版本不支援 reconfigure，使用替代方案
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# 資料庫檔案路徑
DB_FILE = os.path.join(config.BASE_DIR, "production_db.sqlite")

# 用於追蹤是否已經顯示過初始化訊息
_db_init_message_shown = False


def create_tables():
    """建立所有資料表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 產品資料表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            產品ID TEXT NOT NULL UNIQUE,
            客戶名 TEXT,
            溫度等級 TEXT,
            品種 TEXT,
            密度 INTEGER,
            長 REAL,
            寬 REAL,
            高 REAL,
            下限 REAL,
            準重 REAL,
            上限 REAL,
            備註1 TEXT,
            備註2 TEXT,
            備註3 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 工單資料表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            產線 TEXT NOT NULL,
            排程順序 INTEGER NOT NULL,
            工單號碼 TEXT NOT NULL,
            產品ID TEXT,
            顯示內容 TEXT,
            品種 TEXT,
            密度 INTEGER,
            準重 REAL,
            預計數量 INTEGER DEFAULT 0,
            已完成數量 INTEGER DEFAULT 0,
            狀態 TEXT,
            建立時間 TEXT,
            詳細規格字串 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(產線, 工單號碼)
        )
    """)
    
    # 生產紀錄表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            時間 TEXT NOT NULL,
            產線 TEXT,
            工單號 TEXT,
            產品ID TEXT,
            實測重 REAL,
            判定結果 TEXT,
            NG原因 TEXT,
            組別 TEXT DEFAULT 'A',
            班別 TEXT,
            操作員 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 建立索引以提升查詢效能
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(產品ID)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_line ON work_orders(產線)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_sequence ON work_orders(產線, 排程順序)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON production_logs(時間)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_line ON production_logs(產線)")
    
    # [防重複記錄] 建立組合索引以快速查詢重複記錄（時間、產線、工單號、實測重）
    # 注意：不使用 UNIQUE 約束，因為時間戳可能有微小差異，我們在應用層面進行重複檢查
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_duplicate_check ON production_logs(時間, 產線, 工單號, 實測重)")
    
    conn.commit()
    conn.close()
    print(f"✅ 資料庫結構建立完成：{DB_FILE}")


def get_connection():
    """取得資料庫連線"""
    # 確保資料庫檔案存在
    if not os.path.exists(DB_FILE):
        create_tables()
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_database():
    """初始化資料庫（如果不存在則建立）"""
    global _db_init_message_shown
    
    if not os.path.exists(DB_FILE):
        create_tables()
        print(f"📦 資料庫已初始化：{DB_FILE}")
        _db_init_message_shown = True
    else:
        # 確保索引存在（對於已存在的資料庫，確保新索引被創建）
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 創建防重複記錄的組合索引（如果不存在）
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_duplicate_check ON production_logs(時間, 產線, 工單號, 實測重)")
            conn.commit()
        except Exception as e:
            print(f"⚠️ 創建索引時發生錯誤（可忽略）：{e}")
        finally:
            conn.close()
        
        # 只在第一次檢查時顯示訊息，避免重複輸出
        if not _db_init_message_shown:
            print(f"📦 資料庫已存在：{DB_FILE}")
            _db_init_message_shown = True

