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
        # 完全阻止啟動
        st.error("""
        ⚠️ **錯誤：無法連接到伺服器，系統無法啟動**
        
        **問題說明：**
        - 無法連接到伺服器 `{SERVER_PATH}`
        - 系統必須連接到伺服器才能正常運作
        
        **請立即處理：**
        1. 檢查網路連線是否正常
        2. 確認伺服器 `{SERVER_IP}` 是否正常運作
        3. 執行 `測試伺服器連線.bat` 進行診斷
        4. 檢查 `啟動系統.bat` 中的帳號密碼是否正確
        5. 聯繫 IT 人員協助排除連線問題
        
        **系統已停止啟動，請解決連線問題後重新啟動程式。**
        """.format(SERVER_PATH=config.SERVER_PATH, SERVER_IP=config.SERVER_IP))
        st.stop()
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

# 載入資料
load_data()
all_line_statuses = dm.load_line_statuses()

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

# 根據選單載入對應頁面
if menu == "後台：系統管理中心":
    render_admin_page()

elif menu == "現場：產線秤重作業":
    render_production_page(all_line_statuses)

