"""
現場作業頁面模組
包含產線秤重作業、工單管理、生產監控等功能
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import textwrap
import time
import math
import html
import re

import config
import data_manager as dm
from data_loader import save_data, reload_work_orders
from dialogs import show_end_shift_dialog, show_start_shift_dialog, show_undo_confirm, show_finish_work_order_confirm


def generate_lot_number(line_name, shift, group):
    """
    生成 LOT 編號
    格式：LINE + 年份最後一位 + 月份 + 日期 + 班別 + 組別 + T
    範例：36010814T
    - 3 = LINE3
    - 6 = 2026年（只取最後一位）
    - 01 = 1月
    - 08 = 當日日期（晚班在00:00-07:59使用前一天日期）
    - 1 = 班別（早班=1、中班=2、晚班=3）
    - 4 = 組別（A=1、B=2、C=3、D=4）
    - T = 台灣 (TAIWAN)
    """
    from datetime import timedelta
    
    # 提取產線編號（從 "Line 3" 提取 "3"）
    line_num = line_name.replace("Line ", "").strip()
    
    # 取得當前日期時間
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # 根據班別和時間判斷日期
    # 晚班在 00:00-07:59 開班時，使用前一天日期
    if shift == "晚班" and ((current_hour == 0) or (current_hour >= 1 and current_hour < 8) or (current_hour == 7 and current_minute < 55)):
        # 晚班在凌晨時段，日期減一天
        lot_date = now - timedelta(days=1)
    else:
        # 早班、中班，或晚班在 23:55-23:59 開班，使用當天日期
        lot_date = now
    
    year = str(lot_date.year)[-1]  # 年份最後一位（例如 2026 → "6"，2027 → "7"）
    month = f"{lot_date.month:02d}"  # 月份，兩位數
    day = f"{lot_date.day:02d}"      # 日期，兩位數
    
    # 班別轉換
    shift_map = {"早班": "1", "中班": "2", "晚班": "3"}
    shift_num = shift_map.get(shift, "1")
    
    # 組別轉換
    group_map = {"A": "1", "B": "2", "C": "3", "D": "4"}
    group_num = group_map.get(group, "1")
    
    # 組合 LOT 編號，最後加上 T 代表台灣
    lot_number = f"{line_num}{year}{month}{day}{shift_num}{group_num}T"
    
    return lot_number


def render_production_page(all_line_statuses):
    """渲染現場作業頁面"""
    st.markdown('<div class="custom-main-title">🏭 現場作業儀表板</div>', unsafe_allow_html=True)
    
    # [新增] 定期重新載入工單資料，確保平板能即時同步伺服器新增的工單
    # 每 5 秒重新載入一次（避免過於頻繁影響效能）
    @st.fragment(run_every=5)
    def refresh_work_orders():
        reload_work_orders()
    
    refresh_work_orders()
    
    if st.session_state.locked_station == "總覽模式 (所有產線)": 
        lines_to_show = config.PRODUCTION_LINES
    else: 
        lines_to_show = [st.session_state.locked_station]
    op_tabs = st.tabs(lines_to_show)
    
    wo_std_map = st.session_state.work_orders_db.set_index("工單號碼")["準重"].to_dict()

    STABLE_TOLERANCE = 0.15  # [優化] 從 0.2 減少到 0.15，加快穩定判斷
    QUICK_STABLE_TIME = 0.15  # [優化] 從 0.3 減少到 0.15 秒，加快穩定判斷
    HOLD_RELEASE_DIFF = 0.1
    RESET_THRESHOLD = 0.5
    
    # [關鍵修正] 不良品(廢料)重量範圍設定
    NG_MIN = 10.0
    NG_MAX = 10.5

    for i, line_name in enumerate(lines_to_show):
        with op_tabs[i]:
            render_production_line(
                line_name, 
                all_line_statuses, 
                wo_std_map,
                STABLE_TOLERANCE,
                QUICK_STABLE_TIME,
                HOLD_RELEASE_DIFF,
                RESET_THRESHOLD,
                NG_MIN,
                NG_MAX
            )


def render_production_line(line_name, all_line_statuses, wo_std_map, 
                          STABLE_TOLERANCE, QUICK_STABLE_TIME, HOLD_RELEASE_DIFF, 
                          RESET_THRESHOLD, NG_MIN, NG_MAX):
    """渲染單一產線的作業界面"""
    current_status = all_line_statuses.get(line_name, {"active": False, "shift": "早班", "group": "A"})
    is_active = current_status.get("active", False)
    cur_s = current_status.get("shift", "早班")
    cur_g = current_status.get("group", "A")

    if f"lock_{line_name}" not in st.session_state: 
        st.session_state[f"lock_{line_name}"] = False
    if f"hist_{line_name}" not in st.session_state: 
        st.session_state[f"hist_{line_name}"] = []
    if f"stable_start_{line_name}" not in st.session_state: 
        st.session_state[f"stable_start_{line_name}"] = None
    if f"auto_held_val_{line_name}" not in st.session_state: 
        st.session_state[f"auto_held_val_{line_name}"] = None

    if is_active:
        render_active_line(line_name, cur_s, cur_g, wo_std_map, 
                          STABLE_TOLERANCE, QUICK_STABLE_TIME, HOLD_RELEASE_DIFF, 
                          RESET_THRESHOLD, NG_MIN, NG_MAX, all_line_statuses)
    else:
        render_idle_line(line_name, all_line_statuses)


def render_active_line(line_name, cur_s, cur_g, wo_std_map,
                      STABLE_TOLERANCE, QUICK_STABLE_TIME, HOLD_RELEASE_DIFF,
                      RESET_THRESHOLD, NG_MIN, NG_MAX, all_line_statuses):
    """渲染活動中的產線界面"""
    # 生成 LOT 編號
    lot_number = generate_lot_number(line_name, cur_s, cur_g)
    
    st.markdown(f"""
    <div class="shift-card">
        <div class="shift-title">📍 {line_name} 生產監控中</div>
        <div><span class="shift-badge">LOT：{lot_number}</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    dialog_key = f"dialog_open_{line_name}"
    dialog_closed_key = f"dialog_closed_{line_name}"
    
    # 檢查是否應該清除 dialog 標記（用戶關閉了 dialog）
    # 必須在檢查 dialog_key 和顯示 dialog 之前執行，確保狀態正確
    if st.session_state.get(dialog_closed_key, False):
        # 先清除 dialog_key，防止 dialog 顯示
        st.session_state[dialog_key] = False
        # 清除相關狀態，防止殘留
        if f"p_conf_{line_name}" in st.session_state:
            del st.session_state[f"p_conf_{line_name}"]
        if f"p_val_{line_name}" in st.session_state:
            del st.session_state[f"p_val_{line_name}"]
        if f"p_zero_{line_name}" in st.session_state:
            del st.session_state[f"p_zero_{line_name}"]
        # 最後清除 dialog_closed_key，準備下次使用
        st.session_state[dialog_closed_key] = False
    
    if st.button(f"🏁 結算下班 (End Shift)", key=f"btn_end_{line_name}", width='stretch', type="primary"):
        if f"p_conf_{line_name}" in st.session_state: 
            del st.session_state[f"p_conf_{line_name}"]
        st.session_state[dialog_key] = True
        st.session_state[dialog_closed_key] = False  # 重置關閉標記
        st.rerun()

    # 只有在 dialog_key 為 True 且 dialog_closed_key 不為 True 時才顯示 dialog
    # 三重檢查，確保不會在關閉後重新顯示
    should_show_dialog = (
        st.session_state.get(dialog_key, False) and 
        not st.session_state.get(dialog_closed_key, False)
    )
    
    if should_show_dialog:
        show_end_shift_dialog(line_name, cur_s, cur_g, all_line_statuses)
    else:
        # 如果 dialog_key 為 False，確保 dialog_closed_key 也是 False（清理狀態）
        if not st.session_state.get(dialog_key, False):
            st.session_state[dialog_closed_key] = False
    st.divider()

    mask = (st.session_state.work_orders_db["狀態"].isin(["待生產", "生產中"])) & (st.session_state.work_orders_db["產線"] == line_name)
    pending = st.session_state.work_orders_db[mask].sort_values(by="排程順序")
    
    if not pending.empty:
        if not st.session_state.products_db.empty: 
            p_db = st.session_state.products_db.copy()
            queue_view = pending.merge(p_db, on="產品ID", how="left")
        else: 
            queue_view = pending.copy()
        
        queue_view["temp_sort"] = range(1, len(queue_view) + 1)
        def make_label(row):
            if "客戶名" in row and pd.notna(row["客戶名"]):
                spec = f"{dm.format_size(row['長'])}x{dm.format_size(row['寬'])}x{dm.format_size(row['高'])}"
                # 從 products_db 中取得密度值
                density_str = ""
                product_id = row.get("產品ID", "")
                if product_id and not st.session_state.products_db.empty:
                    product_match = st.session_state.products_db[st.session_state.products_db["產品ID"] == product_id]
                    if not product_match.empty and "密度" in product_match.columns:
                        density_val = product_match.iloc[0]["密度"]
                        if pd.notna(density_val) and str(density_val).strip() != "":
                            try:
                                density_str = f"{float(density_val):.1f} | "
                            except (ValueError, TypeError):
                                density_str = f"{density_val} | "
                return f"#{row['temp_sort']} {row['客戶名']} | {row['溫度等級']} | {row['品種_x']} | {density_str}{spec} | {float(row['準重_x']):.3f}kg (數:{int(row['預計數量'])})"
            else: 
                return f"#{row['temp_sort']} {str(row['顯示內容'])} (數:{int(row['預計數量'])})"
        
        queue_view["選單顯示"] = queue_view.apply(make_label, axis=1)
        options_list = queue_view["選單顯示"].tolist()
        
        col_sel, col_finish_btn = st.columns([3, 1])
        with col_sel:
            key_sel = f"sel_wo_{line_name}" 
            # [當機恢復] 優先從持久化存儲恢復，如果沒有則使用 session_state
            saved_wo_label = dm.load_current_work_order(line_name)
            
            # [交接班優化] 如果保存的工單不在當前列表中，優先選擇"生產中"的工單
            if saved_wo_label and saved_wo_label not in options_list:
                # 優先選擇"生產中"的工單
                try:
                    producing_mask = queue_view["狀態"] == "生產中"
                    if producing_mask.any():
                        producing_queue = queue_view[producing_mask]
                        if not producing_queue.empty:
                            producing_item = producing_queue.iloc[0]
                            producing_label = queue_view[queue_view["工單號碼"] == producing_item["工單號碼"]]["選單顯示"].iloc[0]
                            if producing_label in options_list:
                                saved_wo_label = producing_label
                                dm.save_current_work_order(line_name, producing_label)
                            else:
                                saved_wo_label = None
                                dm.save_current_work_order(line_name, None)
                        else:
                            saved_wo_label = None
                            dm.save_current_work_order(line_name, None)
                    else:
                        saved_wo_label = None
                        dm.save_current_work_order(line_name, None)
                except Exception as e:
                    saved_wo_label = None
                    dm.save_current_work_order(line_name, None)
            
            # 初始化 session_state（只在第一次或需要恢復時）
            if key_sel not in st.session_state:
                if saved_wo_label and saved_wo_label in options_list:
                    st.session_state[key_sel] = saved_wo_label
                elif options_list:
                    # [交接班優化] 優先選擇"生產中"的工單
                    try:
                        producing_mask = queue_view["狀態"] == "生產中"
                        if producing_mask.any():
                            producing_queue = queue_view[producing_mask]
                            if not producing_queue.empty:
                                producing_item = producing_queue.iloc[0]
                                producing_label = queue_view[queue_view["工單號碼"] == producing_item["工單號碼"]]["選單顯示"].iloc[0]
                                if producing_label in options_list:
                                    st.session_state[key_sel] = producing_label
                                else:
                                    st.session_state[key_sel] = options_list[0]
                            else:
                                st.session_state[key_sel] = options_list[0]
                        else:
                            st.session_state[key_sel] = options_list[0]
                    except:
                        st.session_state[key_sel] = options_list[0]
            
            # 確保 session_state 中的值在選項列表中
            if key_sel in st.session_state and st.session_state[key_sel] not in options_list:
                if options_list:
                    # [交接班優化] 優先選擇"生產中"的工單
                    try:
                        producing_mask = queue_view["狀態"] == "生產中"
                        if producing_mask.any():
                            producing_queue = queue_view[producing_mask]
                            if not producing_queue.empty:
                                producing_item = producing_queue.iloc[0]
                                producing_label = queue_view[queue_view["工單號碼"] == producing_item["工單號碼"]]["選單顯示"].iloc[0]
                                if producing_label in options_list:
                                    st.session_state[key_sel] = producing_label
                                else:
                                    st.session_state[key_sel] = options_list[0]
                            else:
                                st.session_state[key_sel] = options_list[0]
                        else:
                            st.session_state[key_sel] = options_list[0]
                    except:
                        st.session_state[key_sel] = options_list[0]
                else:
                    st.session_state[key_sel] = None
            
            # 使用 selectbox，讓 Streamlit 自動管理狀態
            if options_list:
                wo_label = st.selectbox("👇 切換當前任務", options=options_list, key=key_sel)
                
                # [當機恢復] 當工單選擇改變時，立即保存到持久化存儲
                if wo_label != saved_wo_label:
                    dm.save_current_work_order(line_name, wo_label)
            else:
                wo_label = None
                st.info("暫無待生產工單")
        
        # 確保 wo_label 有效
        if wo_label and not queue_view.empty:
            curr_row_list = queue_view[queue_view["選單顯示"] == wo_label]
            if not curr_row_list.empty: 
                curr = curr_row_list.iloc[0]
            else: 
                curr = queue_view.iloc[0]
        elif not queue_view.empty:
            curr = queue_view.iloc[0]
        else:
            curr = None

        if curr is not None:
            # 結束工單對話框狀態初始化
            finish_dialog_key = f"finish_wo_dialog_{line_name}"
            finish_dialog_closed_key = f"finish_wo_dialog_closed_{line_name}"
            finish_wo_id_key = f"finish_wo_id_{line_name}"
            finish_wo_info_key = f"finish_wo_info_{line_name}"
            
            # 初始化對話框狀態
            if finish_dialog_key not in st.session_state:
                st.session_state[finish_dialog_key] = False
            if finish_dialog_closed_key not in st.session_state:
                st.session_state[finish_dialog_closed_key] = False
            
            # 檢查是否應該清除 dialog 標記（用戶之前關閉了它）
            if st.session_state.get(finish_dialog_closed_key, False):
                st.session_state[finish_dialog_key] = False
                st.session_state[finish_dialog_closed_key] = False
            
            with col_finish_btn:
                st.write(""); st.write("") 
                if st.button("🏁 結束當前工單", type="primary", width='stretch', key=f"fin_{line_name}"):
                    # 保存工單資訊以便對話框使用
                    wo_id = curr["工單號碼"]
                    wo_info = curr.get("顯示內容", wo_id)
                    
                    st.session_state[finish_wo_id_key] = wo_id
                    st.session_state[finish_wo_info_key] = wo_info
                    
                    # 打開確認對話框
                    st.session_state[finish_dialog_key] = True
                    st.session_state[finish_dialog_closed_key] = False
                    st.rerun()
            
            # 顯示確認對話框（在按鈕區塊之外，確保對話框能正確顯示）
            should_show_finish_dialog = (
                st.session_state.get(finish_dialog_key, False) and 
                not st.session_state.get(finish_dialog_closed_key, False)
            )
            
            if should_show_finish_dialog:
                wo_id = st.session_state.get(finish_wo_id_key)
                wo_info = st.session_state.get(finish_wo_info_key)
                if wo_id:
                    show_finish_work_order_confirm(line_name, wo_id, wo_info)

            # 工單列表表格（智能刷新：有新數據時快速刷新，否則慢速刷新，與紀錄歷程同步）
            # 先定義內部函數，確保在調用前已定義
            def render_queue_table_internal(q_view, current_item, line_n):
                # 重新讀取最新的工單數據，確保進度是最新的
                try:
                    latest_pending = st.session_state.work_orders_db[
                        (st.session_state.work_orders_db["狀態"].isin(["待生產", "生產中"])) & 
                        (st.session_state.work_orders_db["產線"] == line_n)
                    ].sort_values(by="排程順序")
                    
                    if not latest_pending.empty and not st.session_state.products_db.empty:
                        latest_queue = latest_pending.merge(st.session_state.products_db, on="產品ID", how="left")
                    else:
                        latest_queue = latest_pending.copy() if not latest_pending.empty else q_view
                    
                    latest_queue["temp_sort"] = range(1, len(latest_queue) + 1)
                except:
                    latest_queue = q_view
                
                q_df = pd.DataFrame()
                q_df["序"] = range(1, len(latest_queue) + 1)
                if "客戶名" in latest_queue.columns:
                    q_df["客戶"] = latest_queue["客戶名"]
                    q_df["溫度"] = latest_queue["溫度等級"].astype(str)
                    q_df["品種"] = latest_queue["品種_x"]
                    
                    # [優化] 預先建立密度對照表，避免重複查詢 DataFrame
                    # 使用向量化操作建立對照表
                    if not st.session_state.products_db.empty and "產品ID" in st.session_state.products_db.columns and "密度" in st.session_state.products_db.columns:
                        density_df = st.session_state.products_db[["產品ID", "密度"]].copy()
                        density_df = density_df[density_df["密度"].notna()]
                        def format_density(x):
                            """安全地格式化密度值"""
                            if pd.isna(x):
                                return ""
                            x_str = str(x).strip()
                            if x_str == "" or x_str.upper() == "N/A":
                                return ""
                            try:
                                return f"{float(x):.1f}"
                            except (ValueError, TypeError):
                                return ""
                        density_df["密度"] = density_df["密度"].apply(format_density)
                        density_map = dict(zip(density_df["產品ID"], density_df["密度"]))
                    else:
                        density_map = {}
                    
                    # [優化] 使用 map 取代 apply，提升效能
                    q_df["密度"] = latest_queue["產品ID"].map(density_map).fillna("")
                    
                    # [優化] 向量化規格處理
                    q_df["規格"] = (latest_queue["長"].apply(dm.format_size) + "x" + 
                                   latest_queue["寬"].apply(dm.format_size) + "x" + 
                                   latest_queue["高"].apply(dm.format_size))
                    
                    if "下限" in latest_queue.columns: 
                        q_df["下限"] = latest_queue["下限"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "")
                    else: 
                        q_df["下限"] = ""
                    q_df["準重"] = latest_queue["準重_x"].apply(dm.safe_format_weight)
                    if "上限" in latest_queue.columns: 
                        q_df["上限"] = latest_queue["上限"].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "")
                    else: 
                        q_df["上限"] = ""
                    for note_col in ['備註1', '備註2', '備註3']:
                        if note_col in latest_queue.columns: 
                            # 清理備註內容：移除 HTML 標籤並處理特殊字符
                            def clean_note(x):
                                if pd.isna(x) or str(x).lower() == 'none':
                                    return ""
                                val_str = str(x)
                                # 先移除任何 HTML 標籤
                                val_str = re.sub(r'<[^>]+>', '', val_str)
                                # 移除多餘的空白字符
                                val_str = val_str.strip()
                                return val_str
                            q_df[note_col] = latest_queue[note_col].apply(clean_note)
                        else: 
                            q_df[note_col] = ""
                    # [優化] 向量化進度計算
                    q_df["進度"] = (latest_queue["已完成數量"].astype(str) + " / " + 
                                   latest_queue["預計數量"].astype(str))
                else: 
                    q_df["內容"] = latest_queue["詳細規格字串"]
                    # [優化] 向量化進度計算
                    q_df["進度"] = (latest_queue["已完成數量"].astype(str) + " / " + 
                                   latest_queue["預計數量"].astype(str))

                if "內容" in q_df.columns: 
                    cols = ["序", "內容", "進度"]
                else: 
                    cols = ["序", "客戶", "溫度", "品種", "密度", "規格", "下限", "準重", "上限", "備註1", "備註2", "備註3", "進度"]
                
                html_q = '<div class="table-scroll-container"><table class="styled-table"><thead><tr>'
                for c in cols: 
                    html_q += f'<th>{c}</th>'
                html_q += '</tr></thead><tbody>'
                # [優化] 使用 itertuples 取代 iterrows，提升效能 10-100 倍
                for row in q_df.itertuples():
                    is_active = (row.序 == current_item["temp_sort"])
                    row_style = 'style="background-color: #d6eaf8; border-left: 5px solid #3498db;"' if is_active else ''
                    html_q += f'<tr {row_style}>'
                    for c in cols:
                        # 使用 getattr 取得屬性值（itertuples 使用屬性而非字典）
                        val = getattr(row, c, "")
                        # HTML 轉義，防止 HTML 標籤破壞格式
                        # 對於備註欄位，先清理再轉義
                        if c in ["備註1", "備註2", "備註3"]:
                            # 備註欄位：先清理 HTML 標籤，再轉義
                            val_str = str(val) if val else ""
                            # 移除任何殘留的 HTML 標籤（雙重保護）
                            val_str = re.sub(r'<[^>]+>', '', val_str)
                            # HTML 轉義
                            val_escaped = html.escape(val_str)
                            # 將換行符轉換為 <br> 標籤（在轉義後）
                            val_escaped = val_escaped.replace('\n', '<br>').replace('\r', '')
                        else:
                            val_escaped = html.escape(str(val)) if val else ""
                        val_display = f"<strong>{val_escaped}</strong>" if is_active else f"{val_escaped}"
                        # 修正：使用雙引號包裹 style 屬性，避免與外層單引號衝突
                        td_style = 'style="max-width: 120px; white-space: normal; word-wrap: break-word; word-break: break-all; color: #d35400;"' if c in ["備註1", "備註2", "備註3"] else ""
                        html_q += f'<td {td_style}>{val_display}</td>'
                    html_q += '</tr>'
                html_q += '</tbody></table></div>'
                st.markdown(html_q, unsafe_allow_html=True)
            
            # 工單列表表格（智能刷新：有新數據時快速刷新，否則慢速刷新，與紀錄歷程同步）
            has_new_log_queue = st.session_state.get(f"new_log_{line_name}", False)
            
            if has_new_log_queue:
                # 有新數據時，使用快速刷新（0.5 秒）
                @st.fragment(run_every=0.5)  # [優化] 從 0.3 秒改為 0.5 秒，減少伺服器負載和連線檢查頻率
                def render_queue_table_fast(q_view, current_item, line_n):
                    # 清除標記，下次使用慢速刷新
                    if st.session_state.get(f"new_log_{line_n}", False):
                        st.session_state[f"new_log_{line_n}"] = False
                    render_queue_table_internal(q_view, current_item, line_n)
                render_queue_table_fast(queue_view, curr, line_name)
            else:
                # 沒有新數據時，使用慢速刷新（10 秒）
                @st.fragment(run_every=10.0)
                def render_queue_table_slow(q_view, current_item, line_n):
                    render_queue_table_internal(q_view, current_item, line_n)
                render_queue_table_slow(queue_view, curr, line_name)
            
            st.divider()

            # 檢查是否應該顯示撤銷對話框（在 fragment 外部）
            undo_dialog_key = f"undo_dialog_{line_name}"
            undo_dialog_closed_key = f"undo_dialog_closed_{line_name}"
            
            if undo_dialog_key not in st.session_state:
                st.session_state[undo_dialog_key] = False
            if undo_dialog_closed_key not in st.session_state:
                st.session_state[undo_dialog_closed_key] = False
            
            # 檢查是否應該清除 dialog 標記（用戶關閉了 dialog）
            if st.session_state.get(undo_dialog_closed_key, False):
                st.session_state[undo_dialog_key] = False
                st.session_state[undo_dialog_closed_key] = False
            
            if st.session_state[undo_dialog_key]:
                show_undo_confirm(line_name, cur_s, cur_g)
                # 如果完成操作，關閉對話框
                if f"undo_completed_{line_name}" in st.session_state and st.session_state[f"undo_completed_{line_name}"]:
                    st.session_state[undo_dialog_key] = False
                    st.session_state[undo_dialog_closed_key] = False
            
            # 磅秤控制面板：1.5 秒刷新一次，確保磅秤讀取有足夠時間完成（讀取最多需要2秒）
            @st.fragment(run_every=1.5)
            def scale_control_panel(curr_item, line_n, s_curr, g_curr):
                render_scale_control_panel(curr_item, line_n, s_curr, g_curr, wo_std_map,
                                          STABLE_TOLERANCE, QUICK_STABLE_TIME, HOLD_RELEASE_DIFF,
                                          RESET_THRESHOLD, NG_MIN, NG_MAX, undo_dialog_key)

            scale_control_panel(curr, line_name, cur_s, cur_g)
            
            # 紀錄歷程區塊（智能刷新：有新數據時快速刷新，否則慢速刷新）
            has_new_log = st.session_state.get(f"new_log_{line_name}", False)
            
            if has_new_log:
                # 有新數據時，使用快速刷新（0.5 秒）
                @st.fragment(run_every=0.5)  # [優化] 從 0.3 秒改為 0.5 秒，減少伺服器負載和連線檢查頻率
                def record_history_panel_fast(line_n, s_curr, g_curr, wo_std, undo_key):
                    # 清除標記，下次使用慢速刷新
                    if st.session_state.get(f"new_log_{line_n}", False):
                        st.session_state[f"new_log_{line_n}"] = False
                    render_record_history(line_n, s_curr, g_curr, wo_std, undo_key)
                record_history_panel_fast(line_name, cur_s, cur_g, wo_std_map, undo_dialog_key)
            else:
                # 沒有新數據時，使用慢速刷新（10 秒），減少不必要的刷新
                @st.fragment(run_every=10.0)
                def record_history_panel_slow(line_n, s_curr, g_curr, wo_std, undo_key):
                    render_record_history(line_n, s_curr, g_curr, wo_std, undo_key)
                record_history_panel_slow(line_name, cur_s, cur_g, wo_std_map, undo_dialog_key)

    else: 
        st.info(f"{line_name} 無排程")


def render_idle_line(line_name, all_line_statuses):
    """渲染閒置中的產線界面"""
    mask_pending = (st.session_state.work_orders_db["狀態"].isin(["待生產", "生產中"])) & (st.session_state.work_orders_db["產線"] == line_name)
    pending_count = len(st.session_state.work_orders_db[mask_pending])
    if pending_count > 0:
        st.markdown(f'<div class="idle-screen"><div class="idle-icon">💤</div><div class="idle-text">{line_name} 交接作業中</div><div class="idle-subtext">請點擊下方按鈕進行作業</div></div>', unsafe_allow_html=True)
        if st.button(f"🚀 開班上工 (Start Shift)", key=f"btn_start_{line_name}", type="primary", width='stretch'): 
            show_start_shift_dialog(line_name, all_line_statuses)
    else:
        st.markdown(f'<div class="no-task-screen"><div class="no-task-icon">📭</div><div class="no-task-text">{line_name} 目前無排程任務</div><div class="no-task-subtext">請聯繫管理員進行派工 (No Schedule Assigned)</div></div>', unsafe_allow_html=True)


def render_record_history(line_n, s_curr, g_curr, wo_std_map, undo_dialog_key):
    """渲染良品與NG紀錄歷程（不在 fragment 中，只在需要時刷新）"""
    st.divider()
    h_l, h_r = st.columns(2)
    
    # 檢查 production_logs 是否為空
    if st.session_state.production_logs.empty:
        session_logs = pd.DataFrame()
    else:
        mask_strict_shift = (st.session_state.production_logs["班別"] == s_curr)
        mask_strict_group = (st.session_state.production_logs["組別"] == g_curr)
        temp_dts = pd.to_datetime(st.session_state.production_logs["時間"], errors='coerce') 
        mask_date = temp_dts.dt.date.astype(str) == datetime.now().strftime("%Y-%m-%d")
        mask_line = st.session_state.production_logs["產線"] == line_n
        session_logs = st.session_state.production_logs[mask_date & mask_line & mask_strict_shift & mask_strict_group]
    
    pass_all_session = session_logs[session_logs["判定結果"] == "PASS"] if not session_logs.empty else pd.DataFrame()
    # [優化] 向量化總重量計算
    total_weight_session = 0.0
    if not pass_all_session.empty:
        # 使用向量化操作取代 iterrows
        wo_ids = pass_all_session["工單號"].values
        weights = [float(wo_std_map.get(wo_id, 0)) for wo_id in wo_ids]
        total_weight_session = sum(weights)
    total_ng_session = len(session_logs[session_logs["判定結果"] == "NG"]) if not session_logs.empty else 0

    with h_l:
        st.markdown(f'<div class="table-label">✅ 良品紀錄 <span style="font-size:0.8em; color:#666; font-weight:normal; margin-left:10px;">(累計: {total_weight_session:.1f} kg)</span></div>', unsafe_allow_html=True)
        if not session_logs.empty: 
            pass_df = session_logs[session_logs["判定結果"]=="PASS"].copy()
            if not pass_df.empty:
<<<<<<< HEAD
<<<<<<< HEAD
                pass_df = pass_df.sort_values(by="時間", ascending=False)
                pass_df["時間"] = pass_df["時間"].astype(str).apply(lambda x: x.split(" ")[-1] if " " in x else x)
                pass_df["序號"] = range(len(pass_df), 0, -1)
=======
=======
>>>>>>> parent of 74ddb67 (秤重速度改善)
                # 按時間升序排序（最早的在前）
                pass_df = pass_df.sort_values("時間", ascending=True)
                # [優化] 向量化時間處理
                if pd.api.types.is_datetime64_any_dtype(pass_df["時間"]):
                    pass_df["時間"] = pd.to_datetime(pass_df["時間"], errors='coerce').dt.strftime("%H:%M:%S")
                else:
                    pass_df["時間"] = pass_df["時間"].astype(str).str.split(" ").str[-1]
                # 序號從 1 開始遞增（1 是最早的記錄）
                pass_df["序號"] = range(1, len(pass_df) + 1)
                # 反轉顯示順序（最新的記錄顯示在最上面）
                pass_df = pass_df.iloc[::-1]
                # 格式化實測重為小數點一位
                pass_df["實測重"] = pd.to_numeric(pass_df["實測重"], errors='coerce').apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
<<<<<<< HEAD
>>>>>>> parent of 74ddb67 (秤重速度改善)
=======
>>>>>>> parent of 74ddb67 (秤重速度改善)
                html_table = '<div class="table-scroll-container"><table class="styled-table"><thead><tr><th style="width:20%">序號</th><th style="width:40%">時間</th><th style="width:40%">實測重</th></tr></thead><tbody>'
                # [優化] 使用 itertuples 取代 iterrows
                for row in pass_df.itertuples():
                    html_table += f"<tr><td>{row.序號}</td><td>{row.時間}</td><td><strong>{row.實測重}</strong></td></tr>"
                html_table += '</tbody></table></div>'
                st.markdown(html_table, unsafe_allow_html=True)
            else: 
                st.info("尚無良品")
        else: 
            st.info("尚無生產紀錄")
            
    with h_r:
        st.markdown(f'<div class="table-label">🔴 NG 紀錄 <span style="font-size:0.8em; color:#666; font-weight:normal; margin-left:10px;">(累計數量: {total_ng_session})</span></div>', unsafe_allow_html=True)
        if not session_logs.empty: 
            ng_df = session_logs[session_logs["判定結果"]=="NG"].copy()
            if not ng_df.empty:
<<<<<<< HEAD
<<<<<<< HEAD
                ng_df = ng_df.sort_values(by="時間", ascending=False)
                ng_df["時間"] = ng_df["時間"].astype(str).apply(lambda x: x.split(" ")[-1] if " " in x else x)
                ng_df["序號"] = range(len(ng_df), 0, -1)
=======
=======
>>>>>>> parent of 74ddb67 (秤重速度改善)
                # 按時間升序排序（最早的在前）
                ng_df = ng_df.sort_values("時間", ascending=True)
                # [優化] 向量化時間處理
                if pd.api.types.is_datetime64_any_dtype(ng_df["時間"]):
                    ng_df["時間"] = pd.to_datetime(ng_df["時間"], errors='coerce').dt.strftime("%H:%M:%S")
                else:
                    ng_df["時間"] = ng_df["時間"].astype(str).str.split(" ").str[-1]
                # 序號從 1 開始遞增（1 是最早的記錄）
                ng_df["序號"] = range(1, len(ng_df) + 1)
                # 反轉顯示順序（最新的記錄顯示在最上面）
                ng_df = ng_df.iloc[::-1]
<<<<<<< HEAD
>>>>>>> parent of 74ddb67 (秤重速度改善)
=======
>>>>>>> parent of 74ddb67 (秤重速度改善)
                html_table = '<div class="table-scroll-container"><table class="styled-table"><thead><tr><th style="width:20%">序號</th><th style="width:40%">時間</th><th style="width:40%">NG原因</th></tr></thead><tbody>'
                # [優化] 使用 itertuples 取代 iterrows
                for row in ng_df.itertuples():
                    html_table += f"<tr><td>{row.序號}</td><td>{row.時間}</td><td><span style='color:#c0392b;'>{row.NG原因}</span></td></tr>"
                html_table += '</tbody></table></div>'
                st.markdown(html_table, unsafe_allow_html=True)
            else: 
                st.info("尚無NG品")
        else: 
            st.info("尚無生產紀錄")
        
        st.markdown("---")
        # 檢查是否有任何記錄可以撤銷（包括 PASS 和 NG）
        has_any_logs = not session_logs.empty
        
        # 檢查是否剛完成撤銷操作
        undo_key = f"undo_completed_{line_n}"
        if undo_key in st.session_state and st.session_state[undo_key]:
            del st.session_state[undo_key]
            st.rerun()
        
        if st.button("↩️ 撤銷上一筆", type="primary", disabled=not has_any_logs, width='stretch', key=f"undo_{line_n}"):
            # 設定標記，讓 fragment 外部顯示對話框
            st.session_state[undo_dialog_key] = True
            st.rerun()


def render_scale_control_panel(curr_item, line_n, s_curr, g_curr, wo_std_map,
                              STABLE_TOLERANCE, QUICK_STABLE_TIME, HOLD_RELEASE_DIFF,
                              RESET_THRESHOLD, NG_MIN, NG_MAX, undo_dialog_key):
    """渲染磅秤控制面板（需要實時刷新）"""
    # [修正] 實時更新數量
    try:
        latest_wo = st.session_state.work_orders_db[st.session_state.work_orders_db["工單號碼"] == curr_item["工單號碼"]].iloc[0]
        rem_qty = int(latest_wo['預計數量']) - int(latest_wo['已完成數量'])
    except:
        rem_qty = int(curr_item['預計數量']) - int(curr_item['已完成數量'])

    st.markdown("""
    <style>
    .weight-display { font-size: 8rem !important; letter-spacing: -2px !important; font-weight: 800 !important; line-height: 1.1 !important; }
    div:has(div#control-buttons-marker) + div button { height: 90px !important; min-height: 90px !important; border-radius: 12px !important; }
    div:has(div#control-buttons-marker) + div button * { font-size: 22px !important; font-weight: 500 !important; line-height: 1.2 !important; }
    </style>
    """, unsafe_allow_html=True)

    try:
        spec = st.session_state.products_db[st.session_state.products_db["產品ID"] == curr_item["產品ID"]].iloc[0]
        std, low, high = float(spec['準重']), float(spec['下限']), float(spec['上限'])
        temp_val = str(spec['溫度等級'])
        temp_color = dm.get_temp_color(temp_val)
        density_val = spec['密度']
        density_show = f"{float(density_val):.1f}" if str(density_val).replace('.','',1).isdigit() else str(density_val).replace('N/A', '-')
        size_show = f"{dm.format_size(spec['長'])}x{dm.format_size(spec['寬'])}x{dm.format_size(spec['高'])}"
        range_show = f"{low:.1f} - {std:.3f} - {high:.1f}"
        notes_html = ""
        for n in [spec['備註1'], spec['備註2'], spec['備註3']]:
            if pd.notna(n) and str(n).strip() != "" and str(n) != "None": 
                # 清理備註內容：徹底移除 HTML 標籤並轉義特殊字符
                note_text = str(n)
                # 第一步：移除所有完整的 HTML 標籤（包括 </div>、<div> 等）
                # 使用非貪婪匹配，確保移除所有標籤
                while '<' in note_text and '>' in note_text:
                    # 持續移除 HTML 標籤，直到沒有為止
                    old_text = note_text
                    note_text = re.sub(r'<[^>]+>', '', note_text)
                    if old_text == note_text:
                        break  # 如果沒有變化，停止循環
                # 第二步：強制移除所有殘留的 < 和 > 字符（處理不完整的標籤）
                note_text = note_text.replace('<', '').replace('>', '')
                # 第三步：移除 HTML 實體編碼（如 &lt; &gt; 等）
                note_text = note_text.replace('&lt;', '').replace('&gt;', '')
                note_text = note_text.replace('&LT;', '').replace('&GT;', '')
                # 第四步：轉義剩餘的 HTML 特殊字符（如 & 等）
                note_text = html.escape(note_text)
                # 第五步：移除多餘的空白字符和換行符
                note_text = ' '.join(note_text.split())
                note_text = note_text.strip()
                # 如果清理後還有內容，才加入 HTML
                if note_text:
                    notes_html += f"<div style='font-size: 1.3rem;'>• {note_text}</div>"
        if not notes_html: 
            notes_html = "<div style='opacity:0.5; font-size: 1.3rem;'>(無特殊備註)</div>"
    except: 
        st.error("❌ 資料庫異常")
        return

    col_left, col_right = st.columns([4, 6])
    with col_left:
        usc_html = f"""<div class="unified-spec-card" style="border-left-color: {temp_color};"><div class="usc-header"><div class="u-label" style="color: #b0bec5; font-weight: bold; font-size: 0.75rem;">CLIENT / 客戶</div><div class="u-value">{spec['客戶名']}</div></div><div class="usc-grid"><div class="usc-item"><span class="u-label">TEMP / 溫度</span><span class="u-value" style="color: {temp_color}">{temp_val}</span></div><div class="usc-item"><span class="u-label">VARIETY / 品種</span><span class="u-value">{spec['品種']}</span></div><div class="usc-item"><span class="u-label">DENSITY / 密度</span><span class="u-value">{density_show}</span></div></div><div class="usc-size-row"><div class="u-label" style="color: #b0bec5; font-weight: bold; font-size: 0.75rem;">SIZE / 尺寸</div><div class="u-value">{size_show}</div></div><div class="usc-range-row"><div class="u-label" style="color: #b0bec5; font-weight: bold; font-size: 0.75rem;">RANGE / 範圍</div><div class="u-value">{range_show}</div></div><div class="usc-notes"><div style="color: #ff4b4b; border-bottom: 1px solid #ff4b4b; padding-bottom: 4px; margin-bottom: 4px; font-weight: bold; font-size: 0.8rem;">NOTES / 備註</div><div class="u-content">{notes_html}</div></div></div>"""
        st.markdown(usc_html, unsafe_allow_html=True)

    with col_right:
        # 獲取重量（總覽模式下顯示 0）
        if st.session_state.locked_station == "總覽模式 (所有產線)": 
            real_w, scale_msg = 0.0, "總覽模式"
        else: 
            real_w, scale_msg = dm.get_real_weight()

        hist = st.session_state[f"hist_{line_n}"]
        hist.append(real_w)
        if len(hist) > 5: 
            hist.pop(0) 
        
        # [優化] 使用滑動平均濾波判斷穩定，比最大值最小值比較更快
        is_variance_low = False
        # [優化] 減少需要的歷史數據從 3 筆改為 2 筆，加快穩定判斷
        if len(hist) >= 2:
            # 計算最近2筆讀數的滑動平均值（使用更少的數據，更快響應）
            recent_hist = hist[-2:]
            moving_avg = sum(recent_hist) / len(recent_hist)
            # 將當前讀數和平均值都四捨五入到第二位小數
            real_w_rounded = round(real_w, 2)
            moving_avg_rounded = round(moving_avg, 2)
            # 如果當前讀數與平均值的差異在容差範圍內，判定為穩定
            if abs(real_w_rounded - moving_avg_rounded) <= STABLE_TOLERANCE:
                is_variance_low = True
        
        if is_variance_low and real_w > 0.1:
            if st.session_state[f"stable_start_{line_n}"] is None:
                st.session_state[f"stable_start_{line_n}"] = time.time()
            else:
                if st.session_state[f"auto_held_val_{line_n}"] is None:
                    if (time.time() - st.session_state[f"stable_start_{line_n}"]) >= QUICK_STABLE_TIME:
                        st.session_state[f"auto_held_val_{line_n}"] = real_w
        else:
            st.session_state[f"stable_start_{line_n}"] = None
            if st.session_state[f"auto_held_val_{line_n}"] is not None:
                if abs(real_w - st.session_state[f"auto_held_val_{line_n}"]) > HOLD_RELEASE_DIFF:
                    st.session_state[f"auto_held_val_{line_n}"] = None

        is_manually_locked = st.session_state[f"lock_{line_n}"]
        auto_held_val = st.session_state[f"auto_held_val_{line_n}"]

        if is_manually_locked:
            display_val = 0.0
            msg_status = "✅ 已記錄 - 請移除物品"
            msg_color = "#3498db"
            if real_w < RESET_THRESHOLD:
                st.session_state[f"lock_{line_n}"] = False
                st.session_state[f"auto_held_val_{line_n}"] = None
                st.session_state[f"hist_{line_n}"] = []
        elif auto_held_val is not None:
            display_val = auto_held_val
            msg_status = "🟢 穩定 - 請按鈕"
            msg_color = "#27ae60"
        else:
            display_val = real_w
            if real_w < 0.1: 
                msg_status = "請放置物品"
                msg_color = "#95a5a6"
            else:
                msg_status = "⚡ 測量中..."
                msg_color = "#e74c3c"

        st.markdown(f"<div style='color:{msg_color}; font-weight:900; font-size:1.5rem; margin-bottom:15px;'>{msg_status}</div>", unsafe_allow_html=True)
        # 顯示磅秤連線狀態（如果有錯誤或警告）
        if "正常" not in scale_msg and "模擬" not in scale_msg:
            if "連線失敗" in scale_msg or "錯誤" in scale_msg or "失敗" in scale_msg:
                st.error(f"⚠️ 磅秤連線問題: {scale_msg}")
            elif "無數據" in scale_msg:
                st.warning(f"ℹ️ {scale_msg}")
            else:
                st.info(f"📡 {scale_msg}")

        buttons_enabled = (auto_held_val is not None) and (not is_manually_locked)
        
        # [修正] 無條件捨去到 1 位小數後判定，與資訊卡顯示一致
        display_val_rounded = math.floor(display_val * 10) / 10
        low_rounded = math.floor(low * 10) / 10
        high_rounded = math.floor(high * 10) / 10
        is_pass_weight = (display_val_rounded >= low_rounded) and (display_val_rounded <= high_rounded)
        is_ng_weight = (display_val_rounded >= NG_MIN) and (display_val_rounded <= NG_MAX)
        
        over_cls = "over-prod" if rem_qty < 0 else ""

        logs = st.session_state.production_logs
        today_str = datetime.now().strftime("%Y-%m-%d")
        mask_logs = (logs["產線"]==line_n) & (logs["班別"]==s_curr) & (logs["組別"]==g_curr)
        current_logs = logs[mask_logs]
        current_logs = current_logs[pd.to_datetime(current_logs["時間"], errors='coerce').dt.strftime("%Y-%m-%d") == today_str]
        pass_logs_now = current_logs[current_logs["判定結果"] == "PASS"]
        act_sum = pd.to_numeric(pass_logs_now["實測重"], errors='coerce').fillna(0).sum()
        std_sum = pass_logs_now["工單號"].map(wo_std_map).fillna(0).astype(float).sum()
        weight_ratio = (act_sum / std_sum * 100) if std_sum > 0 else 0.0

        # 計算無條件捨去的顯示值
        display_val_floor = math.floor(display_val * 10) / 10
        card_html = textwrap.dedent(f"""
        <div class="status-container {'status-pass' if (is_pass_weight and buttons_enabled) else ('status-ng-ready' if (is_ng_weight and buttons_enabled) else 'status-fail')}">
            <div class="status-left-panel"><div class="weight-display">{display_val_floor:.1f}<span style="font-size: 0.3em; margin-left: 15px;">kg</span></div></div>
            <div class="status-right-panel">
                <div class="info-box"><div class="info-label">SHIFT / 班別</div><div class="info-value">{s_curr}-{g_curr}</div></div>
                <div class="info-box"><div class="info-label">REMAIN / 剩餘</div><div class="info-value-huge {over_cls}">{rem_qty}</div></div>
                <div class="info-box"><div class="info-label">RATIO / 實重準重</div><div class="info-value-large">{weight_ratio:.1f}%</div></div>
            </div>
        </div>
        """)
        st.markdown(card_html, unsafe_allow_html=True)
        st.markdown('<div id="control-buttons-marker"></div>', unsafe_allow_html=True)

        # 將當前顯示值存儲在 session_state 中，以便按鈕回調函數使用（避免閉包變數問題）
        st.session_state[f"current_display_val_{line_n}"] = display_val
        
        # [防護機制] 當有鎖定的重量值時，立即保存快照，避免作業員點擊後立即移除物品導致讀取到錯誤值
        if auto_held_val is not None:
            st.session_state[f"snapshot_weight_{line_n}"] = auto_held_val

        # 將當前工單信息存儲在 session_state 中，以便按鈕回調函數使用（避免閉包變數問題）
        st.session_state[f"current_wo_id_{line_n}"] = curr_item["工單號碼"]
        st.session_state[f"current_product_id_{line_n}"] = curr_item["產品ID"]
        
        b_l, b_r = st.columns([3, 1])
        with b_l:
            def do_pass():
                # [防重複點擊] 檢查是否正在處理中，防止連續點擊造成重複記錄
                processing_key = f"processing_pass_{line_n}"
                if st.session_state.get(processing_key, False):
                    return  # 如果正在處理，直接返回，不執行任何操作
                
                # [時間間隔檢查] 防止連點問題：檢查距離上次記錄的時間間隔
                last_record_time_key = f"last_record_time_{line_n}"
                last_record_time = st.session_state.get(last_record_time_key)
                MIN_RECORD_INTERVAL = 2.0  # 最小記錄間隔：2秒（實際操作中不可能一秒秤一個）
                
                if last_record_time is not None:
                    time_since_last = time.time() - last_record_time
                    if time_since_last < MIN_RECORD_INTERVAL:
                        remaining_time = MIN_RECORD_INTERVAL - time_since_last
                        st.warning(f"⏱️ 操作過快！請等待 {remaining_time:.1f} 秒後再記錄。實際操作中不可能一秒秤一個產品。")
                        return
                
                # 設置處理標記，防止重複執行
                st.session_state[processing_key] = True
                
                try:
                    # [防護機制] 優先使用快照的重量值，如果沒有快照則使用當前鎖定的值
                    weight_to_record = st.session_state.get(f"snapshot_weight_{line_n}")
                    if weight_to_record is None:
                        # 如果沒有快照，使用當前鎖定的重量值
                        weight_to_record = st.session_state.get(f"auto_held_val_{line_n}")
                    if weight_to_record is None:
                        # 如果意外為 None，使用當前顯示值（從 session_state 中讀取，避免閉包問題）
                        weight_to_record = st.session_state.get(f"current_display_val_{line_n}", 0.0)
                    
                    # 從 session_state 獲取當前工單信息（避免閉包變數問題）
                    wo_id = st.session_state.get(f"current_wo_id_{line_n}")
                    product_id = st.session_state.get(f"current_product_id_{line_n}")
                    
                    if wo_id is None or product_id is None:
                        st.error("無法取得當前工單信息，請重新選擇工單")
                        return
                    
                    # [防護機制] 驗證重量是否在合理範圍內
                    # 獲取產品規格以驗證重量
                    try:
                        spec = st.session_state.products_db[st.session_state.products_db["產品ID"] == product_id].iloc[0]
                        low_limit = float(spec['下限'])
                        # 如果重量小於下限的 50% 或小於 0.5kg，視為異常數據，拒絕記錄
                        min_valid_weight = max(low_limit * 0.5, 0.5)
                        if weight_to_record < min_valid_weight:
                            st.error(f"❌ 記錄失敗：重量值 {weight_to_record:.3f} kg 過小，疑似物品已移除。請重新放置物品後再記錄。")
                            st.session_state[f"lock_{line_n}"] = False  # 不鎖定，讓作業員可以重新操作
                            return
                    except Exception as e:
                        # 如果無法獲取規格，至少檢查重量是否大於 0.5kg
                        if weight_to_record < 0.5:
                            st.error(f"❌ 記錄失敗：重量值 {weight_to_record:.3f} kg 過小，疑似物品已移除。請重新放置物品後再記錄。")
                            st.session_state[f"lock_{line_n}"] = False
                            return
                    
                    # [重複記錄檢查] 檢查是否已經有相同的記錄（防止系統錯誤重複記錄）
                    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 檢查 session_state 中是否已有相同時間和重量的記錄
                    if not st.session_state.production_logs.empty:
                        recent_logs = st.session_state.production_logs.tail(5)  # 檢查最近5筆
                        duplicate_mask = (
                            (recent_logs["時間"].astype(str).str[:19] == current_time_str[:19]) &
                            (recent_logs["產線"] == line_n) &
                            (recent_logs["工單號"] == wo_id) &
                            (abs(recent_logs["實測重"] - weight_to_record) < 0.01)  # 重量相同（容差0.01kg）
                        )
                        if duplicate_mask.any():
                            st.error("❌ 檢測到重複記錄！系統可能發生錯誤，請稍後再試。")
                            return
                    
                    idx = st.session_state.work_orders_db[st.session_state.work_orders_db["工單號碼"] == wo_id].index[0]
                    st.session_state.work_orders_db.at[idx, "已完成數量"] += 1
                    st.session_state.work_orders_db.at[idx, "狀態"] = "生產中"
                    new_log = pd.DataFrame([[current_time_str, line_n, wo_id, product_id, weight_to_record, "PASS", "", g_curr, s_curr, ""]], columns=config.LOG_COLUMNS)
                    st.session_state.production_logs = pd.concat([st.session_state.production_logs, new_log], ignore_index=True)
                    save_data()
                    st.session_state[f"lock_{line_n}"] = True
                    
                    # [時間間隔檢查] 記錄本次記錄時間
                    st.session_state[last_record_time_key] = time.time()
                    
                    # 清除快照，避免下次誤用
                    if f"snapshot_weight_{line_n}" in st.session_state:
                        del st.session_state[f"snapshot_weight_{line_n}"]
                    # 設置標記，通知 fragment 有新數據需要刷新
                    st.session_state[f"new_log_{line_n}"] = True
                except Exception as e:
                    st.error(f"記錄失敗: {e}")
                finally:
                    # 清除處理標記，允許下次操作
                    st.session_state[processing_key] = False
            btn_pass_disabled = not (is_pass_weight and buttons_enabled)
            st.button("紀錄良品\n(PASS)", disabled=btn_pass_disabled, type="primary", width='stretch', on_click=do_pass, key=f"btn_pass_{line_n}")

        with b_r:
            def do_ng():
                # [防重複點擊] 檢查是否正在處理中，防止連續點擊造成重複記錄
                processing_key = f"processing_ng_{line_n}"
                if st.session_state.get(processing_key, False):
                    return  # 如果正在處理，直接返回，不執行任何操作
                
                # [時間間隔檢查] 防止連點問題：檢查距離上次記錄的時間間隔
                last_record_time_key = f"last_record_time_{line_n}"
                last_record_time = st.session_state.get(last_record_time_key)
                MIN_RECORD_INTERVAL = 2.0  # 最小記錄間隔：2秒（實際操作中不可能一秒秤一個）
                
                if last_record_time is not None:
                    time_since_last = time.time() - last_record_time
                    if time_since_last < MIN_RECORD_INTERVAL:
                        remaining_time = MIN_RECORD_INTERVAL - time_since_last
                        st.warning(f"⏱️ 操作過快！請等待 {remaining_time:.1f} 秒後再記錄。實際操作中不可能一秒秤一個產品。")
                        return
                
                # 設置處理標記，防止重複執行
                st.session_state[processing_key] = True
                
                try:
                    # [防護機制] 優先使用快照的重量值，如果沒有快照則使用當前鎖定的值
                    weight_to_record = st.session_state.get(f"snapshot_weight_{line_n}")
                    if weight_to_record is None:
                        # 如果沒有快照，使用當前鎖定的重量值
                        weight_to_record = st.session_state.get(f"auto_held_val_{line_n}")
                    if weight_to_record is None:
                        # 如果意外為 None，使用當前顯示值（從 session_state 中讀取，避免閉包問題）
                        weight_to_record = st.session_state.get(f"current_display_val_{line_n}", 0.0)
                    
                    # 從 session_state 獲取當前工單信息（避免閉包變數問題）
                    wo_id = st.session_state.get(f"current_wo_id_{line_n}")
                    product_id = st.session_state.get(f"current_product_id_{line_n}")
                    
                    if wo_id is None or product_id is None:
                        st.error("無法取得當前工單信息，請重新選擇工單")
                        return
                    
                    # [防護機制] 驗證 NG 重量是否在合理範圍內（10.0~10.5 kg）
                    if weight_to_record < 9.0 or weight_to_record > 11.0:
                        st.error(f"❌ 記錄失敗：NG 重量值 {weight_to_record:.3f} kg 不在合理範圍內（應為 10.0~10.5 kg）。請重新確認。")
                        st.session_state[f"lock_{line_n}"] = False  # 不鎖定，讓作業員可以重新操作
                        return
                    
                    # [重複記錄檢查] 檢查是否已經有相同的記錄（防止系統錯誤重複記錄）
                    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 檢查 session_state 中是否已有相同時間和重量的記錄
                    if not st.session_state.production_logs.empty:
                        recent_logs = st.session_state.production_logs.tail(5)  # 檢查最近5筆
                        duplicate_mask = (
                            (recent_logs["時間"].astype(str).str[:19] == current_time_str[:19]) &
                            (recent_logs["產線"] == line_n) &
                            (recent_logs["工單號"] == wo_id) &
                            (abs(recent_logs["實測重"] - weight_to_record) < 0.01)  # 重量相同（容差0.01kg）
                        )
                        if duplicate_mask.any():
                            st.error("❌ 檢測到重複記錄！系統可能發生錯誤，請稍後再試。")
                            return
                    
                    r = st.session_state.get(f"ng_sel_{line_n}", "其他")
                    new_log = pd.DataFrame([[current_time_str, line_n, wo_id, product_id, weight_to_record, "NG", r, g_curr, s_curr, ""]], columns=config.LOG_COLUMNS)
                    st.session_state.production_logs = pd.concat([st.session_state.production_logs, new_log], ignore_index=True)
                    save_data()
                    st.session_state.toast_msg = (f"🔴 NG: {weight_to_record} kg", None)
                    st.session_state[f"lock_{line_n}"] = True
                    
                    # [時間間隔檢查] 記錄本次記錄時間
                    st.session_state[last_record_time_key] = time.time()
                    
                    # 清除快照，避免下次誤用
                    if f"snapshot_weight_{line_n}" in st.session_state:
                        del st.session_state[f"snapshot_weight_{line_n}"]
                    # 設置標記，通知 fragment 有新數據需要刷新
                    st.session_state[f"new_log_{line_n}"] = True
                except Exception as e:
                    st.error(f"記錄失敗: {e}")
                finally:
                    # 清除處理標記，允許下次操作
                    st.session_state[processing_key] = False
            
            # [關鍵修正] NG 只有在 10.0~10.5 之間才能按
            btn_ng_disabled = not (is_ng_weight and buttons_enabled)
<<<<<<< HEAD
<<<<<<< HEAD
            st.button("紀錄不良品\n(NG)", disabled=btn_ng_disabled, type="primary", use_container_width=True, on_click=do_ng, key=f"btn_ng_{line_n}")
=======
            st.button("紀錄不良品\n(NG)", disabled=btn_ng_disabled, type="primary", width='stretch', on_click=do_ng, key=f"btn_ng_{line_n}")
>>>>>>> parent of 74ddb67 (秤重速度改善)
=======
            st.button("紀錄不良品\n(NG)", disabled=btn_ng_disabled, type="primary", width='stretch', on_click=do_ng, key=f"btn_ng_{line_n}")
>>>>>>> parent of 74ddb67 (秤重速度改善)
        
        # [關鍵修正] 下拉選單只在 NG 範圍內出現
        if is_ng_weight and not is_manually_locked: 
            st.selectbox("NG 原因", ["不足重尾數", "規格切換廢料", "外觀不良", "其他"], key=f"ng_sel_{line_n}")

