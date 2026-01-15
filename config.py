import os
import sys
import threading
import time

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

# --- 連線狀態快取（避免頻繁檢查）---
_connection_cache = {
    'last_check': 0,
    'cache_duration': 5,  # 快取 5 秒
    'last_status': None,
    'last_base_dir': None
}

# --- 自動判斷連線狀態（帶超時保護）---
def check_server_path(path, timeout=2):
    """
    檢查伺服器路徑是否可存取（使用多重方式驗證，帶超時保護）
    
    參數:
        path: 伺服器路徑
        timeout: 超時時間（秒），預設 2 秒
    """
    def _check():
        try:
            # 方法1: 使用 os.path.exists（快速檢查）
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
    
    # 使用執行緒和超時機制，避免阻塞
    result = [None]
    exception = [None]
    
    def target():
        try:
            result[0] = _check()
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        # 超時，返回 False（假設連線失敗）
        return False
    
    if exception[0]:
        return False
    
    return result[0] if result[0] is not None else False

# 初始化連線狀態（啟動時檢查一次）
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
# 動態連線檢查函數（解決操作過程中斷線問題，帶快取機制）
# ==========================================
def get_base_dir(force_check=False):
    """
    動態獲取 BASE_DIR（帶快取機制，避免頻繁檢查）
    
    參數:
        force_check: 是否強制檢查（忽略快取）
    """
    global BASE_DIR, IS_STANDALONE_MODE, _connection_cache
    
    current_time = time.time()
    
    # 檢查快取是否有效
    if not force_check and _connection_cache['last_status'] is not None:
        time_since_check = current_time - _connection_cache['last_check']
        if time_since_check < _connection_cache['cache_duration']:
            # 使用快取的結果
            if _connection_cache['last_status']:
                BASE_DIR = SERVER_PATH
                IS_STANDALONE_MODE = False
            else:
                BASE_DIR = _connection_cache['last_base_dir']
                IS_STANDALONE_MODE = True
            return BASE_DIR
    
    # 執行連線檢查（帶超時，最多 2 秒）
    is_connected = check_server_path(SERVER_PATH, timeout=2)
    
    # 更新快取
    _connection_cache['last_check'] = current_time
    _connection_cache['last_status'] = is_connected
    
    if is_connected:
        # 如果連線正常，使用伺服器路徑
        if BASE_DIR != SERVER_PATH:
            print(f"🔄 [重新連線] 偵測到伺服器連線恢復：{SERVER_PATH}")
        BASE_DIR = SERVER_PATH
        IS_STANDALONE_MODE = False
        _connection_cache['last_base_dir'] = BASE_DIR
        return BASE_DIR
    else:
        # 如果連線中斷，使用本機路徑
        local_dir = os.path.dirname(os.path.abspath(__file__))
        if BASE_DIR == SERVER_PATH:
            print(f"⚠️ [連線中斷] 偵測到伺服器連線中斷，切換到本機模式：{local_dir}")
        BASE_DIR = local_dir
        IS_STANDALONE_MODE = True
        _connection_cache['last_base_dir'] = BASE_DIR
        return BASE_DIR

def is_server_connected():
    """檢查伺服器是否連線（使用快取，快速檢查）"""
    # 使用快取，避免頻繁檢查
    return get_base_dir() == SERVER_PATH

def refresh_connection():
    """強制重新檢查連線狀態並更新 BASE_DIR（清除快取）"""
    global BASE_DIR, IS_STANDALONE_MODE, _connection_cache
    # 清除快取，強制重新檢查
    _connection_cache['last_check'] = 0
    BASE_DIR = get_base_dir(force_check=True)
    return BASE_DIR

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