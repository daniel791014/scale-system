"""
對話框模組
包含所有彈出視窗 (Dialogs) 的函數
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import config
import data_manager as dm
from data_loader import save_data


@st.dialog("確認撤銷 (Confirm Undo)")
def show_undo_confirm(line_name, shift_curr, group_curr):
    """顯示撤銷確認對話框"""
    dialog_key = f"undo_dialog_{line_name}"
    dialog_closed_key = f"undo_dialog_closed_{line_name}"
    
    # 檢查是否應該清除 dialog（用戶之前關閉了它）
    if st.session_state.get(dialog_closed_key, False):
        st.session_state[dialog_key] = False
        st.session_state[dialog_closed_key] = False
        return
    
    st.write(f"您確定要刪除 {line_name} 的上一筆紀錄嗎？")
    st.warning("此動作無法復原！")
    
    # 添加取消和確定按鈕
    col_cancel, col_confirm = st.columns([1, 2])
    
    with col_cancel:
        if st.button("取消\n(Cancel)", type="secondary", width='stretch', key=f"cancel_undo_{line_name}"):
            st.session_state[dialog_closed_key] = True
            st.session_state[dialog_key] = False
            st.rerun()
    
    with col_confirm:
        if st.button("確定\n(Confirm)", type="primary", width='stretch'):
            try:
                logs = st.session_state.production_logs
                
                # 檢查 logs 是否為空
                if logs.empty:
                    st.error("❌ 沒有記錄可以刪除")
                    return
                
                # 過濾出符合條件的記錄（同一個 session：日期、產線、班別、組別）
                today_str = datetime.now().strftime("%Y-%m-%d")
                mask_strict_shift = (logs["班別"] == shift_curr)
                mask_strict_group = (logs["組別"] == group_curr)
                temp_dts = pd.to_datetime(logs["時間"], errors='coerce') 
                mask_date = temp_dts.dt.date.astype(str) == today_str
                mask_line = logs["產線"] == line_name
                session_logs = logs[mask_date & mask_line & mask_strict_shift & mask_strict_group]
                
                # 檢查是否有符合條件的記錄
                if session_logs.empty or len(session_logs) == 0:
                    st.error(f"❌ {line_name} 目前沒有可刪除的記錄")
                    return
                
                # 取得最後一筆記錄的索引
                last_idx = session_logs.index[-1]
                last_log = logs.loc[last_idx]
                
                # 如果是 PASS 記錄，需要更新工單的已完成數量
                if last_log["判定結果"] == "PASS":
                    wo_id = last_log["工單號"]
                    if not st.session_state.work_orders_db.empty:
                        wo_indices = st.session_state.work_orders_db.index[
                            st.session_state.work_orders_db["工單號碼"] == wo_id
                        ].tolist()
                        if wo_indices:
                            wo_idx = wo_indices[0]
                            current_qty = st.session_state.work_orders_db.at[wo_idx, "已完成數量"]
                            if current_qty > 0:
                                st.session_state.work_orders_db.at[wo_idx, "已完成數量"] = current_qty - 1
                                st.session_state.work_orders_db.at[wo_idx, "狀態"] = "生產中" 
                
                # 刪除最後一筆記錄（無論是 PASS 還是 NG）
                st.session_state.production_logs = logs.drop(last_idx)
                save_data()
                st.session_state.toast_msg = ("↩️ 已成功撤銷上一筆紀錄", None)
                # 設定標記，讓主程式知道需要重新載入
                st.session_state[f"undo_completed_{line_name}"] = True
                # 關閉對話框
                st.session_state[dialog_key] = False
                st.session_state[dialog_closed_key] = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ 刪除失敗：{str(e)}")
                import traceback
                st.exception(e)
    
    # 隱藏對話框右上角的關閉按鈕（X）
    st.markdown("""
    <style>
    /* 隱藏 dialog 右上角的關閉按鈕 */
    div[data-testid="stDialog"] button[aria-label*="Close"],
    div[data-testid="stDialog"] button[aria-label*="關閉"],
    div[data-testid="stDialog"] button[title*="Close"],
    div[data-testid="stDialog"] button[title*="關閉"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 隱藏 header 中的關閉按鈕 */
    div[data-testid="stDialog"] header button:last-child,
    div[data-testid="stDialog"] header button[aria-label*="close" i] {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    <script>
    (function() {
        function hideCloseButton() {
            try {
                var dialog = document.querySelector('[data-testid="stDialog"]');
                if (!dialog) return;
                
                // 查找所有可能的關閉按鈕
                var closeButtons = dialog.querySelectorAll('button');
                for (var i = 0; i < closeButtons.length; i++) {
                    var btn = closeButtons[i];
                    var ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                    var title = (btn.getAttribute('title') || '').toLowerCase();
                    var btnText = (btn.innerText || btn.textContent || '').trim();
                    
                    // 檢查是否為關閉按鈕（在 header 中且標記為關閉）
                    var inHeader = false;
                    var parent = btn.parentElement;
                    for (var j = 0; j < 5; j++) {
                        if (!parent) break;
                        if (parent.tagName === 'HEADER' || 
                            (parent.className && parent.className.toLowerCase().includes('header'))) {
                            inHeader = true;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                    
                    var isCloseButton = inHeader && (
                        ariaLabel.includes('close') || ariaLabel.includes('關閉') ||
                        title.includes('close') || title.includes('關閉') ||
                        btnText === '×' || btnText === '✕' || btnText === 'X' || btnText === ''
                    );
                    
                    // 只隱藏關閉按鈕，保留我們的取消和確認按鈕
                    var isOurButton = btnText.includes('取消') || btnText.includes('Cancel') ||
                                     btnText.includes('確定') || btnText.includes('Confirm') ||
                                     btnText.includes('刪除');
                    
                    if (isCloseButton && !isOurButton) {
                        btn.style.setProperty('display', 'none', 'important');
                        btn.style.setProperty('visibility', 'hidden', 'important');
                        btn.style.setProperty('opacity', '0', 'important');
                        btn.style.setProperty('pointer-events', 'none', 'important');
                    }
                }
            } catch(e) {
                console.error('Error hiding close button:', e);
            }
        }
        
        // 立即執行多次
        hideCloseButton();
        setTimeout(hideCloseButton, 50);
        setTimeout(hideCloseButton, 100);
        setTimeout(hideCloseButton, 200);
        setTimeout(hideCloseButton, 500);
        setTimeout(hideCloseButton, 1000);
        
        // 監聽 DOM 變化
        var observer = new MutationObserver(function() {
            hideCloseButton();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        
        setTimeout(function() {
            observer.disconnect();
        }, 10000);
    })();
    </script>
    """, unsafe_allow_html=True)


@st.dialog("🏁 結算下班 (End Shift)")
def show_end_shift_dialog(line_name, current_s, current_g, all_line_statuses):
    """顯示結算下班對話框"""
    dialog_key = f"dialog_open_{line_name}"
    dialog_closed_key = f"dialog_closed_{line_name}"
    
    # 檢查是否應該清除 dialog（用戶之前關閉了它）
    if st.session_state.get(dialog_closed_key, False):
        st.session_state[dialog_key] = False
        st.session_state[dialog_closed_key] = False
        # 清除所有相關狀態
        key_confirmed = f"p_conf_{line_name}"
        key_weight = f"p_val_{line_name}"
        key_zero_check = f"p_zero_{line_name}"
        if key_confirmed in st.session_state: 
            del st.session_state[key_confirmed]
        if key_weight in st.session_state: 
            del st.session_state[key_weight]
        if key_zero_check in st.session_state: 
            del st.session_state[key_zero_check]
        return
    
    st.markdown(f"### 📋 {line_name} 生產數據確認")
    today_str = datetime.now().strftime("%Y-%m-%d")
    logs = st.session_state.production_logs
    
    key_confirmed = f"p_conf_{line_name}"
    key_weight = f"p_val_{line_name}"
    key_zero_check = f"p_zero_{line_name}"

    if key_confirmed not in st.session_state: 
        st.session_state[key_confirmed] = False
    if key_weight not in st.session_state: 
        st.session_state[key_weight] = 0
    if key_zero_check not in st.session_state: 
        st.session_state[key_zero_check] = False

    total_production_weight = 0
    yield_rate_val = 0.0
    collection_rate_val = 0.0
    product_weight = 0.0

    if not logs.empty:
        temp_logs = logs.copy()
        temp_logs['datetime'] = temp_logs['時間'].apply(dm.parse_log_time)
        mask = ((temp_logs['產線'] == line_name) & 
                (temp_logs['datetime'].dt.strftime("%Y-%m-%d") == today_str) & 
                (temp_logs['班別'] == current_s) & 
                (temp_logs['組別'] == current_g))
        shift_data = temp_logs[mask]
        pass_data = shift_data[shift_data['判定結果'] == 'PASS']
        ng_data = shift_data[shift_data['判定結果'] == 'NG']
        count_ng = len(ng_data)
        total_std_pass = 0.0
        pass_actual_sum = 0.0
        if not pass_data.empty:
            wo_std_map = st.session_state.work_orders_db.set_index("工單號碼")["準重"].to_dict()
            mapped_stds = pass_data["工單號"].map(wo_std_map).fillna(0).astype(float)
            total_std_pass = mapped_stds.sum()
            pass_actual_sum = pd.to_numeric(pass_data['實測重'], errors='coerce').fillna(0).sum()
        total_ng_weight = count_ng * 10.0
        total_production_val = total_std_pass + total_ng_weight
        total_production_weight = int(round(total_production_val, 0))
        if total_production_val > 0:
            yield_rate_val = (total_std_pass / total_production_val) * 100
        product_weight = pass_actual_sum + total_ng_weight

    if st.session_state[key_zero_check] and not st.session_state[key_confirmed]:
        st.warning("⚠️ 檢測到數值為 0。若此製程無粒子產出，請再次點擊「確認」；若為疏忽請輸入數值。")

    particle_weight_input = st.number_input(
        "👇 請輸入本班粒子重量 (kg)", 
        min_value=0, step=1, format="%d", 
        key=f"p_input_{line_name}",
        disabled=st.session_state[key_confirmed], 
        value=st.session_state[key_weight]
    )

    if not st.session_state[key_confirmed]:
        btn_label = "✅ 確認粒子重量"
        btn_type = "secondary"
        if st.session_state[key_zero_check]:
            btn_label = "⚠️ 確認無粒子 (0kg)"
            btn_type = "primary" 

        if st.button(btn_label, type=btn_type, width='stretch'):
            current_val = int(particle_weight_input)
            
            if current_val > 0:
                st.session_state[key_confirmed] = True
                st.session_state[key_weight] = current_val
                st.session_state[key_zero_check] = False 
                st.rerun()
            else:
                if st.session_state[key_zero_check]:
                    st.session_state[key_confirmed] = True
                    st.session_state[key_weight] = 0
                    st.session_state[key_zero_check] = False
                    st.rerun()
                else:
                    st.session_state[key_zero_check] = True
                    st.rerun()
    else:
        c_msg, c_edit = st.columns([5, 1], vertical_alignment="center")
        with c_msg:
            if st.session_state[key_weight] == 0:
                st.info("ℹ️ 粒子重量 0 kg (無產出) 已確認")
            else:
                st.success(f"粒子重量 {st.session_state[key_weight]} kg 已確認")
        with c_edit:
            if st.button("✏️", help="修改重量", key=f"edit_{line_name}"):
                st.session_state[key_confirmed] = False
                st.session_state[key_zero_check] = False 
                st.rerun()

    current_p_weight = st.session_state[key_weight] if st.session_state[key_confirmed] else particle_weight_input
    total_input = product_weight + current_p_weight
    if total_input > 0:
        collection_rate_val = (product_weight / total_input) * 100
        
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("總生產量 (Total)", f"{total_production_weight} kg")
    col2.metric("良率 (Yield)", f"{yield_rate_val:.1f}%")
    col3.metric("集棉率 (Collection)", f"{collection_rate_val:.1f}%")
    st.write("")
    
    # 添加取消按鈕 - 明確允許用戶取消操作
    cancel_col, confirm_col = st.columns([1, 2])
    with cancel_col:
        if st.button("❌ 取消 (Cancel)", type="secondary", width='stretch', key=f"cancel_end_shift_{line_name}"):
            # 清除所有狀態並關閉 dialog
            st.session_state[dialog_closed_key] = True
            st.session_state[dialog_key] = False
            # 清除所有相關狀態
            if key_confirmed in st.session_state: 
                del st.session_state[key_confirmed]
            if key_weight in st.session_state: 
                del st.session_state[key_weight]
            if key_zero_check in st.session_state: 
                del st.session_state[key_zero_check]
            st.rerun()
    
    logout_disabled = not st.session_state[key_confirmed]
    
    # 添加按鈕樣式 - 使用 JavaScript 直接設定
    st.markdown("""
    <script>
    (function() {
        function styleLogoutButton() {
            var buttons = document.getElementsByTagName('button');
            for (var i = 0; i < buttons.length; i++) {
                var btn = buttons[i];
                var txt = btn.innerText || btn.textContent || '';
                if (txt.includes("確認結算並下班") || txt.includes("Confirm & Logout")) {
                    btn.style.setProperty('height', '35px', 'important');
                    btn.style.setProperty('min-height', '35px', 'important');
                    btn.style.setProperty('max-height', '35px', 'important');
                    btn.style.setProperty('padding', '4px 12px', 'important');
                    btn.style.setProperty('font-size', '14px', 'important');
                    btn.style.setProperty('line-height', '1.2', 'important');
                }
            }
        }
        styleLogoutButton();
        setTimeout(styleLogoutButton, 100);
        setTimeout(styleLogoutButton, 500);
    })();
    </script>
    """, unsafe_allow_html=True)
    
    with confirm_col:
        if st.button("🏁 確認結算並下班 (Confirm & Logout)", type="primary", width='stretch', disabled=logout_disabled):
            final_p = st.session_state[key_weight]
            new_log = pd.DataFrame([[
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                line_name, "SHIFT_END", "PARTICLE", final_p, "PARTICLE", "", current_g, current_s, ""
            ]], columns=config.LOG_COLUMNS)
            st.session_state.production_logs = pd.concat([st.session_state.production_logs, new_log], ignore_index=True)
            save_data()
            
            all_line_statuses[line_name] = {"active": False, "shift": current_s, "group": current_g} 
            dm.save_line_status(all_line_statuses)
            
            if key_confirmed in st.session_state: 
                del st.session_state[key_confirmed]
            if key_weight in st.session_state: 
                del st.session_state[key_weight]
            if key_zero_check in st.session_state: 
                del st.session_state[key_zero_check]
            st.session_state[f"dialog_open_{line_name}"] = False
            
            st.toast(f"✅ {line_name} 結算完成，已下班！", icon="🏁")
            time.sleep(3)
            st.rerun()
    
    # 使用 JavaScript 強制隱藏關閉按鈕（叉叉）並減少空白
    st.markdown(f"""
    <style>
    /* 減少 dialog 底部空白 */
    div[data-testid="stDialog"] > div:last-child,
    div[data-testid="stDialog"] form:last-child {{
        padding-bottom: 10px !important;
        margin-bottom: 0 !important;
    }}
    
    /* 確保按鈕列沒有多餘的空白 */
    div[data-testid="stDialog"] [data-testid*="column"]:last-child {{
        margin-bottom: 0 !important;
        padding-bottom: 5px !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # 使用 JavaScript 強制隱藏關閉按鈕（叉叉），並減少空白
    st.markdown(f"""
    <script>
    (function() {{
        // 強制隱藏 dialog 右上角的關閉按鈕（叉叉）並減少空白
        function hideCloseButton() {{
            try {{
                var dialog = document.querySelector('[data-testid="stDialog"]');
                if (!dialog) return;
                
                // 查找所有按鈕
                var allButtons = dialog.querySelectorAll('button');
                for (var i = 0; i < allButtons.length; i++) {{
                    var btn = allButtons[i];
                    var btnText = (btn.innerText || btn.textContent || '').trim();
                    var ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                    var title = (btn.getAttribute('title') || '').toLowerCase();
                    
                    // 檢查是否在 header 區域
                    var inHeader = false;
                    var parent = btn;
                    for (var j = 0; j < 5; j++) {{
                        if (!parent) break;
                        if (parent.tagName === 'HEADER' || 
                            (parent.className && parent.className.toLowerCase().includes('header'))) {{
                            inHeader = true;
                            break;
                        }}
                        parent = parent.parentElement;
                    }}
                    
                    // 檢查是否為關閉按鈕（在 header 中且標記為關閉）
                    var isCloseButton = inHeader && (
                        ariaLabel.includes('close') || ariaLabel.includes('關閉') ||
                        title.includes('close') || title.includes('關閉') ||
                        btnText === '×' || btnText === '✕' || btnText === 'X' || btnText === ''
                    );
                    
                    // 檢查是否為我們的按鈕
                    var isOurButton = btnText.includes('取消') || btnText.includes('Cancel') ||
                                     btnText.includes('確認') || btnText.includes('Confirm') ||
                                     btnText.includes('結算') || btnText.includes('Logout');
                    
                    // 只隱藏關閉按鈕，保留我們的按鈕
                    if (isCloseButton && !isOurButton) {{
                        btn.style.setProperty('display', 'none', 'important');
                        btn.style.setProperty('visibility', 'hidden', 'important');
                        btn.style.setProperty('opacity', '0', 'important');
                        btn.style.setProperty('pointer-events', 'none', 'important');
                        btn.style.setProperty('position', 'absolute', 'important');
                        btn.style.setProperty('left', '-9999px', 'important');
                        btn.style.setProperty('width', '0', 'important');
                        btn.style.setProperty('height', '0', 'important');
                        btn.style.setProperty('padding', '0', 'important');
                        btn.style.setProperty('margin', '0', 'important');
                    }}
                }}
                
                // 減少 dialog 底部空白
                var forms = dialog.querySelectorAll('form');
                if (forms.length > 0) {{
                    forms[forms.length - 1].style.setProperty('padding-bottom', '10px', 'important');
                    forms[forms.length - 1].style.setProperty('margin-bottom', '0', 'important');
                }}
                
                var lastDiv = dialog.querySelector('> div:last-child');
                if (lastDiv) {{
                    lastDiv.style.setProperty('padding-bottom', '10px', 'important');
                    lastDiv.style.setProperty('margin-bottom', '0', 'important');
                }}
            }} catch(e) {{
                console.error('Error hiding close button:', e);
            }}
        }}
        
        // 立即執行多次
        hideCloseButton();
        setTimeout(hideCloseButton, 50);
        setTimeout(hideCloseButton, 100);
        setTimeout(hideCloseButton, 200);
        setTimeout(hideCloseButton, 500);
        setTimeout(hideCloseButton, 1000);
        
        // 持續監聽 DOM 變化
        var observer = new MutationObserver(function() {{
            hideCloseButton();
        }});
        observer.observe(document.body, {{ childList: true, subtree: true }});
        
        setTimeout(function() {{
            observer.disconnect();
        }}, 10000);
        
        var dialogClosed = false;
        
        function hideDetectorButton() {{
            try {{
                var btn = document.querySelector('button[data-testid*="' + detectorKey + '"]');
                if (btn) {{
                    btn.style.display = 'none';
                    btn.style.visibility = 'hidden';
                    btn.style.height = '0';
                    btn.style.width = '0';
                    btn.style.padding = '0';
                    btn.style.margin = '0';
                    btn.style.opacity = '0';
                    btn.style.position = 'absolute';
                    btn.style.left = '-9999px';
                    
                    var parent = btn.parentElement;
                    while (parent && parent !== document.body) {{
                        if (parent.tagName === 'DIV') {{
                            parent.style.display = 'none';
                            parent.style.height = '0';
                            parent.style.minHeight = '0';
                            parent.style.maxHeight = '0';
                            parent.style.margin = '0';
                            parent.style.padding = '0';
                            parent.style.overflow = 'hidden';
                        }}
                        parent = parent.parentElement;
                    }}
                }}
            }} catch(e) {{
                // 忽略錯誤
            }}
        }}
        
        // 監聽並隱藏 dialog 關閉按鈕（叉叉）
        function setupCloseListener() {{
            var dialog = document.querySelector('[data-testid="stDialog"]');
            if (!dialog) {{
                // 如果找不到 dialog，稍後再試
                setTimeout(setupCloseListener, 100);
                return;
            }}
            
            console.log('Setting up dialog close listeners...');
            
            // 方法1: 監聽關閉按鈕點擊（嘗試多種選擇器）
            var closeBtn = dialog.querySelector('button[aria-label*="Close"]') || 
                          dialog.querySelector('button[aria-label*="關閉"]') ||
                          dialog.querySelector('button[title*="Close"]') ||
                          dialog.querySelector('button[title*="關閉"]');
            
            if (!closeBtn) {{
                // 嘗試在 header 中查找
                var header = dialog.querySelector('header') || 
                            dialog.querySelector('[role="dialog"] > div:first-child') ||
                            dialog.querySelector('[class*="header"]');
                if (header) {{
                    var headerButtons = header.querySelectorAll('button');
                    // 通常關閉按鈕是最後一個
                    if (headerButtons.length > 0) {{
                        closeBtn = headerButtons[headerButtons.length - 1];
                        // 也可以嘗試第一個
                        if (!closeBtn || closeBtn.style.display === 'none') {{
                            closeBtn = headerButtons[0];
                        }}
                    }}
                }}
            }}
            
            if (closeBtn) {{
                console.log('Found close button, hiding it...');
                // 直接隱藏關閉按鈕，因為我們使用取消按鈕
                closeBtn.style.setProperty('display', 'none', 'important');
                closeBtn.style.setProperty('visibility', 'hidden', 'important');
                closeBtn.style.setProperty('opacity', '0', 'important');
                closeBtn.style.setProperty('pointer-events', 'none', 'important');
            }} else {{
                console.log('Close button not found, will try again...');
                setTimeout(setupCloseListener, 200);
            }}
                
            
            // 方法2: 監聽 dialog 移除事件
            var lastDialogState = dialog.style.display;
            var observer = new MutationObserver(function(mutations) {{
                mutations.forEach(function(mutation) {{
                    if (mutation.removedNodes.length > 0) {{
                        mutation.removedNodes.forEach(function(node) {{
                            if (node === dialog || (node.contains && node.contains(dialog))) {{
                                console.log('Dialog removed from DOM');
                            }}
                        }});
                    }}
                    // 也檢查 dialog 的 display 或 visibility 變化
                    if (mutation.type === 'attributes' && mutation.target === dialog) {{
                        var style = window.getComputedStyle(dialog);
                        var currentDisplay = style.display;
                        var currentVisibility = style.visibility;
                        
                        if (currentDisplay === 'none' || currentVisibility === 'hidden') {{
                            if (lastDialogState !== 'none') {{
                                console.log('Dialog hidden');
                                lastDialogState = 'none';
                            }}
                        }}
                    }}
                }});
                
                // 定期檢查 dialog 是否還在 DOM 中
                var currentDialog = document.querySelector('[data-testid="stDialog"]');
                if (!currentDialog || currentDialog !== dialog) {{
                    console.log('Dialog no longer in DOM');
                }}
            }});
            observer.observe(document.body, {{ 
                childList: true, 
                subtree: true, 
                attributes: true, 
                attributeFilter: ['style', 'class']
            }});
            
            // 方法3: 監聽 ESC 鍵（僅隱藏，實際關閉由取消按鈕處理）
            function handleEsc(event) {{
                if (event.key === 'Escape' || event.keyCode === 27) {{
                    console.log('ESC key pressed - dialog will be handled by cancel button');
                }}
            }}
            document.addEventListener('keydown', handleEsc, true);
            
            // 方法4: 定期檢查 dialog 是否還存在並隱藏關閉按鈕
            var checkInterval = setInterval(function() {{
                var currentDialog = document.querySelector('[data-testid="stDialog"]');
                if (!currentDialog || currentDialog !== dialog) {{
                    console.log('Dialog no longer exists');
                    clearInterval(checkInterval);
                }} else {{
                    // 持續隱藏關閉按鈕
                    if (closeBtn) {{
                        closeBtn.style.setProperty('display', 'none', 'important');
                        closeBtn.style.setProperty('visibility', 'hidden', 'important');
                    }}
                }}
            }}, 500);
            
            setTimeout(function() {{
                observer.disconnect();
                document.removeEventListener('keydown', handleEsc);
                clearInterval(checkInterval);
            }}, 30000);
        }}
        
        // 立即設置監聽器
        setupCloseListener();
        // 也延遲設置，以防 DOM 還沒準備好
        setTimeout(setupCloseListener, 200);
        setTimeout(setupCloseListener, 500);
    }})();
    </script>
    """, unsafe_allow_html=True)


@st.dialog("🗑️ 確認刪除工單 (Confirm Delete Work Order)")
def show_delete_work_orders_confirm(target_line, work_order_ids, work_order_info_list):
    """顯示刪除工單確認對話框"""
    dialog_key = f"delete_wo_dialog_{target_line}"
    dialog_closed_key = f"delete_wo_dialog_closed_{target_line}"
    
    # 檢查是否應該清除 dialog（用戶之前關閉了它）
    if st.session_state.get(dialog_closed_key, False):
        st.session_state[dialog_key] = False
        st.session_state[dialog_closed_key] = False
        return
    
    st.markdown(f"""
    <div style="font-size: 20px; font-weight: bold; margin-bottom: 20px;">
        ⚠️ 您確定要刪除以下工單嗎？
    </div>
    """, unsafe_allow_html=True)
    
    # 顯示將要刪除的工單列表，使用與結束工單相同的藍色背景框樣式
    if work_order_info_list:
        # 將所有工單資訊合併成一個字串，用換行分隔
        work_order_display = "<br>".join([f"• {info}" for info in work_order_info_list])
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 8px; border-left: 4px solid #1f77b4; margin: 10px 0;">
            <p style="font-size: 18px; font-weight: bold; color: #1f77b4; margin: 0;">
                {work_order_display}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    col_cancel, col_confirm = st.columns([1, 2])
    
    with col_cancel:
        if st.button("取消\n(Cancel)", type="secondary", width='stretch'):
            st.session_state[dialog_closed_key] = True
            st.session_state[dialog_key] = False
            st.rerun()
    
    with col_confirm:
        if st.button("確定\n(Confirm)", type="primary", width='stretch'):
            try:
                # 執行刪除邏輯
                if 'work_orders_db' not in st.session_state:
                    from data_loader import load_data
                    load_data()
                
                if not work_order_ids:
                    st.error("❌ 沒有要刪除的工單")
                    return
                
                latest_db = st.session_state.work_orders_db.copy()
                
                # 檢查要刪除的工單是否存在
                existing_ids = latest_db["工單號碼"].unique().tolist()
                valid_ids = [wo_id for wo_id in work_order_ids if wo_id in existing_ids]
                
                if not valid_ids:
                    st.error("❌ 要刪除的工單不存在於資料庫中")
                    return
                
                if len(valid_ids) != len(work_order_ids):
                    st.warning(f"⚠️ 警告：{len(work_order_ids) - len(valid_ids)} 個工單不存在，將只刪除 {len(valid_ids)} 個工單")
                
                latest_db = latest_db[~latest_db["工單號碼"].isin(valid_ids)]
                latest_db = dm.normalize_sequences(latest_db)
                st.session_state.work_orders_db = latest_db
                save_data()
                
                st.session_state.toast_msg = (f"✅ 已成功刪除 {len(valid_ids)} 筆工單", None)
                
                # 設置清除 checkbox 的標記（在下次渲染時清除所有該產線的 checkbox）
                # 注意：我們不能直接修改已創建的 widget 狀態，所以使用標記在下次渲染時清除
                clear_checkboxes_key = f"clear_checkboxes_{target_line}"
                st.session_state[clear_checkboxes_key] = "all"
                
                # 關閉對話框
                st.session_state[dialog_key] = False
                st.session_state[dialog_closed_key] = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ 刪除失敗：{str(e)}")
                import traceback
                st.exception(e)
    
    # 隱藏對話框右上角的關閉按鈕（X）
    st.markdown("""
    <style>
    /* 隱藏 dialog 右上角的關閉按鈕 */
    div[data-testid="stDialog"] button[aria-label*="Close"],
    div[data-testid="stDialog"] button[aria-label*="關閉"],
    div[data-testid="stDialog"] button[title*="Close"],
    div[data-testid="stDialog"] button[title*="關閉"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 隱藏 header 中的關閉按鈕 */
    div[data-testid="stDialog"] header button:last-child,
    div[data-testid="stDialog"] header button[aria-label*="close" i] {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    <script>
    (function() {
        function hideCloseButton() {
            try {
                var dialog = document.querySelector('[data-testid="stDialog"]');
                if (!dialog) return;
                
                // 查找所有可能的關閉按鈕
                var closeButtons = dialog.querySelectorAll('button');
                for (var i = 0; i < closeButtons.length; i++) {
                    var btn = closeButtons[i];
                    var ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                    var title = (btn.getAttribute('title') || '').toLowerCase();
                    var btnText = (btn.innerText || btn.textContent || '').trim();
                    
                    // 檢查是否為關閉按鈕（在 header 中且標記為關閉）
                    var inHeader = false;
                    var parent = btn.parentElement;
                    for (var j = 0; j < 5; j++) {
                        if (!parent) break;
                        if (parent.tagName === 'HEADER' || 
                            (parent.className && parent.className.toLowerCase().includes('header'))) {
                            inHeader = true;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                    
                    var isCloseButton = inHeader && (
                        ariaLabel.includes('close') || ariaLabel.includes('關閉') ||
                        title.includes('close') || title.includes('關閉') ||
                        btnText === '×' || btnText === '✕' || btnText === 'X' || btnText === ''
                    );
                    
                    // 只隱藏關閉按鈕，保留我們的取消和確認按鈕
                    var isOurButton = btnText.includes('取消') || btnText.includes('Cancel') ||
                                     btnText.includes('確定') || btnText.includes('Confirm') ||
                                     btnText.includes('刪除');
                    
                    if (isCloseButton && !isOurButton) {
                        btn.style.setProperty('display', 'none', 'important');
                        btn.style.setProperty('visibility', 'hidden', 'important');
                        btn.style.setProperty('opacity', '0', 'important');
                        btn.style.setProperty('pointer-events', 'none', 'important');
                    }
                }
            } catch(e) {
                console.error('Error hiding close button:', e);
            }
        }
        
        // 立即執行多次
        hideCloseButton();
        setTimeout(hideCloseButton, 50);
        setTimeout(hideCloseButton, 100);
        setTimeout(hideCloseButton, 200);
        setTimeout(hideCloseButton, 500);
        setTimeout(hideCloseButton, 1000);
        
        // 監聽 DOM 變化
        var observer = new MutationObserver(function() {
            hideCloseButton();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        
        setTimeout(function() {
            observer.disconnect();
        }, 10000);
    })();
    </script>
    """, unsafe_allow_html=True)


@st.dialog("🏁 確認結束工單 (Confirm Finish Work Order)")
def show_finish_work_order_confirm(line_name, work_order_id, work_order_info):
    """顯示結束工單確認對話框"""
    dialog_key = f"finish_wo_dialog_{line_name}"
    dialog_closed_key = f"finish_wo_dialog_closed_{line_name}"
    
    # 檢查是否應該清除 dialog（用戶之前關閉了它）
    if st.session_state.get(dialog_closed_key, False):
        st.session_state[dialog_key] = False
        st.session_state[dialog_closed_key] = False
        return
    
    st.markdown(f"""
    <div style="font-size: 20px; font-weight: bold; margin-bottom: 20px;">
        ⚠️ 您確定要結束此工單嗎？
    </div>
    """, unsafe_allow_html=True)
    
    # 只顯示工單顯示內容，使用更醒目的樣式
    if work_order_info:
        # 使用更大的字體和更明顯的樣式顯示工單資訊
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 8px; border-left: 4px solid #1f77b4; margin: 10px 0;">
            <p style="font-size: 18px; font-weight: bold; color: #1f77b4; margin: 0;">
                {work_order_info}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.warning("⚠️ 此動作會將工單狀態設為「已完成」，無法繼續生產此工單！")
    st.write("")
    
    col_cancel, col_confirm = st.columns([1, 2])
    
    with col_cancel:
        if st.button("❌ 取消 (Cancel)", type="secondary", width='stretch'):
            st.session_state[dialog_closed_key] = True
            st.session_state[dialog_key] = False
            st.rerun()
    
    with col_confirm:
        if st.button("✅ 確定結束工單", type="primary", width='stretch'):
            try:
                # 執行結束工單邏輯
                from data_loader import update_work_order_status
                if update_work_order_status(work_order_id, "已完成"):
                    st.session_state.toast_msg = (f"✅ {line_name} 工單已結案！", None)
                else:
                    st.session_state.toast_msg = ("❌ 找不到該工單", None)
                
                # 關閉對話框
                st.session_state[dialog_key] = False
                st.session_state[dialog_closed_key] = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ 存檔失敗：{str(e)}")
                import traceback
                st.exception(e)
    
    # 隱藏對話框右上角的關閉按鈕（X）
    st.markdown("""
    <style>
    /* 隱藏 dialog 右上角的關閉按鈕 */
    div[data-testid="stDialog"] button[aria-label*="Close"],
    div[data-testid="stDialog"] button[aria-label*="關閉"],
    div[data-testid="stDialog"] button[title*="Close"],
    div[data-testid="stDialog"] button[title*="關閉"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 隱藏 header 中的關閉按鈕 */
    div[data-testid="stDialog"] header button:last-child,
    div[data-testid="stDialog"] header button[aria-label*="close" i] {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    <script>
    (function() {
        function hideCloseButton() {
            try {
                var dialog = document.querySelector('[data-testid="stDialog"]');
                if (!dialog) return;
                
                // 查找所有可能的關閉按鈕
                var closeButtons = dialog.querySelectorAll('button');
                for (var i = 0; i < closeButtons.length; i++) {
                    var btn = closeButtons[i];
                    var ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                    var title = (btn.getAttribute('title') || '').toLowerCase();
                    var btnText = (btn.innerText || btn.textContent || '').trim();
                    
                    // 檢查是否為關閉按鈕（在 header 中且標記為關閉）
                    var inHeader = false;
                    var parent = btn.parentElement;
                    for (var j = 0; j < 5; j++) {
                        if (!parent) break;
                        if (parent.tagName === 'HEADER' || 
                            (parent.className && parent.className.toLowerCase().includes('header'))) {
                            inHeader = true;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                    
                    var isCloseButton = inHeader && (
                        ariaLabel.includes('close') || ariaLabel.includes('關閉') ||
                        title.includes('close') || title.includes('關閉') ||
                        btnText === '×' || btnText === '✕' || btnText === 'X' || btnText === ''
                    );
                    
                    // 只隱藏關閉按鈕，保留我們的取消和確認按鈕
                    var isOurButton = btnText.includes('取消') || btnText.includes('Cancel') ||
                                     btnText.includes('確定') || btnText.includes('Confirm');
                    
                    if (isCloseButton && !isOurButton) {
                        btn.style.setProperty('display', 'none', 'important');
                        btn.style.setProperty('visibility', 'hidden', 'important');
                        btn.style.setProperty('opacity', '0', 'important');
                        btn.style.setProperty('pointer-events', 'none', 'important');
                    }
                }
            } catch(e) {
                console.error('Error hiding close button:', e);
            }
        }
        
        // 立即執行多次
        hideCloseButton();
        setTimeout(hideCloseButton, 50);
        setTimeout(hideCloseButton, 100);
        setTimeout(hideCloseButton, 200);
        setTimeout(hideCloseButton, 500);
        setTimeout(hideCloseButton, 1000);
        
        // 監聽 DOM 變化
        var observer = new MutationObserver(function() {
            hideCloseButton();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        
        setTimeout(function() {
            observer.disconnect();
        }, 10000);
    })();
    </script>
    """, unsafe_allow_html=True)


@st.dialog("🚀 開班上工 (Start Shift)")
def show_start_shift_dialog(line_name, all_line_statuses):
    """顯示開班上工對話框"""
    st.markdown(f"### 👋 {line_name} 歡迎使用")
    st.write("請選擇您的組別以開始作業：")
    
    # [優化] 根據當前時間自動判斷班別
    # 早班：08:00-16:00（往前推5分鐘：07:55-15:59）
    # 中班：16:00-00:00（往前推5分鐘：15:55-23:59）
    # 晚班：00:00-08:00（往前推5分鐘：23:55-07:59）
    current_time = datetime.now()
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    if (current_hour == 7 and current_minute >= 55) or (8 <= current_hour < 15) or (current_hour == 15 and current_minute < 55):
        auto_shift = "早班"
    elif (current_hour == 15 and current_minute >= 55) or (16 <= current_hour < 23) or (current_hour == 23 and current_minute < 55):
        auto_shift = "中班"
    else:  # (current_hour == 23 and current_minute >= 55) or (0 <= current_hour < 7) or (current_hour == 7 and current_minute < 55)
        auto_shift = "晚班"
    
    # 顯示自動判斷的班別（只讀，不可選擇）
    last_status = all_line_statuses.get(line_name, {})
    last_group = last_status.get("group", "A")
    
    # 顯示班別資訊（使用 info 顯示，不可選擇）
    st.info(f"📅 **班別**：{auto_shift} (系統自動判斷：{current_time.strftime('%H:%M')})")
    st.write("")
    
    # 只顯示組別選擇（作業員只需要選擇這個）
    new_group = st.selectbox(
        "請選擇組別", 
        config.GROUP_OPTIONS, 
        index=config.GROUP_OPTIONS.index(last_group) if last_group in config.GROUP_OPTIONS else 0
    )
    
    st.write("")
    if st.button("✅ 確認開班 (Confirm Start)", type="primary", width='stretch'):
        # 使用自動判斷的班別
        all_line_statuses[line_name] = {"active": True, "shift": auto_shift, "group": new_group}
        dm.save_line_status(all_line_statuses)
        
        # [當機恢復優化] 優先恢復之前保存的工單選擇，如果沒有則選擇第一個未完成的工單
        try:
            # 找到該產線未完成的工單（狀態為"待生產"或"生產中"）
            mask = (st.session_state.work_orders_db["狀態"].isin(["待生產", "生產中"])) & (st.session_state.work_orders_db["產線"] == line_name)
            pending = st.session_state.work_orders_db[mask].sort_values(by="排程順序")
            
            if not pending.empty:
                # [當機恢復] 嘗試恢復之前保存的工單選擇
                saved_wo_label = dm.load_current_work_order(line_name)
                target_pending = None
                wo_label = None
                
                if saved_wo_label:
                    # 如果有保存的工單，嘗試在待完成工單中找到匹配的
                    if not st.session_state.products_db.empty:
                        queue_view = pending.merge(st.session_state.products_db, on="產品ID", how="left")
                    else:
                        queue_view = pending.copy()
                    queue_view["temp_sort"] = range(1, len(queue_view) + 1)
                    
                    # 生成選單顯示文字來匹配
                    def make_label(row):
                        if "客戶名" in row and pd.notna(row["客戶名"]):
                            spec = f"{dm.format_size(row['長'])}x{dm.format_size(row['寬'])}x{dm.format_size(row['高'])}"
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
                    matched = queue_view[queue_view["選單顯示"] == saved_wo_label]
                    if not matched.empty:
                        target_pending = matched.iloc[0]
                        wo_label = saved_wo_label
                
                # 如果沒有找到匹配的保存工單，優先選擇"生產中"的工單，接續上一班的生產
                if target_pending is None:
                    # [交接班優化] 優先選擇狀態為"生產中"的工單
                    producing = pending[pending["狀態"] == "生產中"]
                    if not producing.empty:
                        # 如果有生產中的工單，選擇第一個（按排程順序）
                        target_pending = producing.iloc[0]
                    else:
                        # 如果沒有生產中的工單，才選擇第一個待生產的工單
                        target_pending = pending.iloc[0]
                    
                    # 生成選單顯示文字（使用與 render_active_line 相同的邏輯，確保序號正確）
                    if not st.session_state.products_db.empty:
                        queue_view_temp = pending.merge(st.session_state.products_db, on="產品ID", how="left")
                    else:
                        queue_view_temp = pending.copy()
                    queue_view_temp["temp_sort"] = range(1, len(queue_view_temp) + 1)
                    
                    # 找到目標工單在排序後的位置
                    target_matched = queue_view_temp[queue_view_temp["工單號碼"] == target_pending["工單號碼"]]
                    if not target_matched.empty:
                        target_row = target_matched.iloc[0]
                        # 生成選單顯示文字（使用與 render_active_line 相同的邏輯）
                        def make_label(row):
                            if "客戶名" in row and pd.notna(row["客戶名"]):
                                spec = f"{dm.format_size(row['長'])}x{dm.format_size(row['寬'])}x{dm.format_size(row['高'])}"
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
                        
                        wo_label = make_label(target_row)
                    else:
                        # 如果找不到，使用簡單格式（但這不應該發生）
                        if not st.session_state.products_db.empty:
                            product_match = st.session_state.products_db[st.session_state.products_db["產品ID"] == target_pending["產品ID"]]
                            if not product_match.empty:
                                product_row = product_match.iloc[0]
                                spec = f"{dm.format_size(product_row['長'])}x{dm.format_size(product_row['寬'])}x{dm.format_size(product_row['高'])}"
                                density_str = ""
                                density_val = product_row.get("密度", "")
                                if pd.notna(density_val) and str(density_val).strip() != "":
                                    try:
                                        density_str = f"{float(density_val):.1f} | "
                                    except (ValueError, TypeError):
                                        density_str = f"{density_val} | "
                                wo_weight = float(target_pending.get('準重', product_row.get('準重', 0)))
                                wo_label = f"#1 {product_row['客戶名']} | {product_row['溫度等級']} | {product_row['品種']} | {density_str}{spec} | {wo_weight:.3f}kg (數:{int(target_pending['預計數量'])})"
                            else:
                                wo_label = f"#1 {str(target_pending['顯示內容'])} (數:{int(target_pending['預計數量'])})"
                        else:
                            wo_label = f"#1 {str(target_pending['顯示內容'])} (數:{int(target_pending['預計數量'])})"
                
                # 設置工單選擇
                if wo_label:
                    st.session_state[f"sel_wo_{line_name}"] = wo_label
                    # 保存當前選擇（確保持久化）
                    dm.save_current_work_order(line_name, wo_label)
        except Exception as e:
            # 如果自動選擇失敗，不影響開班流程，讓系統使用默認的第一筆
            pass
        
        st.rerun()

