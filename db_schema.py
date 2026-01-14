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

# 資料庫檔案路徑 - 改為動態獲取函數（解決重新連線後路徑不更新的問題）
def get_db_file():
    """動態獲取資料庫檔案路徑（根據當前的 BASE_DIR）"""
    return os.path.join(config.BASE_DIR, "production_db.sqlite")

# 保留 DB_FILE 變數以維持向後相容性（但改為動態獲取）
# 注意：所有使用 DB_FILE 的地方都應該改用 get_db_file() 函數
DB_FILE = get_db_file()

# 用於追蹤是否已經顯示過初始化訊息
_db_init_message_shown = False


def create_tables():
    """建立所有資料表"""
    try:
        # 動態獲取資料庫路徑（確保使用最新的 BASE_DIR）
        db_file = get_db_file()
        # [改進] 確保資料庫目錄存在
        db_dir = os.path.dirname(db_file)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                print(f"📁 建立資料庫目錄：{db_dir}")
            except Exception as e:
                print(f"❌ 無法建立資料庫目錄 {db_dir}：{e}")
                raise
        
        # [改進] 檢查是否有寫入權限
        if os.path.exists(db_dir):
            test_file = os.path.join(db_dir, ".write_test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                print(f"❌ 資料庫目錄沒有寫入權限：{db_dir} - {e}")
                raise
        
        print(f"🔧 正在建立資料庫：{db_file}")
        # [改進] 加入 timeout/busy_timeout，避免多人同時啟動或網路磁碟延遲時出現 database is locked
        conn = sqlite3.connect(db_file, timeout=30, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout = 30000")
        
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
        print(f"✅ 資料庫結構建立完成：{db_file}")
        
        # [改進] 驗證資料庫檔案是否真的建立
        if os.path.exists(db_file):
            file_size = os.path.getsize(db_file)
            print(f"✅ 資料庫檔案已建立，大小：{file_size} bytes")
        else:
            raise Exception(f"資料庫檔案建立失敗：{db_file}")
            
    except sqlite3.Error as e:
        error_msg = f"❌ SQLite 錯誤：{e}"
        print(error_msg)
        print(f"   資料庫路徑：{db_file}")
        print(f"   資料庫目錄：{os.path.dirname(db_file)}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"❌ 建立資料庫時發生錯誤：{e}"
        print(error_msg)
        print(f"   資料庫路徑：{db_file}")
        print(f"   資料庫目錄：{os.path.dirname(db_file)}")
        print(f"   BASE_DIR：{config.BASE_DIR}")
        raise Exception(error_msg)


def get_connection():
    """取得資料庫連線"""
    try:
        # 動態獲取資料庫路徑（確保使用最新的 BASE_DIR）
        db_file = get_db_file()
        # 確保資料庫檔案存在
        if not os.path.exists(db_file):
            print(f"📦 資料庫檔案不存在，正在建立：{db_file}")
            create_tables()
        
        # [改進] 測試連接 + timeout/busy_timeout，降低 network share / 多人同時存取造成的鎖定問題
        conn = sqlite3.connect(db_file, timeout=30, check_same_thread=False)
        # 執行簡單查詢測試連接是否正常
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout = 30000")
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return conn
    except Exception as e:
        error_msg = f"❌ 無法建立資料庫連接：{e}"
        print(error_msg)
        db_file = get_db_file()
        print(f"   資料庫路徑：{db_file}")
        print(f"   資料庫目錄：{os.path.dirname(db_file)}")
        print(f"   BASE_DIR：{config.BASE_DIR}")
        raise Exception(error_msg)


def init_database():
    """初始化資料庫（如果不存在則建立）"""
    global _db_init_message_shown
    
    try:
        # 動態獲取資料庫路徑（確保使用最新的 BASE_DIR）
        db_file = get_db_file()
        print(f"🔍 檢查資料庫：{db_file}")
        print(f"   BASE_DIR：{config.BASE_DIR}")
        print(f"   資料庫目錄存在：{os.path.exists(os.path.dirname(db_file))}")
        
        if not os.path.exists(db_file):
            print(f"📦 資料庫檔案不存在，開始初始化...")
            create_tables()
            print(f"📦 資料庫已初始化：{db_file}")
            _db_init_message_shown = True
        else:
            print(f"📦 資料庫檔案已存在：{db_file}")
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
                file_size = os.path.getsize(db_file)
                print(f"📦 資料庫已存在，大小：{file_size} bytes")
                _db_init_message_shown = True
    except Exception as e:
        error_msg = f"❌ 初始化資料庫失敗：{e}"
        print(error_msg)
        db_file = get_db_file()
        print(f"   資料庫路徑：{db_file}")
        print(f"   資料庫目錄：{os.path.dirname(db_file)}")
        print(f"   BASE_DIR：{config.BASE_DIR}")
        raise Exception(error_msg)

