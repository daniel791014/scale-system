import os
import sys

# 設定標準輸出編碼為 UTF-8（解決 Windows 命令提示字元中文顯示問題）
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Python 3.6 或更早版本不支援 reconfigure，使用替代方案
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# ==========================================
# 1. 網路與伺服器連線設定
# ==========================================
# 資料庫電腦 (伺服器) 的 IP
SERVER_IP = "172.16.3.155" 

# 資料庫電腦桌面上的共用資料夾名稱
SHARED_FOLDER = "GEMINI TEST2"

# 組合出 Windows 網路路徑 (例如: \\172.16.3.155\GEMINI TEST2)
SERVER_PATH = f"\\\\{SERVER_IP}\\{SHARED_FOLDER}"

# --- 自動判斷連線狀態 ---
def check_server_path(path):
    """檢查伺服器路徑是否可存取（使用多重方式驗證）"""
    try:
        # 方法1: 使用 os.path.exists
        if os.path.exists(path):
            # 方法2: 嘗試列出目錄內容以確認真的可以存取
            try:
                _ = os.listdir(path)
                return True
            except (OSError, PermissionError):
                return False
        return False
    except Exception:
        return False

if check_server_path(SERVER_PATH):
    # 如果找得到伺服器，就用伺服器當作基地
    BASE_DIR = SERVER_PATH
    IS_STANDALONE_MODE = False
    print(f"🔗 [連線模式] 成功連接伺服器：{SERVER_PATH}")
else:
    # 如果找不到 (斷線或權限不足)，暫時用自己電腦的桌面
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    IS_STANDALONE_MODE = True
    print(f"⚠️ [單機模式] 找不到伺服器，使用本機路徑：{BASE_DIR}")

# ==========================================
# 2. 資料庫設定
# ==========================================
# 注意：系統已改用 SQLite 資料庫，不再使用 CSV 檔案
# SQL 資料庫檔案路徑在 db_schema.py 中定義
# 如需遷移現有 CSV 資料，請執行 migrate_to_sql.py

# 保留以下路徑定義以維持向後相容性（用於遷移腳本）
FILE_PRODUCTS = os.path.join(BASE_DIR, "db_products.csv")
FILE_ORDERS = os.path.join(BASE_DIR, "db_orders.csv")
FILE_LOGS = os.path.join(BASE_DIR, "db_logs.csv")
FILE_LINE_STATUS = os.path.join(BASE_DIR, "db_line_status.json")

# ==========================================
# 3. ⚖️ 磅秤硬體設定 (關鍵修改區)
# ==========================================
# 設定您剛剛測試出來的正確 Port
SCALE_PORT = "COM5"

# 傳輸速率 (通常是 9600，如果亂碼改 2400)
SCALE_BAUDRATE = 9600 

# ⚠️ 是否使用模擬模式？
# True  = 顯示拉條，手動拉重量 (測試用)
# False = 隱藏拉條，直接讀取 COM5 (正式用)
USE_SIMULATION = False

# ==========================================
# 4. 資料庫欄位定義 (請勿更改)
# ==========================================
ORDER_COLUMNS = [
    "產線", "排程順序", "工單號碼", "產品ID", "顯示內容", 
    "品種", "密度", "準重", "預計數量", "已完成數量", 
    "狀態", "建立時間", "詳細規格字串"
]

LOG_COLUMNS = [
    "時間", "產線", "工單號", "產品ID", "實測重", 
    "判定結果", "NG原因", "組別", "班別", "操作員"
]

# ==========================================
# 5. 選項與參數設定
# ==========================================
PRODUCTION_LINES = ["Line 1", "Line 2", "Line 3", "Line 4"]
SHIFT_OPTIONS = ["早班", "中班", "晚班"]
GROUP_OPTIONS = ["A", "B", "C", "D"]
TEMP_OPTIONS = ["1260", "1200", "1300", "1400", "1500", "BIOSTAR"]

# ==========================================
# 6. 產品規格與密度邏輯
# ==========================================
# 密度對照表 {密度: (下限係數, 上限係數)}
DENSITY_MAP = {
    64: (59.74, 85.00), 
    80: (74.03, 93.75), 
    96: (87.55, 115.00), 
    104: (96.24, 121.88), 
    112: (103.64, 131.25), 
    120: (111.05, 140.63), 
    128: (118.45, 150.00), 
    136: (125.85, 159.38), 
    144: (133.26, 168.75), 
    160: (154.50, 175.50), 
    192: (177.68, 220.00), 
    256: (226.60, 312.00)
}
DENSITY_OPTIONS = list(DENSITY_MAP.keys())

# 特殊品種清單
SPECIAL_VARIETIES = ["BULK", "BUXD", "SB", "BIOSTAR"] 
# 所有品種清單
ALL_VARIETIES = sorted(["ACPE", "ACBL", "BL", "BLOC(原反)", "RHK(S-F)"] + SPECIAL_VARIETIES)

# ==========================================
# 7. 介面設定
# ==========================================
PAGE_TITLE = "產線秤重系統 v18.55 (COM5 正式版)"
PAGE_LAYOUT = "wide"

# ==========================================
# 8. 單機模式處理設定
# ==========================================
# 當無法連接到伺服器時的行為：
# True  = 完全阻止啟動，顯示錯誤訊息並停止程式
# False = 顯示警告訊息但允許繼續使用（不建議，資料可能無法同步）
BLOCK_STANDALONE_MODE = True