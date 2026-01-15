# data_manager.py (完全匹配 main.py 版)
import pandas as pd
import os
import json
import time
import serial
import re
import config
import random
import datetime
import streamlit as st
import sys

# 檔案鎖定相關 import（跨平台）
try:
    import fcntl  # Unix/Linux
except ImportError:
    fcntl = None

try:
    import msvcrt  # Windows
except ImportError:
    msvcrt = None

# ==========================================
# 1. 核心功能：磅秤讀取 (對應 main.py Line 883)
# ==========================================

@st.cache_resource
def get_serial_connection():
    """
    獲取串口連接（使用快取，保持連接開啟）
    這個函數會自動在 Streamlit session 中保持連接，避免頻繁開關串口
    """
    try:
        ser = serial.Serial(config.SCALE_PORT, config.SCALE_BAUDRATE, timeout=0.1)
        return ser
    except Exception as e:
        print(f"串口連接失敗: {e}")
        return None

def _read_weight_from_serial(ser):
    """
    從串口讀取重量數據（內部函數）
    """
    try:
        # [優化] 先清空舊數據，只讀取最新數據
        ser.reset_input_buffer()
        
        # [優化] 減少等待時間，快速讀取最新數據
        # 先等待一小段時間讓數據傳入
        time.sleep(0.05)  # 從 0.1 秒減少到 0.05 秒
        
        # [優化] 讀取所有可用的數據，只取最後一筆（最新的）
        latest_val = None
        latest_text = ""
        attempts = 0
        max_attempts = 5  # 從 20 次減少到 5 次
        
        while attempts < max_attempts:
            if ser.in_waiting:
                raw = ser.readline()
                try:
                    text = raw.decode('utf-8', errors='ignore').strip()
                    if len(text) > 3:
                        match = re.search(r"([\d]+\.[\d]+)", text)
                        if match:
                            latest_val = float(match.group(1))
                            latest_text = text
                            # 繼續讀取，直到沒有更多數據（獲取最新值）
                except:
                    pass
            else:
                # 如果沒有數據，稍微等待一下
                time.sleep(0.02)
            
            attempts += 1
        
        # 如果讀取到數據，返回最新值
        if latest_val is not None:
            return latest_val, f"正常連線 ({latest_text})"
        
        return 0.0, "無數據 (連線中)"
    
    except serial.SerialException as e:
        # 串口連接異常，需要重連
        raise ConnectionError(f"串口讀取錯誤: {e}")
    except Exception as e:
        raise Exception(f"讀取數據時發生錯誤: {e}")

def get_real_weight():
    """
    獲取磅秤實際重量（優化版：使用連接快取）
    
    優化說明：
    - 使用 @st.cache_resource 快取串口連接，避免頻繁開關
    - 連接會在 Streamlit session 期間保持開啟
    - 自動檢測連接狀態，連接失敗時自動重連
    - 完全向後相容，不影響現有功能
    """
    # 模擬模式 check
    if config.USE_SIMULATION:
        val = round(random.uniform(24.5, 25.5), 2)
        return val, "模擬數據 (測試用)"

    # 嘗試使用快取的連接
    ser = get_serial_connection()
    
    if ser is None:
        # 如果連接失敗，清除快取並重試一次
        try:
            get_serial_connection.clear()
            ser = get_serial_connection()
        except Exception:
            pass
        
        if ser is None:
            return 0.0, "連線失敗: 無法建立串口連接"
    
    # 檢查連接是否仍然有效
    try:
        if not ser.is_open:
            # 連接已關閉，清除快取並重新連接
            try:
                get_serial_connection.clear()
                ser = get_serial_connection()
            except Exception:
                pass
            
            if ser is None:
                return 0.0, "連線失敗: 串口連接已關閉"
    except (AttributeError, serial.SerialException):
        # 連接狀態檢查失敗，清除快取並重新連接
        try:
            get_serial_connection.clear()
            ser = get_serial_connection()
        except Exception:
            pass
        
        if ser is None:
            return 0.0, "連線失敗: 串口連接異常"
    
    # 嘗試讀取數據
    try:
        return _read_weight_from_serial(ser)
    except ConnectionError as e:
        # 連接錯誤，清除快取以便下次重連
        try:
            get_serial_connection.clear()
        except Exception:
            pass
        return 0.0, f"連線失敗: {str(e)}"
    except serial.SerialException as e:
        # 串口異常，清除快取以便下次重連
        try:
            get_serial_connection.clear()
        except Exception:
            pass
        return 0.0, f"串口錯誤: {str(e)}"
    except Exception as e:
        return 0.0, f"讀取失敗: {str(e)}"

# ==========================================
# 2. 核心功能：工單排序 (對應 main.py Line 160, 195...)
# ==========================================
def normalize_sequences(df):
    """
    依照產線分組，重新編號排程順序 (1, 2, 3...)
    """
    if df.empty or "排程順序" not in df.columns or "產線" not in df.columns:
        return df
    
    # 先依照產線和舊順序排序
    df = df.sort_values(by=["產線", "排程順序"])
    
    # 重新產生流水號
    df["排程順序"] = df.groupby("產線").cumcount() + 1
    return df

# ==========================================
# 3. 核心功能：產線狀態存取 (對應 main.py Line 196, 318...)
# ==========================================
def _lock_file(file_handle):
    """鎖定檔案（跨平台）"""
    try:
        if sys.platform == 'win32' and msvcrt:
            # Windows 使用 msvcrt
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
        elif fcntl:
            # Unix/Linux 使用 fcntl
            fcntl.flock(file_handle, fcntl.LOCK_EX)
    except Exception:
        pass  # 如果鎖定失敗，繼續執行（避免阻塞）

def _unlock_file(file_handle):
    """解鎖檔案（跨平台）"""
    try:
        if sys.platform == 'win32' and msvcrt:
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
        elif fcntl:
            fcntl.flock(file_handle, fcntl.LOCK_UN)
    except Exception:
        pass

def load_line_statuses(max_retries=3, retry_delay=0.1):
    """
    讀取 JSON 狀態檔（帶重試機制和檔案鎖定）
    
    參數:
        max_retries: 最大重試次數（預設 3 次）
        retry_delay: 重試間隔（秒，預設 0.1 秒）
    """
    file_path = config.FILE_LINE_STATUS
    
    # 如果檔案不存在，返回空字典
    if not os.path.exists(file_path):
        return {}
    
    for attempt in range(max_retries):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                _lock_file(f)
                try:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
                finally:
                    _unlock_file(f)
        except (json.JSONDecodeError, IOError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                print(f"⚠️ 讀取狀態檔失敗（已重試 {max_retries} 次）：{e}")
                return {}
        except Exception as e:
            print(f"⚠️ 讀取狀態檔時發生未預期錯誤：{e}")
            return {}
    
    return {}

def save_line_status(status_data, max_retries=3, retry_delay=0.1):
    """
    寫入 JSON 狀態檔（帶重試機制和檔案鎖定）
    
    參數:
        status_data: 要儲存的狀態資料
        max_retries: 最大重試次數（預設 3 次）
        retry_delay: 重試間隔（秒，預設 0.1 秒）
    """
    file_path = config.FILE_LINE_STATUS
    
    # 確保目錄存在
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    except Exception:
        pass
    
    for attempt in range(max_retries):
        try:
            # 使用臨時檔案，然後原子性移動（避免寫入過程中檔案損壞）
            temp_path = file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                _lock_file(f)
                try:
                    json.dump(status_data, f, ensure_ascii=False, indent=4)
                    f.flush()
                    os.fsync(f.fileno())  # 強制寫入磁碟
                finally:
                    _unlock_file(f)
            
            # 原子性移動（Windows 上需要先刪除目標檔案）
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            os.rename(temp_path, file_path)
            return  # 成功
            
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                # 清理臨時檔案
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass
                continue
            else:
                print(f"⚠️ 狀態存檔失敗（已重試 {max_retries} 次）：{e}")
        except Exception as e:
            print(f"⚠️ 狀態存檔時發生未預期錯誤：{e}")
            # 清理臨時檔案
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            return

def save_current_work_order(line_name, work_order_label):
    """保存當前選擇的工單（用於當機恢復）"""
    try:
        status_data = load_line_statuses()
        if line_name not in status_data:
            status_data[line_name] = {}
        status_data[line_name]["current_work_order"] = work_order_label
        save_line_status(status_data)
    except Exception as e:
        print(f"保存當前工單失敗: {e}")

def load_current_work_order(line_name):
    """讀取當前選擇的工單（用於當機恢復）"""
    try:
        status_data = load_line_statuses()
        if line_name in status_data and "current_work_order" in status_data[line_name]:
            return status_data[line_name]["current_work_order"]
    except:
        pass
    return None

# ==========================================
# 4. 格式化工具 (對應 main.py 各處顯示邏輯)
# ==========================================

def get_p_label(val):
    """(對應 Line 368) 顯示密度選項，例如 64 -> 64P"""
    return f"{val}P"

def format_size(val):
    """(對應 Line 490) 格式化尺寸，去除多餘的 .0"""
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except:
        return str(val)

def safe_format_weight(val):
    """(對應 Line 774) 安全格式化重量"""
    try:
        if pd.isna(val) or val == "":
            return "0.000"
        return f"{float(val):.3f}"
    except:
        return "0.000"

def get_temp_color(temp_val):
    """(對應 Line 847) 根據溫度等級回傳顏色"""
    temp_str = str(temp_val)
    if "1260" in temp_str: return "#ffffff" # 白色
    if "1300" in temp_str: return "#3498db" # 藍色
    if "1200" in temp_str: return "#000000" # 黑色
    if "1400" in temp_str: return "#e67e22" # 橘色
    if "1500" in temp_str: return "#2ecc71" # 綠色
    if "BIO" in temp_str: return "#87CEEB"  # 天空藍
    return "#95a5a6" # 灰色

# ==========================================
# 5. 時間與班別工具 (對應 main.py Line 625, 628)
# ==========================================

def parse_log_time(time_str):
    """將字串轉為 datetime 物件"""
    try:
        return pd.to_datetime(time_str, errors='coerce')
    except:
        return datetime.datetime.now()

def get_shift_info_backup(dt_obj):
    """如果班別空白，根據時間自動判斷 (備用邏輯，往前推5分鐘)"""
    try:
        h = dt_obj.hour
        m = dt_obj.minute
        # 早班：07:55 - 15:59
        # 中班：15:55 - 23:59
        # 晚班：23:55 - 07:59
        if (h == 7 and m >= 55) or (8 <= h < 15) or (h == 15 and m < 55):
            return "早班"
        elif (h == 15 and m >= 55) or (16 <= h < 23) or (h == 23 and m < 55):
            return "中班"
        else:  # (h == 23 and m >= 55) or (0 <= h < 7) or (h == 7 and m < 55)
            return "晚班"
    except:
        return ""

def generate_lot_number(line_name, shift, group, dt=None):
    """
    生成 LOT 號碼
    格式：{產線}{年份末位}{月份}{日期}{班別}{組別}T
    例如：36011511T
    - 3 代表 LINE.3
    - 6 代表西曆 2026 的 6
    - 01 代表 1 月
    - 15 代表日期
    - 1 代表早班（2 為中班、3 為晚班）
    - 最後的 1 代表 A 組（2=B 組、3=C 組、4=D 組）
    - T 代表台灣
    考慮晚班跨日：晚班在 00:00-07:59 時段使用前一天日期
    """
    if dt is None:
        dt = datetime.datetime.now()
    
    # 根據班別和時間判斷日期（考慮晚班跨日）
    if shift == "晚班":
        hour = dt.hour
        minute = dt.minute
        # 晚班在 00:00-07:59 時段，使用前一天日期
        if (hour == 0) or (hour >= 1 and hour < 8) or (hour == 7 and minute < 55):
            adjusted_date = dt - datetime.timedelta(days=1)
            date_obj = adjusted_date
        else:
            date_obj = dt
    else:
        date_obj = dt
    
    # 產線編號（從 Line 1, Line 2 等提取數字）
    line_num = "".join(filter(str.isdigit, line_name)) or "0"
    
    # 年份末位數字（例如：2026 -> 6）
    year_last_digit = str(date_obj.year)[-1]
    
    # 月份（兩位數，例如：01, 02, ..., 12）
    month_str = date_obj.strftime("%m")
    
    # 日期（兩位數，例如：01, 02, ..., 31）
    day_str = date_obj.strftime("%d")
    
    # 班別代碼：早班=1, 中班=2, 晚班=3
    shift_code = {"早班": "1", "中班": "2", "晚班": "3"}.get(shift, "0")
    
    # 組別代碼：A=1, B=2, C=3, D=4
    group_code_map = {"A": "1", "B": "2", "C": "3", "D": "4"}
    group_code = group_code_map.get(str(group).upper(), "0")
    
    # 組合 LOT 號碼：{產線}{年份末位}{月份}{日期}{班別}{組別}T
    lot_number = f"{line_num}{year_last_digit}{month_str}{day_str}{shift_code}{group_code}T"
    
    return lot_number