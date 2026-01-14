"""
後台管理頁面模組
包含產品建檔、產能排程、生產報表等功能
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os
import time
import re
import random
import uuid
import sqlite3

import config
import data_manager as dm
from data_loader import save_data, upsert_products, delete_products, reload_products
from db_schema import get_connection
from dialogs import show_delete_work_orders_confirm


def render_admin_page():
    """渲染後台管理頁面"""
    st.markdown('<div class="custom-main-title">🛠️ 系統管理中心</div>', unsafe_allow_html=True)
    tab_prod, tab_sch, tab_rpt = st.tabs(["📦 產品建檔與管理", "🗓️ 產能排程與佇列", "📊 生產報表中心"])

    with tab_prod:
        render_product_management()
    
    with tab_sch:
        render_schedule_management()
    
    with tab_rpt:
        render_reports()


def render_product_management():
    """產品建檔與管理"""
    st.markdown('<div class="section-header header-admin">1. 新增產品資料</div>', unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1.5])
        with c1: batch_client = st.text_input("客戶名", value="庫存")
        with c2: batch_temp = st.selectbox("溫度等級", config.TEMP_OPTIONS, index=0)
        with c3: batch_variety = st.selectbox("品種", [""] + config.ALL_VARIETIES, index=0)
        is_special = batch_variety in config.SPECIAL_VARIETIES
        fixed_weight_opt = 0; batch_density = 0
        with c4:
            if is_special: fixed_weight_opt = st.selectbox("固定包裝重 (kg)", [10, 15, 20, 25], index=0)
            else: batch_density = st.selectbox("密度", config.DENSITY_OPTIONS, index=6, key="density_selectbox")
        st.write("")
        col_t1, col_t2 = st.columns([6, 1.5])
        with col_t1: st.markdown('<div class="table-label">規格輸入</div>', unsafe_allow_html=True)
        with col_t2:
            if st.button("🗑️ 重置表格", type="primary", width='stretch'):
                st.session_state.editor_df_clean = pd.DataFrame({"長": [0.0], "寬": [0.0], "高": [0.0], "下限": [0.0], "準重": [0.0], "上限": [0.0], "備註1": [""], "備註2": [""], "備註3": [""]})
                st.rerun()
        if 'editor_df_clean' not in st.session_state: st.session_state.editor_df_clean = pd.DataFrame({"長": [0.0], "寬": [0.0], "高": [0.0], "下限": [0.0], "準重": [0.0], "上限": [0.0], "備註1": [""], "備註2": [""], "備註3": [""]})
        column_cfg = {"下限": st.column_config.NumberColumn(format="%.1f"), "上限": st.column_config.NumberColumn(format="%.1f"), "長": st.column_config.NumberColumn(disabled=is_special, format="%.1f", step=0.1), "寬": st.column_config.NumberColumn(disabled=is_special, format="%.1f", step=0.1), "高": st.column_config.NumberColumn(disabled=is_special, format="%.1f", step=0.1), "準重": st.column_config.NumberColumn(format="%.3f")}
        st.session_state.editor_df_clean.index = range(1, len(st.session_state.editor_df_clean) + 1)
        edited_df = st.data_editor(st.session_state.editor_df_clean, num_rows="fixed", width='stretch', column_config=column_cfg, key="data_editor")
        col_add, _ = st.columns([1, 4])
        with col_add:
            if st.button("➕ 增加 1 列", type="primary", width='stretch'):
                st.session_state.editor_df_clean = pd.concat([edited_df, pd.DataFrame({"長": [0.0], "寬": [0.0], "高": [0.0], "下限": [0.0], "準重": [0.0], "上限": [0.0], "備註1": [""], "備註2": [""], "備註3": [""]})], ignore_index=True)
                st.rerun()
        st.write(""); col_btn1, col_btn2 = st.columns([1, 3])
        with col_btn1:
            if st.button("🔄 計算重量", type="primary", width='stretch'):
                calc_df = edited_df.reset_index(drop=True)
                for index, row in calc_df.iterrows():
                    if is_special: w = float(fixed_weight_opt); calc_df.at[index, "準重"], calc_df.at[index, "下限"], calc_df.at[index, "上限"] = w, w, w + 0.2
                    else:
                        if row["長"] > 0 and row["寬"] > 0 and row["高"] > 0:
                            vol = (row["長"]/1000) * (row["寬"]/1000) * (row["高"]/1000)
                            if batch_density in config.DENSITY_MAP: d_min, d_max = config.DENSITY_MAP[batch_density]; calc_df.at[index, "準重"] = round(vol * batch_density, 3); calc_df.at[index, "下限"] = round(vol * d_min, 1); calc_df.at[index, "上限"] = round(vol * d_max, 1)
                st.session_state.editor_df_clean = calc_df; st.rerun()
        with col_btn2:
            if st.button("💾 確認寫入資料庫", type="primary", width='stretch'):
                final_df = edited_df.reset_index(drop=True); saved = 0; skipped = 0
                if not batch_variety: st.error("❌ 請選擇品種")
                else:
                    # 清理備註欄位中的 HTML 標籤（防止從 Excel 複製貼上時帶入 HTML）
                    def clean_note_field(val):
                        """清理備註欄位中的 HTML 標籤"""
                        if pd.isna(val) or str(val).lower() == 'none':
                            return ""
                        val_str = str(val)
                        # 移除 HTML 標籤
                        val_str = re.sub(r'<[^>]+>', '', val_str)
                        # 移除多餘的空白字符
                        return val_str.strip()
                    
                    existing_signatures = set()
                    def get_signature(client, temp, var, dens, l, w, h, n1, n2, n3): return f"{client}|{temp}|{var}|{dens}|{float(l):.1f}|{float(w):.1f}|{float(h):.1f}|{n1}|{n2}|{n3}"
                    if not st.session_state.products_db.empty:
                        for _, r in st.session_state.products_db.iterrows():
                            try: existing_signatures.add(get_signature(r['客戶名'], r['溫度等級'], r['品種'], r['密度'], r['長'], r['寬'], r['高'], r['備註1'], r['備註2'], r['備註3']))
                            except: continue
                    for i, row in final_df.iterrows():
                        if row["準重"] > 0:
                            current_dens = batch_density if not is_special else "N/A"
                            # 清理備註欄位
                            note1 = clean_note_field(row["備註1"])
                            note2 = clean_note_field(row["備註2"])
                            note3 = clean_note_field(row["備註3"])
                            
                            current_sig = get_signature(batch_client, batch_temp, batch_variety, current_dens, row['長'], row['寬'], row['高'], note1, note2, note3)
                            if current_sig in existing_signatures: skipped += 1
                            else:
                                existing_signatures.add(current_sig)
                                
                                # [關鍵修正] 確保產品 ID 絕對唯一
                                def generate_unique_product_id(client, variety, index):
                                    """生成唯一的產品 ID，確保不會重複"""
                                    max_retries = 100  # 最多嘗試 100 次
                                    
                                    for attempt in range(max_retries):
                                        # 使用完整的時間戳（包含微秒）和隨機數
                                        timestamp = datetime.now()
                                        # 格式：客戶名-品種-索引-年月日時分秒微秒-隨機數
                                        unique_suffix = f"{timestamp.strftime('%Y%m%d%H%M%S')}{timestamp.microsecond:06d}{random.randint(1000, 9999)}"
                                        candidate_id = f"{client}-{variety}-{index}-{unique_suffix}"
                                        
                                        # 檢查 session_state 中是否已存在
                                        if '產品ID' in st.session_state.products_db.columns:
                                            if candidate_id not in st.session_state.products_db['產品ID'].values:
                                                # 再檢查資料庫中是否已存在（查詢資料庫）
                                                try:
                                                    check_conn = get_connection()
                                                    check_cursor = check_conn.cursor()
                                                    check_cursor.execute("SELECT COUNT(*) FROM products WHERE 產品ID = ?", (candidate_id,))
                                                    exists_in_db = check_cursor.fetchone()[0] > 0
                                                    check_conn.close()
                                                    
                                                    if not exists_in_db:
                                                        return candidate_id
                                                except Exception as e:
                                                    # 如果查詢失敗，為了安全起見，繼續嘗試下一個 ID
                                                    print(f"檢查產品 ID 時發生錯誤：{e}")
                                                    continue
                                        
                                        # 如果 ID 已存在，等待一小段時間後重試（確保時間戳不同）
                                        time.sleep(0.001)  # 等待 1 毫秒
                                    
                                    # 如果所有嘗試都失敗，使用 UUID 作為後備方案
                                    fallback_id = f"{client}-{variety}-{index}-{uuid.uuid4().hex[:12]}"
                                    print(f"⚠️ 使用 UUID 後備方案生成產品 ID：{fallback_id}")
                                    return fallback_id
                                
                                new_id = generate_unique_product_id(batch_client, batch_variety, i)
                                new_row_df = pd.DataFrame([[new_id, batch_client, batch_temp, batch_variety, current_dens, row["長"], row["寬"], row["高"], row["下限"], row["準重"], row["上限"], note1, note2, note3]], columns=st.session_state.products_db.columns)
                                # 先累積在記憶體（用於本次匯入計數/避免重複），真正寫入改成增量 upsert（批次）
                                st.session_state.products_db = pd.concat([st.session_state.products_db, new_row_df], ignore_index=True)
                                saved += 1
                    if saved > 0:
                        try:
                            # [關鍵修正] 產品資料改為增量寫入（不再全表刪除）
                            # 只把本次新增的資料 upsert 到 DB（批次）
                            new_inserted = st.session_state.products_db.tail(saved).copy()
                            upsert_products(new_inserted)
                            
                            msg = f"✅ 成功匯入 {saved} 筆" + (f" (⚠️ 另略過 {skipped} 筆重複)" if skipped > 0 else "")
                            st.toast(msg)
                            st.session_state.editor_df_clean = pd.DataFrame({"長": [0.0], "寬": [0.0], "高": [0.0], "下限": [0.0], "準重": [0.0], "上限": [0.0], "備註1": [""], "備註2": [""], "備註3": [""]})
                            time.sleep(0.5)  # 稍微等待，確保資料庫寫入完成
                            # 重新從 DB 載入，確保跨 session 也一致
                            reload_products()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 寫入資料庫失敗：{str(e)}")
                            import traceback
                            st.error(traceback.format_exc())
                    elif skipped > 0: st.error(f"❌ 寫入失敗：偵測到 {skipped} 筆完全重複的產品資料！")
                    else: st.warning("⚠️ 沒有有效資料可寫入 (準重必須 > 0)")

    st.divider()
    st.markdown('<div class="section-header header-admin">2. 檢視與管理現有產品</div>', unsafe_allow_html=True)
    if not st.session_state.products_db.empty:
        db_disp = st.session_state.products_db.copy()
        c_f1, c_f2, c_f3, c_f4, c_del = st.columns([2, 2, 2, 3, 2])
        f_cli = c_f1.selectbox("篩選客戶", ["全部"] + list(db_disp["客戶名"].unique()), key="db_f_cli")
        f_tmp = c_f2.selectbox("篩選溫度", ["全部"] + list(db_disp["溫度等級"].unique()), key="db_f_tmp")
        f_var = c_f3.selectbox("篩選品種", ["全部"] + list(db_disp["品種"].unique()), key="db_f_var")
        f_key = c_f4.text_input("關鍵字搜尋", placeholder="規格/備註...", key="db_f_key")
        if f_cli != "全部": db_disp = db_disp[db_disp["客戶名"] == f_cli]
        if f_tmp != "全部": db_disp = db_disp[db_disp["溫度等級"] == f_tmp]
        if f_var != "全部": db_disp = db_disp[db_disp["品種"] == f_var]
        if f_key: mask = db_disp.astype(str).apply(lambda x: x.str.contains(f_key, case=False, na=False)).any(axis=1); db_disp = db_disp[mask]
        db_disp.insert(0, "刪除", False); db_disp = db_disp.reset_index(drop=True); db_disp.index = range(1, len(db_disp) + 1); db_disp["溫度等級"] = db_disp["溫度等級"].astype(str)
        cols_to_show_db = ["刪除", "客戶名", "溫度等級", "品種", "密度", "長", "寬", "高", "下限", "準重", "上限", "備註1", "備註2", "備註3"]
        edited_db = st.data_editor(db_disp[cols_to_show_db], width='stretch', disabled=[c for c in cols_to_show_db if c!="刪除"], column_config={"刪除": st.column_config.CheckboxColumn(width="small"), "準重": st.column_config.NumberColumn(format="%.3f")})
        with c_del:
            st.write(""); st.write("")
            if st.button("🗑️ 刪除選取資料", type="primary", width='stretch'):
                selected_rows = edited_db[edited_db["刪除"] == True]
                if not selected_rows.empty:
                    ids_to_remove = db_disp.loc[selected_rows.index, "產品ID"].tolist()
                    try:
                        # [關鍵修正] 精準刪除 DB 記錄（不再全表覆寫）
                        delete_products(ids_to_remove)
                        reload_products()
                        st.toast(f"🗑️ 已刪除 {len(ids_to_remove)} 筆資料")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 刪除資料失敗：{str(e)}")
    else: st.info("資料庫為空")


def render_schedule_management():
    """產能排程管理"""
    if 'admin_line_choice' not in st.session_state: st.session_state.admin_line_choice = None
    st.markdown('<div class="section-header header-admin">📊 產能排程管理 - 請選擇產線</div>', unsafe_allow_html=True)
    
    if 'admin_line_choice' not in st.session_state: 
        st.session_state.admin_line_choice = None

    cols_nav = st.columns(4)
    for i, line in enumerate(config.PRODUCTION_LINES):
        pending_count = len(st.session_state.work_orders_db[(st.session_state.work_orders_db["產線"] == line) & (st.session_state.work_orders_db["狀態"] != "已完成")])
        
        btn_type = "primary" if st.session_state.admin_line_choice == line else "secondary"
        
        with cols_nav[i]:
            if st.button(f"{line}\n(待生產: {pending_count})", type=btn_type, width='stretch', key=f"nav_btn_{line}"):
                st.session_state.admin_line_choice = line
                st.rerun()
    
    st.divider()

    if st.session_state.admin_line_choice:
        target_line = st.session_state.admin_line_choice
        
        st.subheader(f"⚙️ 正在管理：{target_line}")
        
        st.markdown("### ➕ 加入新任務")
        if not st.session_state.products_db.empty:
            db_select = st.session_state.products_db.copy()
            c_f1, c_f2, c_f3, c_f4 = st.columns(4)
            f_cli = c_f1.selectbox("篩選客戶", ["全部"] + list(db_select["客戶名"].unique()), key="sch_f_cli")
            f_tmp = c_f2.selectbox("篩選溫度", ["全部"] + list(db_select["溫度等級"].unique()), key="sch_f_tmp")
            f_var = c_f3.selectbox("篩選品種", ["全部"] + list(db_select["品種"].unique()), key="sch_f_var")
            f_key = c_f4.text_input("關鍵字搜尋", placeholder="規格/備註...", key="sch_f_key")
            if f_cli != "全部": db_select = db_select[db_select["客戶名"] == f_cli]
            if f_tmp != "全部": db_select = db_select[db_select["溫度等級"] == f_tmp]
            if f_var != "全部": db_select = db_select[db_select["品種"] == f_var]
            if f_key: mask = db_select.astype(str).apply(lambda x: x.str.contains(f_key, case=False, na=False)).any(axis=1); db_select = db_select[mask]
            db_select = db_select.reset_index(drop=False)
            view_df = pd.DataFrame()
            view_df["產品ID"] = db_select["產品ID"]; view_df["客戶名"] = db_select["客戶名"]; view_df["溫度"] = db_select["溫度等級"].astype(str); view_df["品種"] = db_select["品種"]
            view_df["📏 規格"] = db_select.apply(lambda x: f"{dm.format_size(x['長'])}x{dm.format_size(x['寬'])}x{dm.format_size(x['高'])}", axis=1)
            view_df["下限"] = db_select["下限"]; view_df["準重"] = db_select["準重"]; view_df["上限"] = db_select["上限"]
            view_df["備註1"] = db_select["備註1"]; view_df["備註2"] = db_select["備註2"]; view_df["備註3"] = db_select["備註3"]; view_df["📝 排程數量"] = 0 
            view_df.index = range(1, len(view_df) + 1)
            st.write("在表格最右側輸入「📝 排程數量」：")
            edited_selection = st.data_editor(view_df[["客戶名", "溫度", "品種", "📏 規格", "下限", "準重", "上限", "備註1", "備註2", "備註3", "📝 排程數量"]], column_config={"📝 排程數量": st.column_config.NumberColumn(min_value=0, step=1, required=True, format="%d"), "客戶名": st.column_config.TextColumn(disabled=True), "溫度": st.column_config.TextColumn(disabled=True), "品種": st.column_config.TextColumn(disabled=True), "📏 規格": st.column_config.TextColumn(disabled=True), "下限": st.column_config.NumberColumn(disabled=True, format="%.1f"), "準重": st.column_config.NumberColumn(disabled=True, format="%.3f"), "上限": st.column_config.NumberColumn(disabled=True, format="%.1f"), "備註1": st.column_config.TextColumn(disabled=True), "備註2": st.column_config.TextColumn(disabled=True), "備註3": st.column_config.TextColumn(disabled=True)}, width='stretch')
            st.write("")
            # 確保按鈕有足夠高度和視覺效果（通過 JavaScript 處理，這裡的 CSS 僅作為備用）
            st.markdown("""
            <style>
            button.action-button-primary {
                min-height: 4rem !important;
                height: auto !important;
                padding: 1rem 2rem !important;
                font-size: 1.2rem !important;
                font-weight: 700 !important;
                line-height: 1.5 !important;
                box-shadow: 0 4px 8px rgba(231, 76, 60, 0.3), 0 2px 4px rgba(231, 76, 60, 0.2) !important;
                border: 2px solid #c0392b !important;
                border-radius: 8px !important;
                transition: all 0.3s ease !important;
            }
            button.action-button-primary:hover {
                box-shadow: 0 6px 12px rgba(231, 76, 60, 0.4), 0 4px 6px rgba(231, 76, 60, 0.3) !important;
                transform: translateY(-2px) !important;
                background-color: #ec7063 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            if st.button(f"⬇️ 確認加入至 {target_line} 的排程", type="primary", width='stretch'):
                items_index = edited_selection[edited_selection["📝 排程數量"] > 0].index
                if not items_index.empty:
                    new_orders = []
                    
                    # [關鍵修正] 從資料庫查詢下一個工單序號，確保不會重複
                    try:
                        from data_loader import get_next_work_order_sequence
                        current_sequence = get_next_work_order_sequence()
                    except Exception as e:
                        print(f"查詢工單序號失敗: {e}")
                        # 如果查詢失敗，使用 session_state 作為備用方案
                        current_sequence = len(st.session_state.work_orders_db) + 1 if 'work_orders_db' in st.session_state else 1
                    
                    for idx in items_index:
                        qty = edited_selection.loc[idx, "📝 排程數量"]; original_row = db_select.iloc[idx-1]
                        wo_id = f"WO-{datetime.now().strftime('%m%d')}-{current_sequence:04d}"
                        current_sequence += 1  # 為下一個工單準備序號
                        note_text = str(original_row['備註1']) if pd.notna(original_row['備註1']) else ""; note_display = f" | {note_text}" if note_text else ""
                        spec_str = f"{dm.format_size(original_row['長'])}x{dm.format_size(original_row['寬'])}x{dm.format_size(original_row['高'])}"
                        detail_str = f"[{original_row['客戶名']}] | {original_row['溫度等級']} | {original_row['品種']} | {spec_str} | {original_row['準重']}kg{note_display}"
                        new_orders.append([target_line, 9999, wo_id, original_row['產品ID'], detail_str, original_row['品種'], original_row['密度'], original_row['準重'], int(qty), 0, "待生產", datetime.now(), detail_str])
                    
                    # [修正] 安全寫入（使用 SQL）
                    try:
                        from data_loader import add_work_orders
                        add_work_orders(new_orders)
                        st.toast(f"✅ 已成功加入 {len(new_orders)} 筆工單！"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"存檔失敗: {e}")

                else: st.warning("請至少在一個項目輸入數量")
        else: st.warning("無產品資料")
        st.markdown("---")
        st.markdown(f'<div class="section-header header-queue">📋 {target_line} 佇列管理</div>', unsafe_allow_html=True)
        active_wos = st.session_state.work_orders_db[(st.session_state.work_orders_db["狀態"] != "已完成") & (st.session_state.work_orders_db["產線"] == target_line)].copy().sort_values("排程順序")
        if not active_wos.empty:
            if not st.session_state.products_db.empty: active_wos_view = active_wos.merge(st.session_state.products_db, on="產品ID", how="left")
            else: active_wos_view = active_wos.copy()
            display_df = pd.DataFrame(); display_df["刪除"] = False; display_df["排序"] = range(1, len(active_wos_view) + 1)
            if "客戶名" in active_wos_view.columns:
                display_df["客戶名"] = active_wos_view["客戶名"]; display_df["品種"] = active_wos_view["品種_x"]; display_df["溫度"] = active_wos_view["溫度等級"].astype(str)
                # 從 products_db 中取得密度值
                def get_density(row):
                    product_id = row.get("產品ID", "")
                    if product_id and not st.session_state.products_db.empty:
                        product_match = st.session_state.products_db[st.session_state.products_db["產品ID"] == product_id]
                        if not product_match.empty and "密度" in product_match.columns:
                            density_val = product_match.iloc[0]["密度"]
                            if pd.notna(density_val) and str(density_val).strip() != "":
                                try:
                                    return f"{float(density_val):.1f}"
                                except (ValueError, TypeError):
                                    return str(density_val)
                    return ""
                display_df["密度"] = active_wos_view.apply(get_density, axis=1)
                display_df["規格"] = active_wos_view.apply(lambda x: f"{dm.format_size(x['長'])}x{dm.format_size(x['寬'])}x{dm.format_size(x['高'])}", axis=1); display_df["準重"] = active_wos_view["準重_x"]
            else: display_df["內容"] = active_wos_view["詳細規格字串"]
            display_df["預計數量"] = active_wos_view["預計數量"]; display_df["已完成"] = active_wos_view["已完成數量"]; display_df.index = active_wos.index 
            # 刪除工單對話框狀態初始化（在按鈕區塊之前）
            dialog_key = f"delete_wo_dialog_{target_line}"
            delete_wo_ids_key = f"delete_wo_ids_{target_line}"
            delete_wo_info_key = f"delete_wo_info_{target_line}"
            dialog_closed_key = f"delete_wo_dialog_closed_{target_line}"
            
            # 初始化對話框狀態
            if dialog_key not in st.session_state:
                st.session_state[dialog_key] = False
            if dialog_closed_key not in st.session_state:
                st.session_state[dialog_closed_key] = False
            
            # 檢查是否應該清除 dialog 標記（用戶之前關閉了它）
            if st.session_state.get(dialog_closed_key, False):
                st.session_state[dialog_key] = False
                st.session_state[dialog_closed_key] = False
            
            # 初始化排序操作狀態
            move_key = f"move_wo_{target_line}"
            if move_key not in st.session_state:
                st.session_state[move_key] = None
            
            # 處理上下移動操作
            if st.session_state[move_key] is not None:
                move_action, move_idx = st.session_state[move_key]
                current_order = active_wos.iloc[move_idx]["排程順序"]
                
                if move_action == "up" and move_idx > 0:
                    # 向上移動：與前一個交換順序
                    prev_idx = active_wos.index[move_idx - 1]
                    prev_order = active_wos.iloc[move_idx - 1]["排程順序"]
                    st.session_state.work_orders_db.at[active_wos.index[move_idx], "排程順序"] = prev_order
                    st.session_state.work_orders_db.at[prev_idx, "排程順序"] = current_order
                    st.session_state.work_orders_db = dm.normalize_sequences(st.session_state.work_orders_db)
                    save_data()
                    st.toast(f"✅ 已向上移動")
                    st.session_state[move_key] = None
                    time.sleep(0.5)
                    st.rerun()
                elif move_action == "down" and move_idx < len(active_wos) - 1:
                    # 向下移動：與後一個交換順序
                    next_idx = active_wos.index[move_idx + 1]
                    next_order = active_wos.iloc[move_idx + 1]["排程順序"]
                    st.session_state.work_orders_db.at[active_wos.index[move_idx], "排程順序"] = next_order
                    st.session_state.work_orders_db.at[next_idx, "排程順序"] = current_order
                    st.session_state.work_orders_db = dm.normalize_sequences(st.session_state.work_orders_db)
                    save_data()
                    st.toast(f"✅ 已向下移動")
                    st.session_state[move_key] = None
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.session_state[move_key] = None
            
            # 初始化刪除選項狀態
            delete_checkbox_key = f"delete_checkbox_{target_line}"
            clear_checkboxes_key = f"clear_checkboxes_{target_line}"
            
            # 檢查是否需要清除 checkbox 狀態（在 widget 創建之前清除）
            if clear_checkboxes_key in st.session_state:
                clear_flag = st.session_state[clear_checkboxes_key]
                if clear_flag == "all":
                    # 清除所有該產線的 checkbox 狀態
                    keys_to_delete = [key for key in st.session_state.keys() if key.startswith(f"del_{target_line}_")]
                    for key in keys_to_delete:
                        del st.session_state[key]
                elif isinstance(clear_flag, list):
                    # 清除特定索引的 checkbox 狀態
                    for idx in clear_flag:
                        checkbox_key = f"del_{target_line}_{idx}"
                        if checkbox_key in st.session_state:
                            del st.session_state[checkbox_key]
                # 清除標記
                del st.session_state[clear_checkboxes_key]
            
            if delete_checkbox_key not in st.session_state:
                st.session_state[delete_checkbox_key] = {}
            # 確保所有當前索引都存在於狀態中
            for idx in display_df.index:
                if idx not in st.session_state[delete_checkbox_key]:
                    st.session_state[delete_checkbox_key][idx] = False
            # 移除已不存在的索引（已刪除的項目）
            existing_indices = set(display_df.index)
            st.session_state[delete_checkbox_key] = {
                idx: st.session_state[delete_checkbox_key][idx] 
                for idx in st.session_state[delete_checkbox_key] 
                if idx in existing_indices
            }
            
            col_q1, col_q2 = st.columns([4, 1])
            with col_q1:
                # 添加自定義 CSS 優化上下鈕和表格布局
                st.markdown("""
                <style>
                /* 按鈕容器：使用 flexbox 確保水平排列和對齊 */
                .sort-buttons-container {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    align-items: center !important;
                    justify-content: center !important;
                    gap: 0.3rem !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    width: 100% !important;
                }
                
                /* Streamlit 按鈕包裝器樣式 - 關鍵：強制水平排列，不換行 */
                .sort-buttons-container > .stButton {
                    display: inline-flex !important;
                    flex: 0 0 auto !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    width: 2rem !important;
                    min-width: 2rem !important;
                    max-width: 2rem !important;
                    flex-shrink: 0 !important;
                    vertical-align: middle !important;
                }
                
                /* 按鈕本身樣式 - 增強視覺效果，讓操作者知道可以點選 */
                /* 針對 secondary 類型的箭頭按鈕 - 最高優先級 */
                button.sort-arrow-button,
                button.sort-arrow-button[kind="secondary"],
                .stButton button.sort-arrow-button,
                button[kind="secondary"][data-testid*="move_up_"],
                button[kind="secondary"][data-testid*="move_down_"],
                button[data-testid*="move_up_"],
                button[data-testid*="move_down_"] {
                    width: 2.5rem !important;
                    min-width: 2.5rem !important;
                    max-width: 2.5rem !important;
                    height: 2.2rem !important;
                    min-height: 2.2rem !important;
                    max-height: 2.2rem !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    flex-shrink: 0 !important;
                    text-align: center !important;
                    line-height: 1 !important;
                    background-color: #4fc3f7 !important;
                    background: #4fc3f7 !important;
                    border: 2px solid #0288d1 !important;
                    border-color: #0288d1 !important;
                    color: #ffffff !important;
                    font-weight: 900 !important;
                    font-size: 1.4rem !important;
                    box-shadow: 0 2px 4px rgba(2, 136, 209, 0.3), 0 1px 2px rgba(2, 136, 209, 0.2) !important;
                    border-radius: 6px !important;
                    transition: all 0.2s ease !important;
                    cursor: pointer !important;
                }
                
                /* 上下箭頭按鈕 hover 效果 */
                button.sort-arrow-button:hover:not(:disabled),
                button[kind="secondary"][data-testid*="move_up_"]:hover:not(:disabled),
                button[kind="secondary"][data-testid*="move_down_"]:hover:not(:disabled),
                button[data-testid*="move_up_"]:hover:not(:disabled),
                button[data-testid*="move_down_"]:hover:not(:disabled) {
                    background-color: #29b6f6 !important;
                    background: #29b6f6 !important;
                    border-color: #0277bd !important;
                    box-shadow: 0 4px 8px rgba(2, 136, 209, 0.4), 0 2px 4px rgba(2, 136, 209, 0.3) !important;
                    transform: translateY(-1px) !important;
                }
                
                /* 按鈕 hover 狀態 - 更深的藍色 */
                button.sort-arrow-button:hover:not(:disabled),
                button[kind="secondary"][data-testid*="move_up_"]:hover:not(:disabled),
                button[kind="secondary"][data-testid*="move_down_"]:hover:not(:disabled),
                button[data-testid*="move_up_"]:hover:not(:disabled),
                button[data-testid*="move_down_"]:hover:not(:disabled) {
                    background-color: #81d4fa !important;
                    background: #81d4fa !important;
                    border-color: #4fc3f7 !important;
                }
                
                /* 確保按鈕內的文字/符號置中，加粗箭頭 */
                button.sort-arrow-button p,
                button.sort-arrow-button[kind="secondary"] p,
                .stButton button.sort-arrow-button p,
                button[kind="secondary"][data-testid*="move_up_"] p,
                button[kind="secondary"][data-testid*="move_down_"] p,
                button[data-testid*="move_up_"] p,
                button[data-testid*="move_down_"] p {
                    margin: 0 !important;
                    padding: 0 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    width: 100% !important;
                    height: 100% !important;
                    line-height: 1 !important;
                    text-align: center !important;
                    font-weight: 900 !important;
                    font-size: 1.2rem !important;
                    color: #01579b !important;
                }
                
                /* 表格列間距優化 - 更緊湊，強制減少行高 */
                /* 只針對表格行內的 columns（通過 JavaScript 添加 .table-row-column 類別） */
                div[data-testid="column"].table-row-column {
                    padding: 0.05rem 0.2rem !important;
                    min-height: 0 !important;
                    height: auto !important;
                    max-height: none !important;
                }
                
                /* 強制減少表格行的整體高度 - 只針對表格行內的 columns */
                div[data-testid="column"].table-row-column > div,
                div[data-testid="column"].table-row-column > div > div,
                div[data-testid="column"].table-row-column > div > div > div {
                    min-height: 0 !important;
                    height: auto !important;
                    max-height: none !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    line-height: 1.2 !important;
                }
                
                /* 確保操作按鈕的 columns 保持正常高度 */
                div[data-testid="column"]:not(.table-row-column) {
                    min-height: auto !important;
                    padding: 0.5rem 0.2rem !important;
                }
                
                /* 通過 JavaScript 添加的樣式標記 - 確保操作按鈕有足夠高度 */
                button.action-button-primary,
                div[data-testid="stButton"]:has(button.action-button-primary) {
                    min-height: 3.5rem !important;
                    height: auto !important;
                    padding: 0.75rem 1.5rem !important;
                    font-size: 1.1rem !important;
                    line-height: 1.6 !important;
                }
                
                button.action-button-primary {
                    min-height: 3.5rem !important;
                    height: auto !important;
                    padding: 0.75rem 1.5rem !important;
                    font-size: 1.1rem !important;
                    line-height: 1.6 !important;
                }
                
                /* 表格行間距優化 - 更緊湊 */
                hr {
                    margin: 0.05rem 0 !important;
                    border-color: #e0e0e0 !important;
                    height: 1px !important;
                    border-width: 1px !important;
                }
                
                /* 文字內容對齊 - 減少間距 */
                .stMarkdown {
                    padding: 0 !important;
                    margin: 0 !important;
                    line-height: 1.2 !important;
                    min-height: 0 !important;
                    height: auto !important;
                }
                
                /* 表頭文字樣式 - 更緊湊 */
                div[data-testid="column"] div[style*="font-weight: bold"] {
                    padding: 0.1rem 0 !important;
                    margin: 0 !important;
                    font-size: 0.95rem !important;
                    line-height: 1.2 !important;
                }
                
                /* 減少 checkbox 的高度 */
                div[data-testid="stCheckbox"],
                div[data-testid="stCheckbox"] > label,
                div[data-testid="stCheckbox"] > div,
                div[data-testid="stCheckbox"] > label > div {
                    min-height: 0 !important;
                    height: auto !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    line-height: 1 !important;
                }
                
                /* 減少按鈕容器的高度 - 只在佇列管理頁面的表格行內 */
                /* 只針對表格行內的按鈕容器，不影響其他頁面 */
                div[data-testid="column"].table-row-column div[data-testid="stButton"]:not(:has(button.action-button-primary)),
                div[data-testid="column"].table-row-column div[data-testid="stButton"]:not(:has(button.action-button-primary)) > button:not(.action-button-primary),
                div[data-testid="column"].table-row-column div[data-testid="stButton"]:not(:has(button.action-button-primary)) > div {
                    min-height: 0 !important;
                    height: auto !important;
                    padding: 0 !important;
                    margin: 0 !important;
                }
                
                /* 確保操作按鈕容器有足夠高度 - 只在佇列管理頁面，增強視覺效果 */
                button.action-button-primary,
                div[data-testid="stButton"]:has(button.action-button-primary) button.action-button-primary {
                    min-height: 4rem !important;
                    height: auto !important;
                    padding: 1rem 2rem !important;
                    font-size: 1.2rem !important;
                    font-weight: 700 !important;
                    line-height: 1.5 !important;
                    box-shadow: 0 4px 8px rgba(231, 76, 60, 0.3), 0 2px 4px rgba(231, 76, 60, 0.2) !important;
                    border: 2px solid #c0392b !important;
                    border-radius: 8px !important;
                    transition: all 0.3s ease !important;
                }
                
                button.action-button-primary:hover {
                    box-shadow: 0 6px 12px rgba(231, 76, 60, 0.4), 0 4px 6px rgba(231, 76, 60, 0.3) !important;
                    transform: translateY(-2px) !important;
                    background-color: #ec7063 !important;
                }
                
                /* 強制所有 Streamlit 組件緊湊 - 只在表格行內 */
                div[data-testid="column"].table-row-column * {
                    line-height: 1.2 !important;
                }
                
                /* 特別針對包含表格行的容器 */
                div[data-testid="column"].table-row-column:has(div[style*="text-align: center"]) {
                    min-height: 0 !important;
                    height: auto !important;
                }
                </style>
                <script>
                (function() {
                    // #region agent log
                    try {
                        fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:425',message:'Script loaded',data:{readyState:document.readyState,timestamp:Date.now()},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'A'})}).catch(()=>{});
                    } catch(e) {}
                    // #endregion
                    
                    function adjustSortButtons() {
                        // #region agent log
                        try {
                            fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:427',message:'adjustSortButtons called',data:{timestamp:Date.now()},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'A'})}).catch(()=>{});
                        } catch(e) {}
                        // #endregion
                        
                        // 找到所有按鈕
                        const allButtons = document.querySelectorAll('button');
                        const secondaryButtons = document.querySelectorAll('button[kind="secondary"]');
                        
                        // 使用 MutationObserver 監聽按鈕樣式變化
                        if (!window.sortButtonObserver) {
                            window.sortButtonObserver = new MutationObserver(function(mutations) {
                                mutations.forEach(function(mutation) {
                                    if (mutation.type === 'attributes') {
                                        const button = mutation.target;
                                        const buttonText = (button.textContent || button.innerText || '').trim();
                                        const testId = button.getAttribute('data-testid') || '';
                                        if ((buttonText === '↑' || buttonText === '↓') || 
                                            testId.includes('move_up_') || testId.includes('move_down_')) {
                                            // 強制重新應用樣式
                                            button.style.setProperty('background-color', '#b3e5fc', 'important');
                                            button.style.setProperty('background', '#b3e5fc', 'important');
                                            button.style.setProperty('border', '1px solid #81d4fa', 'important');
                                            button.style.setProperty('border-color', '#81d4fa', 'important');
                                            button.style.setProperty('color', '#01579b', 'important');
                                            button.style.setProperty('font-weight', '900', 'important');
                                            button.style.setProperty('font-size', '1.2rem', 'important');
                                            button.style.removeProperty('background-image');
                                        }
                                    }
                                });
                            });
                        }
                        
                        // #region agent log
                        try {
                            fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:432',message:'Total buttons found',data:{buttonCount:allButtons.length,secondaryButtonCount:secondaryButtons.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'B'})}).catch(()=>{});
                        } catch(e) {}
                        // #endregion
                        
                        let arrowButtonCount = 0;
                        let allButtonTexts = [];
                        allButtons.forEach((button, index) => {
                            // 獲取按鈕的完整文字內容
                            const buttonText = (button.textContent || button.innerText || '').trim();
                            allButtonTexts.push(buttonText.substring(0, 10));
                            
                            // 檢查是否包含箭頭符號
                            if (buttonText === '↑' || buttonText === '↓' || buttonText.includes('↑') || buttonText.includes('↓')) {
                                // #region agent log
                                try {
                                    const buttonHTML = button.outerHTML.substring(0, 300);
                                    const computedBg = window.getComputedStyle(button).backgroundColor;
                                    const inlineBg = button.style.backgroundColor;
                                    fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:440',message:'Arrow button found',data:{index:index,buttonText:buttonText,buttonHTML:buttonHTML,hasClass:button.classList.contains('sort-arrow-button'),computedBg:computedBg,inlineBg:inlineBg,kind:button.getAttribute('kind')},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'B'})}).catch(()=>{});
                                } catch(e) {}
                                // #endregion
                                arrowButtonCount++;
                                
                                // #region agent log
                                try {
                                    const beforeBg = window.getComputedStyle(button).backgroundColor;
                                    fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:445',message:'Processing arrow button',data:{index:index,buttonText:buttonText,beforeBg:beforeBg},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'C'})}).catch(()=>{});
                                } catch(e) {}
                                // #endregion
                                
                                // 添加特定類別
                                button.classList.add('sort-arrow-button');
                                
                                // 使用 cssText 一次性設置所有樣式（更強制性）
                                const existingStyle = button.getAttribute('style') || '';
                                button.setAttribute('style', existingStyle + '; background-color: #b3e5fc !important; background: #b3e5fc !important; border: 1px solid #81d4fa !important; border-color: #81d4fa !important; height: 1.8rem !important; min-height: 1.8rem !important; max-height: 1.8rem !important; width: 2rem !important; min-width: 2rem !important; max-width: 2rem !important; flex-shrink: 0 !important; margin: 0 !important; padding: 0 !important; display: flex !important; align-items: center !important; justify-content: center !important; box-sizing: border-box !important; text-align: center !important; line-height: 1 !important; color: #01579b !important; font-weight: 900 !important; font-size: 1.2rem !important; white-space: nowrap !important;');
                                
                                // 同時使用 setProperty 作為備用，強制覆蓋 Streamlit 的 secondary 按鈕樣式 - 增強視覺效果
                                button.style.setProperty('background-color', '#4fc3f7', 'important');
                                button.style.setProperty('background', '#4fc3f7', 'important');
                                button.style.setProperty('border', '2px solid #0288d1', 'important');
                                button.style.setProperty('border-color', '#0288d1', 'important');
                                button.style.setProperty('color', '#ffffff', 'important');
                                button.style.setProperty('height', '2.2rem', 'important');
                                button.style.setProperty('width', '2.5rem', 'important');
                                button.style.setProperty('display', 'flex', 'important');
                                button.style.setProperty('align-items', 'center', 'important');
                                button.style.setProperty('justify-content', 'center', 'important');
                                button.style.setProperty('font-weight', '900', 'important');
                                button.style.setProperty('font-size', '1.4rem', 'important');
                                button.style.setProperty('white-space', 'nowrap', 'important');
                                button.style.setProperty('box-shadow', '0 2px 4px rgba(2, 136, 209, 0.3), 0 1px 2px rgba(2, 136, 209, 0.2)', 'important');
                                button.style.setProperty('border-radius', '6px', 'important');
                                button.style.setProperty('transition', 'all 0.2s ease', 'important');
                                button.style.setProperty('cursor', 'pointer', 'important');
                                // 移除可能衝突的背景圖片
                                button.style.removeProperty('background-image');
                                
                                // 添加 hover 效果
                                if (!button.hasAttribute('data-arrow-button-styled')) {
                                    button.setAttribute('data-arrow-button-styled', 'true');
                                    button.onmouseenter = function() {
                                        if (!this.disabled) {
                                            this.style.setProperty('background-color', '#29b6f6', 'important');
                                            this.style.setProperty('background', '#29b6f6', 'important');
                                            this.style.setProperty('border-color', '#0277bd', 'important');
                                            this.style.setProperty('box-shadow', '0 4px 8px rgba(2, 136, 209, 0.4), 0 2px 4px rgba(2, 136, 209, 0.3)', 'important');
                                            this.style.setProperty('transform', 'translateY(-1px)', 'important');
                                        }
                                    };
                                    button.onmouseleave = function() {
                                        if (!this.disabled) {
                                            this.style.setProperty('background-color', '#4fc3f7', 'important');
                                            this.style.setProperty('background', '#4fc3f7', 'important');
                                            this.style.setProperty('border-color', '#0288d1', 'important');
                                            this.style.setProperty('box-shadow', '0 2px 4px rgba(2, 136, 209, 0.3), 0 1px 2px rgba(2, 136, 209, 0.2)', 'important');
                                            this.style.setProperty('transform', 'translateY(0)', 'important');
                                        }
                                    };
                                }
                                
                                // 開始監聽這個按鈕的變化
                                if (window.sortButtonObserver) {
                                    window.sortButtonObserver.observe(button, {
                                        attributes: true,
                                        attributeFilter: ['style', 'class'],
                                        attributeOldValue: false
                                    });
                                }
                                
                                // #region agent log
                                try {
                                    const afterBg = window.getComputedStyle(button).backgroundColor;
                                    const inlineBgAfter = button.style.backgroundColor;
                                    fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:470',message:'After setting styles',data:{index:index,afterBg:afterBg,inlineBgAfter:inlineBgAfter,hasClass:button.classList.contains('sort-arrow-button'),styleAttr:button.getAttribute('style')?.substring(0,100)},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D'})}).catch(()=>{});
                                } catch(e) {}
                                // #endregion
                                
                                // 加粗箭頭符號並置中
                                const textElements = button.querySelectorAll('p, span, div, *');
                                
                                // #region agent log
                                fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:465',message:'Text elements found',data:{index:index,textElementCount:textElements.length,elementTexts:Array.from(textElements).slice(0,5).map(el=>(el.textContent||'').trim())},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
                                // #endregion
                                
                                let foundArrow = false;
                                textElements.forEach(el => {
                                    const elText = (el.textContent || el.innerText || '').trim();
                                    if (elText === '↑' || elText === '↓') {
                                        foundArrow = true;
                                        const existingElStyle = el.getAttribute('style') || '';
                                        el.setAttribute('style', existingElStyle + '; font-weight: 900 !important; font-size: 1.4rem !important; margin: 0 !important; padding: 0 !important; display: flex !important; align-items: center !important; justify-content: center !important; width: 100% !important; height: 100% !important; line-height: 1 !important; text-align: center !important;');
                                        el.style.setProperty('font-weight', '900', 'important');
                                        el.style.setProperty('font-size', '1.4rem', 'important');
                                        el.style.setProperty('display', 'flex', 'important');
                                        el.style.setProperty('align-items', 'center', 'important');
                                        el.style.setProperty('justify-content', 'center', 'important');
                                        el.style.setProperty('text-align', 'center', 'important');
                                        el.style.setProperty('color', '#ffffff', 'important');
                                    }
                                });
                                
                                // 如果沒有找到子元素中的箭頭，直接設置按鈕文字樣式
                                if (!foundArrow) {
                                    const existingBtnStyle = button.getAttribute('style') || '';
                                    button.setAttribute('style', existingBtnStyle + '; font-weight: 900 !important; font-size: 1.4rem !important; text-align: center !important; color: #ffffff !important;');
                                    button.style.setProperty('font-weight', '900', 'important');
                                    button.style.setProperty('font-size', '1.4rem', 'important');
                                    button.style.setProperty('text-align', 'center', 'important');
                                    button.style.setProperty('color', '#ffffff', 'important');
                                }
                                
                                // #region agent log
                                fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:490',message:'Button processing complete',data:{index:index,foundArrow:foundArrow,finalBg:window.getComputedStyle(button).backgroundColor,finalFontWeight:window.getComputedStyle(button).fontWeight},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                                // #endregion
                            } else {
                                // 移除類別，確保不影響其他按鈕
                                button.classList.remove('sort-arrow-button');
                            }
                        });
                        
                        // #region agent log
                        try {
                            fetch('http://127.0.0.1:7242/ingest/0fbab503-97dd-4da2-93ee-ac836863970f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'admin.py:510',message:'adjustSortButtons complete',data:{arrowButtonCount:arrowButtonCount,totalButtons:allButtons.length,sampleButtonTexts:allButtonTexts.slice(0,10)},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'A'})}).catch(()=>{});
                        } catch(e) {}
                        // #endregion
                    }
                    
                    // 強制減少表格行高的函數 - 只針對表格行，排除操作按鈕
                    function compactTableRows() {
                        // 找到所有 columns
                        const columns = document.querySelectorAll('div[data-testid="column"]');
                        columns.forEach(function(col) {
                            // 檢查是否包含主要操作按鈕（排除這些 columns）
                            const buttons = col.querySelectorAll('button');
                            let hasActionButton = false;
                            buttons.forEach(function(btn) {
                                const btnText = (btn.textContent || btn.innerText || '').trim();
                                const testId = btn.getAttribute('data-testid') || '';
                                // 檢查是否是操作按鈕（不是上下箭頭按鈕）
                                // 精確匹配：只匹配「確認加入至...的排程」和「移除選中」
                                if (((btnText.includes('確認加入至') && btnText.includes('的排程')) || 
                                     btnText.includes('移除選中')) &&
                                    !btnText.includes('確認寫入') && 
                                    !btnText.includes('刪除選取') &&
                                    !testId.includes('move_up_') && 
                                    !testId.includes('move_down_')) {
                                    hasActionButton = true;
                                }
                            });
                            
                            // 只處理不包含操作按鈕的 columns（表格行）
                            if (!hasActionButton) {
                                // 添加類別標記，讓 CSS 可以選擇
                                col.classList.add('table-row-column');
                                
                                // 強制設置最小高度為 0
                                col.style.setProperty('min-height', '0', 'important');
                                col.style.setProperty('height', 'auto', 'important');
                                col.style.setProperty('padding-top', '0.05rem', 'important');
                                col.style.setProperty('padding-bottom', '0.05rem', 'important');
                                
                                // 處理所有子元素（排除按鈕和輸入框）
                                const children = col.querySelectorAll('*');
                                children.forEach(function(child) {
                                    if (child.tagName !== 'BUTTON' && child.tagName !== 'INPUT') {
                                        child.style.setProperty('min-height', '0', 'important');
                                        child.style.setProperty('height', 'auto', 'important');
                                        child.style.setProperty('line-height', '1.2', 'important');
                                    }
                                });
                            } else {
                                // 對於包含操作按鈕的 columns，移除類別並恢復正常高度
                                col.classList.remove('table-row-column');
                                col.style.setProperty('min-height', 'auto', 'important');
                                col.style.setProperty('height', 'auto', 'important');
                                col.style.setProperty('padding-top', '0.5rem', 'important');
                                col.style.setProperty('padding-bottom', '0.5rem', 'important');
                                
                                // 確保操作按鈕有足夠的高度
                                // 精確匹配：只匹配「確認加入至...的排程」和「移除選中」
                                buttons.forEach(function(btn) {
                                    const btnText = (btn.textContent || btn.innerText || '').trim();
                                    if (((btnText.includes('確認加入至') && btnText.includes('的排程')) || 
                                         btnText.includes('移除選中')) &&
                                        !btnText.includes('確認寫入') && 
                                        !btnText.includes('刪除選取')) {
                                        btn.classList.add('action-button-primary');
                                        btn.style.setProperty('min-height', '3.5rem', 'important');
                                        btn.style.setProperty('height', 'auto', 'important');
                                        btn.style.setProperty('padding', '0.75rem 1.5rem', 'important');
                                        btn.style.setProperty('font-size', '1.1rem', 'important');
                                        btn.style.setProperty('line-height', '1.6', 'important');
                                    }
                                });
                            }
                        });
                        
                        // 單獨處理所有操作按鈕，確保它們有足夠高度
                        // 精確匹配：只匹配「確認加入至...的排程」和「移除選中」
                        const allButtons = document.querySelectorAll('button');
                        allButtons.forEach(function(btn) {
                            const btnText = (btn.textContent || btn.innerText || '').trim();
                            const testId = btn.getAttribute('data-testid') || '';
                            if (((btnText.includes('確認加入至') && btnText.includes('的排程')) || 
                                 btnText.includes('移除選中')) &&
                                !btnText.includes('確認寫入') && 
                                !btnText.includes('刪除選取') &&
                                !testId.includes('move_up_') && 
                                !testId.includes('move_down_')) {
                                btn.classList.add('action-button-primary');
                                btn.style.setProperty('min-height', '3.5rem', 'important');
                                btn.style.setProperty('height', 'auto', 'important');
                                btn.style.setProperty('padding', '0.75rem 1.5rem', 'important');
                                btn.style.setProperty('font-size', '1.1rem', 'important');
                                btn.style.setProperty('line-height', '1.6', 'important');
                                
                                // 同時處理按鈕容器
                                const btnContainer = btn.closest('div[data-testid="stButton"]');
                                if (btnContainer) {
                                    btnContainer.style.setProperty('min-height', '3.5rem', 'important');
                                    btnContainer.style.setProperty('height', 'auto', 'important');
                                    btnContainer.style.setProperty('padding', '0', 'important');
                                }
                            }
                        });
                    }
                    
                    // 專門處理操作按鈕的函數 - 增強視覺效果
                    // 精確匹配：只匹配「確認加入至...的排程」和「移除選中」
                    function fixActionButtons() {
                        const allButtons = document.querySelectorAll('button');
                        allButtons.forEach(function(btn) {
                            const btnText = (btn.textContent || btn.innerText || '').trim();
                            const testId = btn.getAttribute('data-testid') || '';
                            if (((btnText.includes('確認加入至') && btnText.includes('的排程')) || 
                                 btnText.includes('移除選中')) &&
                                !btnText.includes('確認寫入') && 
                                !btnText.includes('刪除選取') &&
                                !testId.includes('move_up_') && 
                                !testId.includes('move_down_')) {
                                // 強制設置樣式 - 增強視覺效果
                                btn.style.cssText = btn.style.cssText.replace(/min-height[^;]*;?/g, '');
                                btn.style.cssText = btn.style.cssText.replace(/height[^;]*;?/g, '');
                                btn.style.cssText = btn.style.cssText.replace(/padding[^;]*;?/g, '');
                                btn.style.cssText = btn.style.cssText.replace(/box-shadow[^;]*;?/g, '');
                                btn.style.cssText = btn.style.cssText.replace(/border[^;]*;?/g, '');
                                btn.style.setProperty('min-height', '4rem', 'important');
                                btn.style.setProperty('height', 'auto', 'important');
                                btn.style.setProperty('padding', '1rem 2rem', 'important');
                                btn.style.setProperty('font-size', '1.2rem', 'important');
                                btn.style.setProperty('font-weight', '700', 'important');
                                btn.style.setProperty('line-height', '1.5', 'important');
                                btn.style.setProperty('box-shadow', '0 4px 8px rgba(231, 76, 60, 0.3), 0 2px 4px rgba(231, 76, 60, 0.2)', 'important');
                                btn.style.setProperty('border', '2px solid #c0392b', 'important');
                                btn.style.setProperty('border-radius', '8px', 'important');
                                btn.style.setProperty('transition', 'all 0.3s ease', 'important');
                                
                                // 添加 hover 效果
                                if (!btn.hasAttribute('data-action-button-styled')) {
                                    btn.setAttribute('data-action-button-styled', 'true');
                                    btn.onmouseenter = function() {
                                        this.style.setProperty('box-shadow', '0 6px 12px rgba(231, 76, 60, 0.4), 0 4px 6px rgba(231, 76, 60, 0.3)', 'important');
                                        this.style.setProperty('transform', 'translateY(-2px)', 'important');
                                        this.style.setProperty('background-color', '#ec7063', 'important');
                                    };
                                    btn.onmouseleave = function() {
                                        this.style.setProperty('box-shadow', '0 4px 8px rgba(231, 76, 60, 0.3), 0 2px 4px rgba(231, 76, 60, 0.2)', 'important');
                                        this.style.setProperty('transform', 'translateY(0)', 'important');
                                        this.style.setProperty('background-color', '#e74c3c', 'important');
                                    };
                                }
                                
                                // 處理按鈕容器
                                const btnContainer = btn.closest('div[data-testid="stButton"]');
                                if (btnContainer) {
                                    btnContainer.style.setProperty('min-height', '4rem', 'important');
                                    btnContainer.style.setProperty('height', 'auto', 'important');
                                }
                                
                                // 處理父 column
                                const parentCol = btn.closest('div[data-testid="column"]');
                                if (parentCol) {
                                    parentCol.style.setProperty('min-height', 'auto', 'important');
                                    parentCol.style.setProperty('padding-top', '1rem', 'important');
                                    parentCol.style.setProperty('padding-bottom', '1rem', 'important');
                                }
                            }
                        });
                    }
                    
                    // 立即執行
                    adjustSortButtons();
                    compactTableRows();
                    fixActionButtons();
                    
                    // 頁面載入時執行
                    if (document.readyState === 'loading') {
                        document.addEventListener('DOMContentLoaded', function() {
                            adjustSortButtons();
                            compactTableRows();
                            fixActionButtons();
                        });
                    } else {
                        adjustSortButtons();
                        compactTableRows();
                        fixActionButtons();
                    }
                    
                    // 監聽 DOM 變化（Streamlit 動態更新時）- 增強版
                    const observer = new MutationObserver(function(mutations) {
                        let shouldAdjust = false;
                        mutations.forEach(function(mutation) {
                            if (mutation.type === 'childList') {
                                mutation.addedNodes.forEach(function(node) {
                                    if (node.nodeType === 1) { // Element node
                                        if (node.tagName === 'BUTTON' || node.querySelectorAll) {
                                            const buttons = node.tagName === 'BUTTON' ? [node] : node.querySelectorAll('button');
                                            buttons.forEach(function(btn) {
                                                const txt = (btn.textContent || btn.innerText || '').trim();
                                                const testId = btn.getAttribute('data-testid') || '';
                                                if (txt === '↑' || txt === '↓' || testId.includes('move_up_') || testId.includes('move_down_')) {
                                                    shouldAdjust = true;
                                                }
                                            });
                                        }
                                        // 檢查是否是新的 column
                                        if (node.getAttribute && node.getAttribute('data-testid') === 'column') {
                                            shouldAdjust = true;
                                        }
                                    }
                                });
                            }
                        });
                        if (shouldAdjust) {
                            setTimeout(function() {
                                adjustSortButtons();
                                compactTableRows();
                                fixActionButtons();
                            }, 10);
                        } else {
                            // 即使沒有特定變化，也定期緊湊行高和修復按鈕
                            compactTableRows();
                            fixActionButtons();
                        }
                    });
                    observer.observe(document.body, { 
                        childList: true, 
                        subtree: true,
                        attributes: false
                    });
                    
                    // 定期檢查（備用方案）- 更頻繁執行
                    setInterval(function() {
                        adjustSortButtons();
                        compactTableRows();
                        fixActionButtons();
                    }, 100);
                    
                    // 延遲執行，確保 DOM 完全載入
                    setTimeout(function() { adjustSortButtons(); compactTableRows(); fixActionButtons(); }, 50);
                    setTimeout(function() { adjustSortButtons(); compactTableRows(); fixActionButtons(); }, 150);
                    setTimeout(function() { adjustSortButtons(); compactTableRows(); fixActionButtons(); }, 300);
                    setTimeout(function() { adjustSortButtons(); compactTableRows(); fixActionButtons(); }, 500);
                    setTimeout(function() { adjustSortButtons(); compactTableRows(); fixActionButtons(); }, 1000);
                })();
                </script>
                """, unsafe_allow_html=True)
                
                # 創建自定義表格，將上下按鈕放在排序欄位前方
                # 表頭 - 優化欄位寬度分配，確保對齊工整
                # 添加緊湊表頭的 CSS
                st.markdown("""
                <style>
                /* 針對表頭的 columns 強制緊湊高度 */
                div[data-testid="column"]:has(div[style*="font-weight: bold"]) {
                    min-height: 0 !important;
                    height: auto !important;
                    padding-top: 0.15rem !important;
                    padding-bottom: 0.15rem !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                header_cols = st.columns([0.35, 0.3, 0.5, 0.9, 0.6, 0.5, 0.5, 1.3, 0.75, 0.75, 0.75], gap="small")
                for i, col in enumerate(header_cols):
                    with col:
                        if i == 0:  # 刪除
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">刪除</div>', unsafe_allow_html=True)
                        elif i == 1:  # 排序
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">排序</div>', unsafe_allow_html=True)
                        elif i == 2:  # 上下按鈕欄位（空白）
                            st.write("")
                        elif i == 3:  # 客戶名
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">客戶名</div>', unsafe_allow_html=True)
                        elif i == 4:  # 品種
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">品種</div>', unsafe_allow_html=True)
                        elif i == 5:  # 溫度
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">溫度</div>', unsafe_allow_html=True)
                        elif i == 6:  # 密度
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">密度</div>', unsafe_allow_html=True)
                        elif i == 7:  # 規格
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">規格</div>', unsafe_allow_html=True)
                        elif i == 8:  # 準重
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">準重</div>', unsafe_allow_html=True)
                        elif i == 9:  # 預計數量
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">預計數量</div>', unsafe_allow_html=True)
                        elif i == 10:  # 已完成
                            st.markdown('<div style="font-weight: bold; text-align: center; white-space: nowrap; writing-mode: horizontal-tb;">已完成</div>', unsafe_allow_html=True)
                
                st.markdown('<hr style="margin: 0.15rem 0;">', unsafe_allow_html=True)
                
                # 資料行 - 使用與表頭相同的欄位寬度
                for idx, (db_idx, row) in enumerate(display_df.iterrows()):
                    row_cols = st.columns([0.35, 0.3, 0.5, 0.9, 0.6, 0.5, 0.5, 1.3, 0.75, 0.75, 0.75])
                    
                    with row_cols[0]:  # 刪除選項框
                        # 使用容器來置中選項框，減少間距
                        st.markdown('<div style="display: flex; justify-content: center; align-items: center; padding: 0.05rem 0;">', unsafe_allow_html=True)
                        checkbox_key = f"del_{target_line}_{db_idx}"
                        checkbox_value = st.checkbox(
                            "", 
                            value=st.session_state.get(checkbox_key, False),
                            key=checkbox_key,
                            label_visibility="collapsed"
                        )
                        # 同步更新到我們的狀態字典
                        st.session_state[delete_checkbox_key][db_idx] = checkbox_value
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with row_cols[1]:  # 排序號碼
                        st.markdown(f'<div style="text-align: center; padding: 0.1rem 0; font-weight: 500;">{row["排序"]}</div>', unsafe_allow_html=True)
                    
                    with row_cols[2]:  # 上下按鈕
                        # 使用 columns 強制水平排列
                        disabled_up = (idx == 0)
                        disabled_down = (idx == len(display_df) - 1)
                        btn_col1, btn_col2 = st.columns([1, 1], gap="small")
                        # 減少按鈕列的間距
                        st.markdown("""
                        <style>
                        div[data-testid="column"]:has(button[data-testid*="move_up_"]),
                        div[data-testid="column"]:has(button[data-testid*="move_down_"]) {
                            padding: 0.05rem 0.1rem !important;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        with btn_col1:
                            btn_up_key = f"move_up_{target_line}_{idx}"
                            if st.button("↑", key=btn_up_key, disabled=disabled_up, use_container_width=True, type="secondary"):
                                st.session_state[move_key] = ("up", idx)
                                st.rerun()
                        with btn_col2:
                            btn_down_key = f"move_down_{target_line}_{idx}"
                            if st.button("↓", key=btn_down_key, disabled=disabled_down, use_container_width=True, type="secondary"):
                                st.session_state[move_key] = ("down", idx)
                                st.rerun()
                        
                        # 在按鈕創建後立即強制應用樣式（使用更強力的方法）
                        st.markdown(f"""
                        <script>
                        (function() {{
                            function forceStyleArrowButtons() {{
                                // 方法1: 通過 data-testid 查找
                                const btnUp = document.querySelector('button[data-testid*="{btn_up_key}"]');
                                const btnDown = document.querySelector('button[data-testid*="{btn_down_key}"]');
                                
                                // 方法2: 通過文字內容查找（備用）
                                const allButtons = document.querySelectorAll('button');
                                let foundUp = btnUp;
                                let foundDown = btnDown;
                                
                                if (!foundUp || !foundDown) {{
                                    allButtons.forEach(function(btn) {{
                                        const txt = (btn.textContent || btn.innerText || '').trim();
                                        if (txt === '↑' && !foundUp) {{
                                            const testId = btn.getAttribute('data-testid') || '';
                                            if (testId.includes('move_up_')) foundUp = btn;
                                        }}
                                        if (txt === '↓' && !foundDown) {{
                                            const testId = btn.getAttribute('data-testid') || '';
                                            if (testId.includes('move_down_')) foundDown = btn;
                                        }}
                                    }});
                                }}
                                
                                function applyStyles(btn) {{
                                    if (!btn) return;
                                    
                                    // 使用 cssText 一次性設置所有樣式（最強力）- 增強視覺效果
                                    btn.style.cssText = `
                                        background-color: #4fc3f7 !important;
                                        background: #4fc3f7 !important;
                                        border: 2px solid #0288d1 !important;
                                        border-color: #0288d1 !important;
                                        color: #ffffff !important;
                                        width: 2.5rem !important;
                                        min-width: 2.5rem !important;
                                        max-width: 2.5rem !important;
                                        height: 2.2rem !important;
                                        min-height: 2.2rem !important;
                                        max-height: 2.2rem !important;
                                        padding: 0 !important;
                                        margin: 0 !important;
                                        display: flex !important;
                                        align-items: center !important;
                                        justify-content: center !important;
                                        text-align: center !important;
                                        font-weight: 900 !important;
                                        font-size: 1.4rem !important;
                                        white-space: nowrap !important;
                                        border-radius: 6px !important;
                                        cursor: pointer !important;
                                        box-shadow: 0 2px 4px rgba(2, 136, 209, 0.3), 0 1px 2px rgba(2, 136, 209, 0.2) !important;
                                        transition: all 0.2s ease !important;
                                    `;
                                    
                                    // 同時使用 setProperty 確保
                                    btn.style.setProperty('background-color', '#4fc3f7', 'important');
                                    btn.style.setProperty('background', '#4fc3f7', 'important');
                                    btn.style.setProperty('border', '2px solid #0288d1', 'important');
                                    btn.style.setProperty('border-color', '#0288d1', 'important');
                                    btn.style.setProperty('color', '#ffffff', 'important');
                                    btn.style.setProperty('font-weight', '900', 'important');
                                    btn.style.setProperty('font-size', '1.4rem', 'important');
                                    btn.style.setProperty('box-shadow', '0 2px 4px rgba(2, 136, 209, 0.3), 0 1px 2px rgba(2, 136, 209, 0.2)', 'important');
                                    btn.style.setProperty('border-radius', '6px', 'important');
                                    btn.style.setProperty('transition', 'all 0.2s ease', 'important');
                                    
                                    // 添加 hover 效果
                                    if (!btn.hasAttribute('data-arrow-button-styled')) {{
                                        btn.setAttribute('data-arrow-button-styled', 'true');
                                        btn.onmouseenter = function() {{
                                            if (!this.disabled) {{
                                                this.style.setProperty('background-color', '#29b6f6', 'important');
                                                this.style.setProperty('background', '#29b6f6', 'important');
                                                this.style.setProperty('border-color', '#0277bd', 'important');
                                                this.style.setProperty('box-shadow', '0 4px 8px rgba(2, 136, 209, 0.4), 0 2px 4px rgba(2, 136, 209, 0.3)', 'important');
                                                this.style.setProperty('transform', 'translateY(-1px)', 'important');
                                            }}
                                        }};
                                        btn.onmouseleave = function() {{
                                            if (!this.disabled) {{
                                                this.style.setProperty('background-color', '#4fc3f7', 'important');
                                                this.style.setProperty('background', '#4fc3f7', 'important');
                                                this.style.setProperty('border-color', '#0288d1', 'important');
                                                this.style.setProperty('box-shadow', '0 2px 4px rgba(2, 136, 209, 0.3), 0 1px 2px rgba(2, 136, 209, 0.2)', 'important');
                                                this.style.setProperty('transform', 'translateY(0)', 'important');
                                            }}
                                        }};
                                    }}
                                    
                                    // 處理內部元素
                                    const textEls = btn.querySelectorAll('p, span, div, *');
                                    textEls.forEach(function(el) {{
                                        const elText = (el.textContent || el.innerText || '').trim();
                                        if (elText === '↑' || elText === '↓') {{
                                            el.style.cssText = `
                                                margin: 0 !important;
                                                padding: 0 !important;
                                                display: flex !important;
                                                align-items: center !important;
                                                justify-content: center !important;
                                                width: 100% !important;
                                                height: 100% !important;
                                                font-weight: 900 !important;
                                                font-size: 1.4rem !important;
                                                color: #ffffff !important;
                                            `;
                                        }}
                                    }});
                                }}
                                
                                applyStyles(foundUp);
                                applyStyles(foundDown);
                            }}
                            
                            // 立即執行多次
                            forceStyleArrowButtons();
                            setTimeout(forceStyleArrowButtons, 10);
                            setTimeout(forceStyleArrowButtons, 50);
                            setTimeout(forceStyleArrowButtons, 100);
                            setTimeout(forceStyleArrowButtons, 200);
                            setTimeout(forceStyleArrowButtons, 500);
                            
                            // 監聽 DOM 變化
                            const observer = new MutationObserver(function() {{
                                forceStyleArrowButtons();
                            }});
                            observer.observe(document.body, {{ childList: true, subtree: true }});
                            
                            // 定期檢查
                            setInterval(forceStyleArrowButtons, 50);
                        }})();
                        </script>
                        """, unsafe_allow_html=True)
                    
                    # 其他欄位（全部置中對齊，減少 padding - 更緊湊）
                    with row_cols[3]:  # 客戶名
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{row.get("客戶名", row.get("內容", ""))}</div>', unsafe_allow_html=True)
                    with row_cols[4]:  # 品種
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{row.get("品種", "")}</div>', unsafe_allow_html=True)
                    with row_cols[5]:  # 溫度
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{row.get("溫度", "")}</div>', unsafe_allow_html=True)
                    with row_cols[6]:  # 密度
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{row.get("密度", "")}</div>', unsafe_allow_html=True)
                    with row_cols[7]:  # 規格
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{row.get("規格", "")}</div>', unsafe_allow_html=True)
                    with row_cols[8]:  # 準重
                        value = f"{row.get('準重', 0):.3f}" if pd.notna(row.get('準重')) else ""
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{value}</div>', unsafe_allow_html=True)
                    with row_cols[9]:  # 預計數量
                        value = int(row.get("預計數量", 0)) if pd.notna(row.get("預計數量")) else 0
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{value}</div>', unsafe_allow_html=True)
                    with row_cols[10]:  # 已完成
                        value = int(row.get("已完成", 0)) if pd.notna(row.get("已完成")) else 0
                        st.markdown(f'<div style="text-align: center; padding: 0.05rem 0;">{value}</div>', unsafe_allow_html=True)
                    
                    if idx < len(display_df) - 1:
                        st.markdown('<hr style="margin: 0.1rem 0;">', unsafe_allow_html=True)
                
                # 計算並顯示總重量（準重 * (預計數量 - 已完成數量)）
                total_weight = 0
                for db_idx, row in display_df.iterrows():
                    standard_weight = row.get('準重', 0)
                    estimated_qty = row.get('預計數量', 0)
                    completed_qty = row.get('已完成', 0)
                    if pd.notna(standard_weight) and pd.notna(estimated_qty):
                        try:
                            remaining_qty = float(estimated_qty) - float(completed_qty) if pd.notna(completed_qty) else float(estimated_qty)
                            if remaining_qty > 0:  # 只計算剩餘待生產的重量
                                total_weight += float(standard_weight) * remaining_qty
                        except (ValueError, TypeError):
                            pass
                
                # 顯示總重量
                st.markdown('<hr style="margin: 0.5rem 0;">', unsafe_allow_html=True)
                st.markdown(f'<div style="text-align: center; font-weight: bold; font-size: 1.1rem; padding: 0.5rem 0; color: #1976d2;">總重量: {int(total_weight)} kg</div>', unsafe_allow_html=True)
            
            with col_q2:
                st.write("")  # 空白行
                # 刪除工單按鈕（需要二次確認）
                # 確保按鈕有足夠高度（通過 JavaScript 處理，這裡的 CSS 僅作為備用）
                st.markdown("""
                <style>
                button.action-button-primary {
                    min-height: 3.5rem !important;
                    height: auto !important;
                    padding: 0.75rem 1.5rem !important;
                    font-size: 1.1rem !important;
                    line-height: 1.6 !important;
                }
                </style>
                """, unsafe_allow_html=True)
                if st.button(f"🗑️ 移除選中", type="primary", width='stretch'):
                    # 收集要刪除的工單資訊 - 從 session_state 中直接讀取 checkbox 狀態
                    indices_to_remove = []
                    for db_idx in display_df.index:
                        checkbox_key = f"del_{target_line}_{db_idx}"
                        if st.session_state.get(checkbox_key, False):
                            indices_to_remove.append(db_idx)
                    
                    if indices_to_remove:
                        try:
                            # 驗證索引是否存在於 work_orders_db 中
                            valid_indices = [idx for idx in indices_to_remove if idx in st.session_state.work_orders_db.index]
                            
                            if not valid_indices:
                                st.error("❌ 無法找到要刪除的工單（索引不匹配）")
                                st.rerun()
                            
                            # 使用有效的索引獲取工單號碼
                            ids_to_delete = st.session_state.work_orders_db.loc[valid_indices, "工單號碼"].tolist()
                            
                            if not ids_to_delete:
                                st.warning("⚠️ 無法獲取工單號碼")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ 處理工單時發生錯誤: {e}")
                            st.rerun()
                        
                        # 準備要顯示的工單資訊（移除備註，加入數量）
                        work_order_info_list = []
                        for idx in valid_indices:
                            try:
                                wo_row = st.session_state.work_orders_db.loc[idx]
                                wo_id = wo_row["工單號碼"]
                                
                                # 重新生成工單資訊，移除備註，加入數量
                                # 先取得產品資訊
                                product_id = wo_row.get("產品ID", "")
                                wo_display = wo_row.get("顯示內容", "")
                                
                                # 如果有產品ID，從products_db取得詳細資訊
                                if product_id and not st.session_state.products_db.empty:
                                    product_match = st.session_state.products_db[st.session_state.products_db["產品ID"] == product_id]
                                    if not product_match.empty:
                                        product_row = product_match.iloc[0]
                                        # 檢查是否有客戶名
                                        if "客戶名" in product_row and pd.notna(product_row["客戶名"]):
                                            # 格式：[客戶名] | 溫度等級 | 品種 | 密度 | 規格 | 準重kg | 數量
                                            client_name = product_row["客戶名"]
                                            temp_level = product_row.get("溫度等級", "")
                                            variety = product_row.get("品種", "")
                                            
                                            # 密度
                                            density_str = ""
                                            density_val = product_row.get("密度", "")
                                            if pd.notna(density_val) and str(density_val).strip() != "":
                                                try:
                                                    density_str = f"{float(density_val):.1f} | "
                                                except (ValueError, TypeError):
                                                    density_str = f"{density_val} | "
                                            
                                            # 規格
                                            spec = f"{dm.format_size(product_row.get('長', 0))}x{dm.format_size(product_row.get('寬', 0))}x{dm.format_size(product_row.get('高', 0))}"
                                            
                                            # 準重
                                            weight = wo_row.get("準重", product_row.get("準重", 0))
                                            weight_str = f"{float(weight):.3f}kg" if pd.notna(weight) else "0kg"
                                            
                                            # 數量
                                            qty = wo_row.get("預計數量", 0)
                                            qty_str = f"數:{int(qty)}" if pd.notna(qty) else "數:0"
                                            
                                            wo_info = f"[{client_name}] | {temp_level} | {variety} | {density_str}{spec} | {weight_str} | {qty_str}"
                                        else:
                                            # 沒有客戶名，使用顯示內容但移除備註，加入數量
                                            # 移除備註部分（通常備註在最後，用 | 分隔）
                                            parts = wo_display.split(" | ")
                                            # 過濾掉包含「備註」的部分
                                            filtered_parts = [p for p in parts if "備註" not in p]
                                            # 加入數量
                                            qty = wo_row.get("預計數量", 0)
                                            qty_str = f"數:{int(qty)}" if pd.notna(qty) else "數:0"
                                            wo_info = " | ".join(filtered_parts) + f" | {qty_str}" if filtered_parts else f"{wo_display} | {qty_str}"
                                    else:
                                        # 找不到產品，使用顯示內容但移除備註，加入數量
                                        parts = wo_display.split(" | ")
                                        filtered_parts = [p for p in parts if "備註" not in p]
                                        qty = wo_row.get("預計數量", 0)
                                        qty_str = f"數:{int(qty)}" if pd.notna(qty) else "數:0"
                                        wo_info = " | ".join(filtered_parts) + f" | {qty_str}" if filtered_parts else f"{wo_display} | {qty_str}"
                                else:
                                    # 沒有產品ID，使用顯示內容但移除備註，加入數量
                                    parts = wo_display.split(" | ")
                                    filtered_parts = [p for p in parts if "備註" not in p]
                                    qty = wo_row.get("預計數量", 0)
                                    qty_str = f"數:{int(qty)}" if pd.notna(qty) else "數:0"
                                    wo_info = " | ".join(filtered_parts) + f" | {qty_str}" if filtered_parts else f"{wo_display} | {qty_str}"
                                
                                work_order_info_list.append(wo_info)
                            except (KeyError, IndexError) as e:
                                continue
                        
                        if not work_order_info_list:
                            st.warning("⚠️ 無法獲取工單資訊")
                            st.rerun()
                        
                        # 保存要清除的 checkbox keys（在下次渲染時清除）
                        clear_checkboxes_key = f"clear_checkboxes_{target_line}"
                        st.session_state[clear_checkboxes_key] = valid_indices
                        
                        # 保存到 session_state 以便對話框使用
                        st.session_state[delete_wo_ids_key] = ids_to_delete
                        st.session_state[delete_wo_info_key] = work_order_info_list
                        
                        # 打開確認對話框
                        st.session_state[dialog_key] = True
                        st.session_state[dialog_closed_key] = False
                        st.rerun()
                    else:
                        st.warning("⚠️ 請先勾選要刪除的工單")
            
            # 顯示確認對話框（在按鈕區塊之外，確保對話框能正確顯示）
            should_show_dialog = (
                st.session_state.get(dialog_key, False) and 
                not st.session_state.get(dialog_closed_key, False)
            )
            
            if should_show_dialog:
                ids_to_delete = st.session_state.get(delete_wo_ids_key, [])
                work_order_info_list = st.session_state.get(delete_wo_info_key, [])
                if ids_to_delete and work_order_info_list:
                    show_delete_work_orders_confirm(target_line, ids_to_delete, work_order_info_list)
        else: st.info(f"{target_line} 目前無工單")
    else:
        st.info("👆 請點選上方按鈕，選擇要管理的產線")


def render_reports():
    """生產報表中心"""
    st.markdown('<div class="section-header header-admin">📊 每日生產統計報表</div>', unsafe_allow_html=True)
    
    logs = st.session_state.production_logs.copy(); final_cols = ['Line.', '日期', '班別', '組別', '溫度等級', '品種', '密度', '長度', '寬度', '厚度', '數量', '標準重量', '總計']
    if logs.empty: 
        st.warning("⚠️ 無紀錄。"); current_year = datetime.now().year; years = [current_year]
    else:
        logs['datetime'] = logs['時間'].apply(dm.parse_log_time); logs['Year'] = logs['datetime'].dt.year; logs['Month'] = logs['datetime'].dt.month; years = sorted(logs['Year'].unique(), reverse=True)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        sel_year = st.selectbox("請選擇年份", years, key="rpt_year")
    with col_d2:
        if not logs.empty: months = sorted(logs[logs['Year'] == sel_year]['Month'].unique(), reverse=True)
        else: months = range(1, 13)
        sel_month = st.selectbox("請選擇月份", months, key="rpt_month")
        
    if not logs.empty: filtered_logs = logs[(logs['Year'] == sel_year) & (logs['Month'] == sel_month)].copy()
    else: filtered_logs = pd.DataFrame()
    
    buffer_daily = io.BytesIO()
    has_data_daily = False
    
    if not filtered_logs.empty:
        has_data_daily = True
        # 先確定班別
        filtered_logs['班別'] = filtered_logs.apply(lambda r: r['班別'] if pd.notna(r['班別']) and str(r['班別']).strip()!="" else dm.get_shift_info_backup(r['datetime']), axis=1)
        
        # 根據班別和時間判斷日期（考慮晚班跨日，與 LOT 編號邏輯一致）
        from datetime import timedelta
        def adjust_date_for_shift(row):
            """根據班別和時間調整日期，晚班在 00:00-07:59 使用前一天日期"""
            dt = row['datetime']
            shift = row['班別']
            
            # 如果是晚班且在 00:00-07:59，日期減一天
            if shift == "晚班":
                hour = dt.hour
                minute = dt.minute
                # 晚班在 00:00-07:59 時段，使用前一天日期（與 LOT 編號邏輯一致）
                if (hour == 0) or (hour >= 1 and hour < 8) or (hour == 7 and minute < 55):
                    adjusted_date = dt - timedelta(days=1)
                    return adjusted_date.strftime("%d")
            
            # 其他情況（早班、中班，或晚班在 23:55-23:59）使用原始日期
            return dt.strftime("%d")
        
        filtered_logs['日期'] = filtered_logs.apply(adjust_date_for_shift, axis=1)
        
        if '組別' not in filtered_logs.columns: filtered_logs['組別'] = 'A'
        # 只處理 PASS 和 NG 記錄，排除 PARTICLE 記錄（PARTICLE 只用於實重準重報表）
        pass_df = filtered_logs[filtered_logs['判定結果'] == 'PASS'].copy(); ng_df = filtered_logs[filtered_logs['判定結果'] == 'NG'].copy()
        if not pass_df.empty:
            if not st.session_state.products_db.empty: pass_final = pd.merge(pass_df, st.session_state.products_db, on="產品ID", how="left")
            else: pass_final = pass_df.copy(); pass_final[['溫度等級', '品種', '密度', '長', '寬', '高', '準重']] = 0
        else: pass_final = pd.DataFrame()
        if not ng_df.empty:
            if not st.session_state.products_db.empty: ng_final = pd.merge(ng_df, st.session_state.products_db, on="產品ID", how="left")
            else: ng_final = ng_df.copy(); ng_final[['溫度等級', '品種', '密度', '長', '寬', '高', '準重']] = ""
            ng_final['品種'] = 'XD'; ng_final['準重'] = 10; ng_final['密度'] = 0; ng_final[['長', '寬', '高']] = 0; ng_final['溫度等級'] = ng_final['溫度等級'].fillna('')
        else: ng_final = pd.DataFrame()
        full_df = pd.concat([pass_final, ng_final], ignore_index=True)
        
        # 如果 full_df 為空，確保有正確的欄位結構（從 filtered_logs 取得欄位）
        if full_df.empty and not filtered_logs.empty:
            # 從 filtered_logs 創建一個空的 DataFrame，保留所有必要欄位
            required_cols = ['產線', '日期', '班別', '組別', '溫度等級', '品種', '密度', '長', '寬', '高', '準重']
            available_cols = [col for col in required_cols if col in filtered_logs.columns]
            full_df = pd.DataFrame(columns=available_cols)
        
        # 只有在 full_df 不為空且包含 '產線' 欄位時才執行 groupby
        if not full_df.empty and '產線' in full_df.columns:
            for c in ['準重', '長', '寬', '高', '密度']: 
                if c in full_df.columns: full_df[c] = pd.to_numeric(full_df[c], errors='coerce').fillna(0)
            report_df = full_df.groupby(['產線', '日期', '班別', '組別', '溫度等級', '品種', '密度', '長', '寬', '高', '準重']).size().reset_index(name='數量')
            report_df['總計'] = (report_df['數量'] * report_df['準重']).round(0).astype(int)
            report_df = report_df.rename(columns={'產線': 'Line.', '長': '長度', '寬': '寬度', '高': '厚度', '準重': '標準重量'})
            
            # 自定義排序：班別按早、中、晚順序，品種中 XD 排在當班最上方
            # 先創建班別的排序順序（早班=1, 中班=2, 晚班=3）
            shift_order = {'早班': 1, '中班': 2, '晚班': 3}
            report_df['班別排序'] = report_df['班別'].map(shift_order).fillna(99)
            
            # 創建品種排序（XD=0 排在最前，其他=1）
            report_df['品種排序'] = report_df['品種'].apply(lambda x: 0 if str(x).strip() == 'XD' else 1)
            
            # 按 Line.、日期、班別排序、品種排序、其他欄位排序
            export_df = report_df.sort_values(
                by=['Line.', '日期', '班別排序', '組別', '溫度等級', '品種排序', '品種', '密度', '長度', '寬度', '厚度', '標準重量']
            )
            # 選擇最終需要的欄位並移除臨時排序欄位
            export_df = export_df[final_cols]
            export_df.index = range(1, len(export_df) + 1)
        else:
            # 如果 full_df 為空或缺少 '產線' 欄位，設置 has_data_daily 為 False
            has_data_daily = False
            export_df = pd.DataFrame(columns=final_cols)
        
        try:
            with pd.ExcelWriter(buffer_daily, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, index=False, sheet_name='生產統計表'); worksheet = writer.sheets['生產統計表']; header_fmt = writer.book.add_format({'bold': True, 'align': 'center', 'bg_color': '#D9E1F2', 'border': 1})
                for col_num, value in enumerate(export_df.columns.values): worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column(0, 12, 12) 
        except: pass
    
    st.download_button(
        label=f"📥 下載 {sel_year} 年 {sel_month} 月 生產統計 Excel", 
        data=buffer_daily.getvalue(), 
        file_name=f"生產統計_{sel_year}_{sel_month}.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        type="primary", 
        width='stretch',
        disabled=not has_data_daily
    )
    
    if not has_data_daily:
        st.info(f"ℹ️ {sel_year} 年 {sel_month} 月尚無生產數據。")

    st.markdown("---")

    st.markdown('<div class="section-header header-admin">⚖️ 實重準重報表</div>', unsafe_allow_html=True)
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        sel_year_weight = st.selectbox("請選擇年份", years, key="weight_rpt_year")
    with col_w2:
        if not logs.empty: months_weight = sorted(logs[logs['Year'] == sel_year_weight]['Month'].unique(), reverse=True)
        else: months_weight = range(1, 13)
        sel_month_weight = st.selectbox("請選擇月份", months_weight, key="weight_rpt_month")

    buffer_weight = io.BytesIO()
    has_data_weight = False
    
    if not logs.empty:
        w_logs = logs[(logs['Year'] == sel_year_weight) & (logs['Month'] == sel_month_weight)].copy()
        
        if not w_logs.empty and not st.session_state.products_db.empty:
            w_merged = pd.merge(w_logs, st.session_state.products_db, on="產品ID", how="left")
            w_merged['datetime_obj'] = pd.to_datetime(w_merged['時間'], errors='coerce')
            w_merged['日期'] = w_merged['datetime_obj'].dt.strftime("%d")
            w_merged['班別'] = w_merged.apply(lambda r: r['班別'] if pd.notna(r['班別']) and str(r['班別']).strip()!="" else dm.get_shift_info_backup(r['datetime_obj']), axis=1)
            if '組別' not in w_merged.columns: w_merged['組別'] = 'A'

            pass_df = w_merged[w_merged['判定結果'] == 'PASS'].copy()
            ng_df = w_merged[w_merged['判定結果'] == 'NG'].copy()
            particle_df = w_merged[w_merged['判定結果'] == 'PARTICLE'].copy()

            pass_df['實測重'] = pd.to_numeric(pass_df['實測重'], errors='coerce').fillna(0)
            wo_map = st.session_state.work_orders_db.set_index("工單號碼")["準重"].to_dict()
            pass_df['準重_calc'] = pass_df['工單號'].map(wo_map).fillna(0).astype(float)

            pass_agg = pass_df.groupby(['日期', '班別', '組別']).agg(
                實重=('實測重', 'sum'),
                準重=('準重_calc', 'sum')
            ).reset_index()

            ng_agg = ng_df.groupby(['日期', '班別', '組別']).size().reset_index(name='NG_Count')

            particle_df['實測重'] = pd.to_numeric(particle_df['實測重'], errors='coerce').fillna(0)
            particle_agg = particle_df.groupby(['日期', '班別', '組別'])['實測重'].sum().reset_index(name='粒子重')

            final_agg = pd.merge(pass_agg, ng_agg, on=['日期', '班別', '組別'], how='outer')
            final_agg = pd.merge(final_agg, particle_agg, on=['日期', '班別', '組別'], how='outer').fillna(0)
            
            final_agg['不良品'] = final_agg['NG_Count'] * 10 
            final_agg['粒子'] = final_agg['粒子重']
            final_agg['實重準重(%)'] = (final_agg['實重'] / final_agg['準重'] * 100).fillna(0).round(1).astype(str) + '%'
            
            total_prod = final_agg['實重'] + final_agg['不良品']
            total_input = total_prod + final_agg['粒子']
            final_agg['集棉率'] = (total_prod / total_input * 100).fillna(0).round(1).astype(str) + '%'
            
            final_agg['BULK/SB/BUXD'] = ""
            final_agg['邊料'] = ""
            final_agg['實重'] = final_agg['實重'].round(1)
            final_agg['準重'] = final_agg['準重'].round(1)

            final_agg = final_agg.sort_values(by=['日期', '班別'])

            # 檢查是否有實際的生產數據（實重、準重、不良品、粒子至少有一個不為0）
            if not final_agg.empty:
                # 檢查是否有任何非零的生產數據
                has_production = (
                    (final_agg['實重'] > 0).any() or 
                    (final_agg['準重'] > 0).any() or 
                    (final_agg['不良品'] > 0).any() or 
                    (final_agg['粒子'] > 0).any()
                )
                if has_production:
                    # 如果有實際生產數據，設置 has_data_weight 為 True
                    has_data_weight = True
                    final_cols_w = ['日期', '班別', '組別', '實重', '準重', 'BULK/SB/BUXD', '邊料', '不良品', '粒子', '實重準重(%)', '集棉率']
                    export_w = final_agg[final_cols_w]
                else:
                    # 如果所有數據都是0，表示沒有實際生產，設置 has_data_weight 為 False
                    has_data_weight = False
                    export_w = pd.DataFrame(columns=['日期', '班別', '組別', '實重', '準重', 'BULK/SB/BUXD', '邊料', '不良品', '粒子', '實重準重(%)', '集棉率'])
            else:
                has_data_weight = False
                export_w = pd.DataFrame(columns=['日期', '班別', '組別', '實重', '準重', 'BULK/SB/BUXD', '邊料', '不良品', '粒子', '實重準重(%)', '集棉率'])
            
            # 只有在有數據時才生成 Excel 文件
            if has_data_weight and not export_w.empty:
                try:
                    with pd.ExcelWriter(buffer_weight, engine='xlsxwriter') as writer:
                        export_w.to_excel(writer, index=False, sheet_name='實重準重表')
                        worksheet = writer.sheets['實重準重表']
                        
                        header_fmt = writer.book.add_format({'bold': True, 'align': 'center', 'border': 1, 'bg_color': '#FFF2CC'})
                        red_header_fmt = writer.book.add_format({'bold': True, 'align': 'center', 'border': 1, 'bg_color': '#FF0000', 'font_color': 'white'})
                        
                        for col_num, value in enumerate(export_w.columns.values):
                            if value == '不良品':
                                worksheet.write(0, col_num, value, red_header_fmt)
                            else:
                                worksheet.write(0, col_num, value, header_fmt)
                            
                            if value in ['實重', '準重', '實重準重(%)', '集棉率']:
                                worksheet.set_column(col_num, col_num, 15)
                            else:
                                worksheet.set_column(col_num, col_num, 8)
                except: pass

    st.download_button(
        label=f"📥 下載 {sel_year_weight} 年 {sel_month_weight} 月 實重準重 Excel", 
        data=buffer_weight.getvalue(), 
        file_name=f"實重準重_{sel_year_weight}_{sel_month_weight}.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        type="primary", 
        width='stretch',
        disabled=not has_data_weight
    )
    
    if not has_data_weight:
        st.info(f"ℹ️ {sel_year_weight} 年 {sel_month_weight} 月尚無生產數據。")

