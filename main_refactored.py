"""
產線秤重系統 - 主程式入口（重構版）
將原本 1075 行的 main.py 拆分為多個模組，方便維護
"""

import streamlit as st
from datetime import datetime
import config
import data_manager as dm
from data_loader import load_data, save_data
from ui_styles import load_styles
from pages.admin import render_admin_page
from pages.production import render_production_page

# ==========================================
# 系統設定 & 初始化
# ==========================================
st.set_page_config(page_title=config.PAGE_TITLE, layout=config.PAGE_LAYOUT)

# 載入樣式
load_styles()

# Toast 訊息處理
if 'toast_msg' in st.session_state and st.session_state.toast_msg:
    msg, icon_char = st.session_state.toast_msg
    if icon_char: 
        st.toast(msg, icon=icon_char)
    else: 
        st.toast(msg)
    st.session_state.toast_msg = None

# 檢查是否為單機模式，如果是則顯示警告或阻止啟動
if config.IS_STANDALONE_MODE:
    if config.BLOCK_STANDALONE_MODE:
        # 持續嘗試重新連線，而不是直接停止
        import subprocess
        import importlib
        
        # 初始化重試計數器
        if 'retry_count' not in st.session_state:
            st.session_state.retry_count = 0
        
        # 嘗試建立網路連線
        st.session_state.retry_count += 1
        
        try:
            # 先刪除舊連線
            subprocess.run(
                f'net use \\\\{config.SERVER_IP}\\IPC$ /delete /y',
                shell=True,
                capture_output=True,
                timeout=3
            )
            
            # 建立新連線
            result = subprocess.run(
                f'net use \\\\{config.SERVER_IP}\\IPC$ /user:test 0508 /persistent:yes',
                shell=True,
                capture_output=True,
                timeout=5
            )
            
            # 重新檢查伺服器連線
            import time
            time.sleep(2)
            
            # 重新檢查連線狀態
            if config.check_server_path(config.SERVER_PATH):
                # 重新載入 config 模組以更新 BASE_DIR 和 IS_STANDALONE_MODE
                importlib.reload(config)
                # 重新載入 db_schema 模組以更新資料庫路徑
                import db_schema
                importlib.reload(db_schema)
                # 清除 session_state 中的資料，強制重新載入
                if 'products_db' in st.session_state:
                    del st.session_state.products_db
                if 'work_orders_db' in st.session_state:
                    del st.session_state.work_orders_db
                if 'production_logs' in st.session_state:
                    del st.session_state.production_logs
                # 如果連線成功，重新載入頁面
                st.rerun()
                
        except Exception as e:
            pass
        
        # 顯示等待畫面
        st.error("""
        ⚠️ **無法連接到伺服器，系統正在嘗試重新連線...**
        
        **問題說明：**
        - 無法連接到伺服器 `{SERVER_PATH}`
        - 系統正在自動嘗試重新建立連線
        
        **已嘗試次數：** {RETRY_COUNT} 次
        
        **請檢查：**
        1. 網路連線是否正常
        2. 確認伺服器 `{SERVER_IP}` 是否正常運作
        3. 執行 `測試伺服器連線.bat` 進行診斷
        4. 檢查 `啟動系統.bat` 中的帳號密碼是否正確
        
        **系統將每 5 秒自動重試連線，請稍候...**
        """.format(SERVER_PATH=config.SERVER_PATH, SERVER_IP=config.SERVER_IP, RETRY_COUNT=st.session_state.retry_count))
        
        # 使用自動重新執行來持續檢查（每 5 秒）
        import time
        time.sleep(5)
        st.rerun()
    else:
        # 顯示警告但允許繼續使用
        st.warning("""
        ⚠️ **警告：系統目前處於單機模式**
        
        **問題說明：**
        - 無法連接到伺服器 `{SERVER_PATH}`
        - 系統將使用本機資料庫，資料可能無法與其他工作站同步
        
        **請立即處理：**
        1. 檢查網路連線是否正常
        2. 確認伺服器 `{SERVER_IP}` 是否正常運作
        3. 執行 `測試伺服器連線.bat` 進行診斷
        4. 聯繫 IT 人員協助排除連線問題
        
        **注意：** 在單機模式下，您的資料可能無法與其他產線同步，請謹慎使用！
        """.format(SERVER_PATH=config.SERVER_PATH, SERVER_IP=config.SERVER_IP))

# ==========================================
# 主選單 & 頁面邏輯
# ==========================================
with st.sidebar:
    st.markdown("### 🏭 產線系統 v18.55")
    menu = st.radio("功能導航", ["現場：產線秤重作業", "後台：系統管理中心"])
    st.divider()
    if 'locked_station' not in st.session_state: 
        st.session_state.locked_station = "總覽模式 (所有產線)"
    station_options = ["總覽模式 (所有產線)"] + config.PRODUCTION_LINES
    selected_station = st.selectbox("📍 鎖定本機工作站", station_options, key="locked_station")
    st.info(f"目前顯示：{selected_station}")

# 根據頁面決定如何載入資料（優化：管理頁面不重新載入工單資料，避免輸入時頻繁刷新）
if menu == "後台：系統管理中心":
    # 管理頁面：只在首次載入時載入工單資料，避免輸入時頻繁刷新
    # [關鍵修正] 產品資料也改為只在首次載入時載入，避免覆蓋正在編輯的資料
    from data_loader import get_connection
    from db_schema import init_database
    import pandas as pd
    
    # [關鍵修正] 添加錯誤處理，避免連線失敗導致應用程式崩潰
    try:
        init_database()
        conn = get_connection()
    except Exception as e:
        st.error(f"⚠️ **無法連接到資料庫：{str(e)}**")
        st.info("""
        **請檢查：**
        1. 網路連線是否正常
        2. 伺服器是否正常運作
        3. 執行 `測試伺服器連線.bat` 進行診斷
        
        **系統將在 5 秒後自動重新載入頁面...**
        """)
        import time
        time.sleep(5)
        st.rerun()
        st.stop()  # 停止執行，避免後續程式碼執行
    
    # [關鍵修正] 只在 products_db 不存在時才載入，避免覆蓋正在編輯的資料
    # 這樣可以確保新增產品後，資料不會被重新載入覆蓋
    if 'products_db' not in st.session_state:
        try:
            query = "SELECT 產品ID, 客戶名, 溫度等級, 品種, 密度, 長, 寬, 高, 下限, 準重, 上限, 備註1, 備註2, 備註3 FROM products"
            st.session_state.products_db = pd.read_sql_query(query, conn)
            
            # 清理備註欄位中的 HTML 標籤
            import re
            def clean_note_field(val):
                if pd.isna(val) or str(val).lower() == 'none':
                    return ""
                val_str = str(val)
                # 先移除所有 HTML 標籤（包括 </div>、<div> 等）
                val_str = re.sub(r'<[^>]+>', '', val_str)
                # 移除所有殘留的 < 和 > 字符（處理不完整的標籤）
                val_str = val_str.replace('<', '').replace('>', '')
                return val_str.strip()
            
            for note_col in ['備註1', '備註2', '備註3']:
                if note_col in st.session_state.products_db.columns:
                    st.session_state.products_db[note_col] = st.session_state.products_db[note_col].apply(clean_note_field)
        except Exception as e:
            print(f"載入產品資料時發生錯誤: {e}")
            st.session_state.products_db = pd.DataFrame(columns=[
                "產品ID", "客戶名", "溫度等級", "品種", "密度", "長", "寬", "高", 
                "下限", "準重", "上限", "備註1", "備註2", "備註3"
            ])
    
    # 工單資料：只在首次載入時載入，避免輸入時頻繁刷新
    if 'work_orders_db' not in st.session_state:
        try:
            query = f"SELECT {', '.join(config.ORDER_COLUMNS)} FROM work_orders ORDER BY 產線, 排程順序"
            st.session_state.work_orders_db = pd.read_sql_query(query, conn)
            # 確保所有必要欄位存在
            for col in config.ORDER_COLUMNS:
                if col not in st.session_state.work_orders_db.columns: 
                    st.session_state.work_orders_db[col] = ""
            # 轉換數值欄位
            for col in ["排程順序", "預計數量", "已完成數量"]:
                if col in st.session_state.work_orders_db.columns:
                    st.session_state.work_orders_db[col] = pd.to_numeric(
                        st.session_state.work_orders_db[col], errors='coerce'
                    ).fillna(0).astype(int)
            # 正規化排序
            st.session_state.work_orders_db = dm.normalize_sequences(st.session_state.work_orders_db)
        except Exception as e:
            print(f"載入工單資料時發生錯誤: {e}")
            st.session_state.work_orders_db = pd.DataFrame(columns=config.ORDER_COLUMNS)
    
    # 載入生產紀錄（只在首次載入時）
    if 'production_logs' not in st.session_state:
        try:
            query = f"SELECT {', '.join(config.LOG_COLUMNS)} FROM production_logs ORDER BY 時間 DESC"
            st.session_state.production_logs = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"載入生產紀錄時發生錯誤: {e}")
            st.session_state.production_logs = pd.DataFrame(columns=config.LOG_COLUMNS)
        
        # 確保所有必要欄位存在並設定預設值
        for col in config.LOG_COLUMNS:
            if col not in st.session_state.production_logs.columns: 
                if col == "組別": 
                    st.session_state.production_logs[col] = "A"
                elif col == "班別": 
                    st.session_state.production_logs[col] = ""
                elif col == "操作員": 
                    st.session_state.production_logs[col] = ""
                else: 
                    st.session_state.production_logs[col] = ""
    
    # 初始化已保存的記錄計數器（用於增量更新）
    if 'production_logs_saved_count' not in st.session_state:
        st.session_state['production_logs_saved_count'] = len(st.session_state.production_logs) if not st.session_state.production_logs.empty else 0
    
    try:
        conn.close()
    except:
        pass
    
    # 載入產線狀態
    try:
        all_line_statuses = dm.load_line_statuses()
    except Exception as e:
        print(f"載入產線狀態時發生錯誤: {e}")
        all_line_statuses = {}
    
    # 渲染管理頁面
    try:
        render_admin_page()
    except Exception as e:
        st.error(f"⚠️ **渲染管理頁面時發生錯誤：{str(e)}**")
        st.info("系統將在 5 秒後自動重新載入頁面...")
        import time
        time.sleep(5)
        st.rerun()

elif menu == "現場：產線秤重作業":
    # 生產頁面：每次都載入資料（確保資料最新）
    # 生產頁面有 fragment 自動刷新，所以這裡主要是初始化
    try:
        load_data()
    except Exception as e:
        st.error(f"⚠️ **載入資料時發生錯誤：{str(e)}**")
        st.info("""
        **請檢查：**
        1. 網路連線是否正常
        2. 伺服器是否正常運作
        3. 執行 `測試伺服器連線.bat` 進行診斷
        
        **系統將在 5 秒後自動重新載入頁面...**
        """)
        import time
        time.sleep(5)
        st.rerun()
        st.stop()  # 停止執行，避免後續程式碼執行
    
    try:
        all_line_statuses = dm.load_line_statuses()
    except Exception as e:
        print(f"載入產線狀態時發生錯誤: {e}")
        all_line_statuses = {}
    
    # 渲染生產頁面
    try:
        render_production_page(all_line_statuses)
    except Exception as e:
        st.error(f"⚠️ **渲染生產頁面時發生錯誤：{str(e)}**")
        st.info("系統將在 5 秒後自動重新載入頁面...")
        import time
        time.sleep(5)
        st.rerun()

