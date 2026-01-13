"""
UI 樣式模組
包含所有 CSS 樣式和 JavaScript 程式碼
"""

def load_styles():
    """載入並應用所有 CSS 和 JavaScript 樣式"""
    import streamlit as st
    
    st.markdown("""
    <style>
        .main .block-container { padding-top: 0.5rem; padding-bottom: 2rem; }
        .section-header { font-size: 22px !important; font-weight: 700 !important; color: #2c3e50; margin: 10px 0; display: flex; align-items: center; border-left: 5px solid #ccc; line-height: 1.2; padding-left: 10px; }
        .header-queue { border-left-color: #FFA500; } .header-pass { border-left-color: #27ae60; } .header-ng { border-left-color: #c0392b; } .header-admin { border-left-color: #e74c3c; } 
        .table-label { font-size: 18px !important; font-weight: 600 !important; color: #444; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
        div[data-baseweb="tab-list"] button { border: 1px solid #d0d0d0 !important; border-radius: 6px !important; padding: 0.5rem 1rem !important; background-color: white !important; margin-bottom: 0px !important; transition: all 0.2s; }
        div[data-baseweb="tab-list"] button:hover { background-color: #f0f2f6 !important; border-color: #b0b0b0 !important; }
        div[data-baseweb="tab-list"] button[aria-selected="true"] { border-color: #e74c3c !important; background-color: #fceceb !important; color: #c0392b !important; }
        div[data-baseweb="tab-highlight"] { display: none !important; }
        div[data-baseweb="tab-list"] button p { font-size: 18px !important; font-weight: 700 !important; }
        div[data-testid="stSelectbox"] > label p, div[data-testid="stTextInput"] > label p { font-size: 16px !important; font-weight: 500 !important; color: #555 !important; }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height: 40px !important; }
        .table-scroll-container { max-height: 400px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 6px; background-color: white; }
        .styled-table { width: 100%; border-collapse: collapse; font-size: 15px; }
        .styled-table th { background-color: #f8f9fa; color: #444; font-weight: 600; text-align: center; padding: 8px; position: sticky; top: 0; z-index: 1; border-bottom: 2px solid #ddd; }
        .styled-table td { padding: 6px 10px; text-align: center; border-bottom: 1px solid #eee; color: #333; }
        .styled-table tbody tr:nth-of-type(even) { background-color: #fcfcfc; }
        .unified-spec-card { background-color: #2c3e50; border-radius: 8px; border-left: 6px solid #95a5a6; box-shadow: 0 2px 5px rgba(0,0,0,0.1); color: white; overflow: hidden; margin-bottom: 5px; border: 1px solid #455a64; height: 480px !important; display: flex; flex-direction: column; justify-content: space-between; }
        .usc-header { background: rgba(0,0,0,0.3); padding: 8px; text-align: center; border-bottom: 1px solid #455a64; }
        .usc-header .u-value { font-size: 2.4rem; font-weight: 900; color: #ffffff; line-height: 1.1; }
        .usc-grid { display: flex; border-bottom: 1px solid #455a64; background-color: #34495e; }
        .usc-item { flex: 1; text-align: center; padding: 6px; border-right: 1px solid #455a64; } .usc-item:last-child { border-right: none; }
        .usc-item .u-label { color: #b0bec5; font-size: 0.75rem; font-weight: bold; display: block; }
        .usc-item .u-value { font-size: 28px !important; font-weight: 900; line-height: 1; color: white; }
        .usc-size-row { background: #233140; padding: 8px; text-align: center; border-bottom: 1px solid #455a64; }
        .usc-size-row .u-value { font-size: 2.0rem; font-weight: 900; color: #ffffff; }
        .usc-range-row { background-color: #2c3e50; padding: 6px; text-align: center; border-bottom: 1px solid #455a64; }
        .usc-range-row .u-value { font-size: 28px !important; font-weight: 900; color: #ffffff; }
        .usc-notes { background: rgba(255, 255, 255, 0.05); padding: 10px; flex-grow: 1; overflow-y: auto; text-align: left; }
        .usc-notes .u-content { color: #ecf0f1; font-size: 1.3rem; line-height: 1.4; margin-top: 5px; }
        .status-container { padding: 0; border-radius: 12px; text-align: center; display: flex; flex-direction: row; height: 300px !important; position: relative; box-shadow: 0 3px 8px rgba(0,0,0,0.15); overflow: hidden; margin-bottom: 20px; }
        .status-pass { background-color: #2980b9; color: white; border: 4px solid #3498db; }
        .status-fail { background-color: #c0392b; color: white; border: 4px solid #e74c3c; }
        .status-ng-ready { background-color: #d35400; color: white; border: 4px solid #e67e22; }
        .status-left-panel { flex: 1; display: flex; justify-content: center; align-items: center; }
        .weight-display { font-size: 9rem; font-weight: 900; line-height: 1; text-shadow: 3px 3px 6px rgba(0,0,0,0.3); margin: 0; color: white; }
        .status-right-panel { width: 160px; background: rgba(0,0,0,0.2); border-left: 1px solid rgba(255,255,255,0.2); display: flex; flex-direction: column; }
        .info-box { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding: 2px; }
        .info-box:last-child { border-bottom: none; }
        .info-label { font-size: 0.8rem; color: #bdc3c7; font-weight: bold; text-transform: uppercase; }
        .info-value { font-size: 1.6rem; font-weight: 900; color: white; }
        .info-value-huge { font-size: 3.2rem; font-weight: 900; color: #f1c40f; line-height: 1; }
        .over-prod { color: #ff6b6b !important; }
        div.stButton > button { white-space: pre-wrap !important; line-height: 1.2 !important; }
        div.stButton > button:disabled { background-color: #bdc3c7 !important; border-color: #95a5a6 !important; color: #7f8c8d !important; cursor: not-allowed !important; }
        div.stButton > button[kind="primary"] { background-color: #e74c3c; border: 1px solid #c0392b; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        div.stButton > button[kind="primary"]:hover { background-color: #ec7063; transform: translateY(-1px); }
        /* [修復] PASS 按鈕強制使用綠色，覆蓋 primary 的紅色樣式 - 使用 data-testid 選擇器 */
        div.stButton > button[kind="primary"][data-testid*="btn_pass_"] {
            background-color: #27ae60 !important;
            border-color: #229954 !important;
            color: white !important;
        }
        div.stButton > button[kind="primary"][data-testid*="btn_pass_"]:hover {
            background-color: #2ecc71 !important;
            border-color: #27ae60 !important;
        }
        div.stButton > button[kind="primary"][data-testid*="btn_pass_"]:disabled {
            background-color: #bdc3c7 !important;
            border-color: #95a5a6 !important;
            color: #7f8c8d !important;
        }
        /* [優化] 記錄良品按鈕使用綠色 - 通過 JavaScript 動態設定，這裡僅作為備用 */
        /* 統一撤銷按鈕高度（只針對撤銷按鈕）*/
        button[data-testid*="undo_"]:not([data-testid*="undo_completed"]):not([data-testid*="undo_dialog"]) { 
            height: 50px !important; 
            min-height: 50px !important; 
            max-height: 50px !important; 
            box-sizing: border-box !important;
        }
        /* 對話框中的確認結算按鈕樣式 */
        div[data-testid="stDialog"] button:has-text("確認結算並下班"),
        div[data-testid="stDialog"] button:has-text("Confirm & Logout") {
            height: 45px !important;
            min-height: 45px !important;
            padding: 6px 16px !important;
            font-size: 16px !important;
        }
        .shift-card { padding: 10px 20px; border-radius: 12px; background: linear-gradient(135deg, #f3e5f5, #e1bee7); border-left: 8px solid #8e24aa; display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .shift-title { font-size: 22px; font-weight: 900; color: #4a148c; display: flex; align-items: center; gap: 10px; }
        .shift-badge { font-size: 28px; color: white; background-color: #8e24aa; padding: 8px 20px; border-radius: 20px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2); margin-left: 10px; }
        .idle-screen { text-align: center; padding: 40px 20px; background-color: #e0f2f1; border-radius: 15px; border: 3px dashed #00897b; color: #00695c; margin-bottom: 20px; }
        .idle-icon { font-size: 60px; margin-bottom: 10px; }
        .idle-text { font-size: 32px; font-weight: 900; color: #004d40; margin-bottom: 5px; }
        .idle-subtext { font-size: 18px; color: #00796b; }
        .no-task-screen { text-align: center; padding: 60px 20px; background-color: #f5f5f5; border-radius: 15px; border: 3px dashed #bdbdbd; color: #616161; margin-bottom: 20px; }
        .no-task-icon { font-size: 70px; margin-bottom: 15px; opacity: 0.7; }
        .no-task-text { font-size: 32px; font-weight: 900; color: #616161; margin-bottom: 5px; }
        .no-task-subtext { font-size: 18px; color: #757575; }
        .custom-main-title { font-size: 28px; font-weight: 900; color: #2c3e50; margin-top: 10px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; }
        /* 隱藏多頁面導航選項（main、admin、production）*/
        nav[data-testid="stSidebarNav"] { display: none !important; visibility: hidden !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
        nav[data-testid="stSidebarNav"] ul { display: none !important; visibility: hidden !important; }
        div[data-testid="stSidebarNav"] { display: none !important; visibility: hidden !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
        /* 隱藏側邊欄中的導航連結容器 */
        section[data-testid="stSidebar"] > div:first-child > nav,
        section[data-testid="stSidebar"] > div:first-child nav[data-testid="stSidebarNav"],
        section[data-testid="stSidebar"] nav[data-testid="stSidebarNav"],
        section[data-testid="stSidebar"] > div[class*="css"]:first-child nav { display: none !important; visibility: hidden !important; height: 0 !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; }
        /* 讓 data_editor 中的 checkbox 始終可見 */
        div[data-testid="stDataEditor"] tbody td div[data-baseweb="checkbox"],
        div[data-testid="stDataEditor"] tbody td input[type="checkbox"],
        div[data-testid="stDataEditor"] tbody td label[data-baseweb="checkbox"] {
            opacity: 1 !important;
            visibility: visible !important;
            display: block !important;
        }
        /* [修復殘影] 隱藏非活動 tab 中的 shift-card 元素 */
        div[data-baseweb="tab-panel"][aria-hidden="true"] .shift-card,
        div[data-baseweb="tab-panel"][aria-hidden="true"] .shift-title {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
    </style>

    <script>
    function hidePageNavigation() {
        // 隱藏多頁面導航選項（main、admin、production）
        try {
            var doc = window.parent && window.parent.document ? window.parent.document : document;
            var navs = doc.querySelectorAll('nav[data-testid="stSidebarNav"], div[data-testid="stSidebarNav"]');
            for (var i = 0; i < navs.length; i++) {
                navs[i].style.display = 'none';
                navs[i].style.visibility = 'hidden';
                navs[i].style.height = '0';
                navs[i].style.margin = '0';
                navs[i].style.padding = '0';
                navs[i].style.overflow = 'hidden';
            }
            // 隱藏側邊欄第一個導航元素
            var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                var firstNav = sidebar.querySelector('nav:first-of-type, div:first-child > nav');
                if (firstNav) {
                    firstNav.style.display = 'none';
                    firstNav.style.visibility = 'hidden';
                    firstNav.style.height = '0';
                }
            }
        } catch(e) {
            // 忽略錯誤
        }
    }
    
    function styleButtons() {
        // 嘗試從主窗口和 iframe 中獲取按鈕，包括所有 tab 中的按鈕
        var doc = window.parent && window.parent.document ? window.parent.document : document;
        // 獲取所有按鈕，包括隱藏的 tab 中的按鈕（使用 querySelectorAll 確保包含所有）
        var buttons = doc.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            if (!btn) continue;
            var txt = btn.innerText || btn.textContent || ''; 
            
            if (txt.includes("PASS")) {
                // [優化] 記錄良品按鈕使用綠色，表示成功/通過
                // 強制應用樣式，確保覆蓋 Streamlit 的 primary 按鈕紅色樣式
                btn.style.setProperty('height', '120px', 'important'); 
                btn.style.setProperty('min-height', '120px', 'important'); 
                btn.style.setProperty('font-size', '28px', 'important'); 
                btn.style.setProperty('font-weight', '900', 'important');
                btn.style.setProperty('border-radius', '12px', 'important');
                
                // 只在按鈕未禁用時應用綠色
                if (!btn.disabled) {
                    btn.style.setProperty('background-color', '#27ae60', 'important'); 
                    btn.style.setProperty('border-color', '#229954', 'important');
                    btn.style.setProperty('color', 'white', 'important'); 
                    // 使用 onmouseenter 和 onmouseleave 避免重複添加事件監聽器
                    if (!btn.hasAttribute('data-pass-styled')) {
                        btn.setAttribute('data-pass-styled', 'true');
                        btn.onmouseenter = function() {
                            if (!this.disabled) {
                                this.style.setProperty('background-color', '#2ecc71', 'important');
                                this.style.setProperty('border-color', '#27ae60', 'important');
                            }
                        };
                        btn.onmouseleave = function() {
                            if (!this.disabled) {
                                this.style.setProperty('background-color', '#27ae60', 'important');
                                this.style.setProperty('border-color', '#229954', 'important');
                            }
                        };
                    }
                } else {
                    // 禁用時保持默認灰色樣式（CSS 會處理）
                    btn.style.setProperty('background-color', '#bdc3c7', 'important');
                    btn.style.setProperty('border-color', '#95a5a6', 'important');
                    btn.style.setProperty('color', '#7f8c8d', 'important');
                }
            } else if (txt.includes("NG") && txt.includes("紀錄")) {
                btn.style.setProperty('height', '120px', 'important'); 
                btn.style.setProperty('min-height', '120px', 'important'); 
                btn.style.setProperty('font-size', '28px', 'important'); 
                btn.style.setProperty('font-weight', '900', 'important');
                btn.style.setProperty('background-color', '#bdc3c7', 'important'); 
                btn.style.setProperty('border-color', '#95a5a6', 'important');
                btn.style.setProperty('color', '#2c3e50', 'important'); 
                btn.style.setProperty('border-radius', '12px', 'important');
            } else if (txt.includes("開班上工")) {
                btn.style.setProperty('font-size', '24px', 'important'); 
                btn.style.setProperty('font-weight', 'bold', 'important'); 
                btn.style.setProperty('height', '80px', 'important');
                btn.style.setProperty('background-color', '#e74c3c', 'important'); 
                btn.style.setProperty('border-color', '#c0392b', 'important');
                btn.style.setProperty('color', 'white', 'important');
            } else if (txt.includes("結算下班")) {
                btn.style.setProperty('background-color', '#e74c3c', 'important'); 
                btn.style.setProperty('border-color', '#c0392b', 'important');
                btn.style.setProperty('color', 'white', 'important');
                btn.style.setProperty('font-weight', 'bold', 'important');
            } else if (txt.includes("確認粒子重量") || txt.includes("讀取重量")) {
                btn.style.setProperty('background-color', '#2980b9', 'important'); 
                btn.style.setProperty('border-color', '#2471a3', 'important');
                btn.style.setProperty('color', 'white', 'important');
            } else if (txt.includes("確認結算並下班") || txt.includes("Confirm & Logout")) {
                btn.style.setProperty('background-color', '#e74c3c', 'important'); 
                btn.style.setProperty('border-color', '#c0392b', 'important');
                btn.style.setProperty('color', 'white', 'important');
                btn.style.setProperty('font-size', '16px', 'important');
                btn.style.setProperty('font-weight', 'bold', 'important');
                btn.style.setProperty('height', '45px', 'important');
                btn.style.setProperty('min-height', '45px', 'important');
                btn.style.setProperty('max-height', '45px', 'important');
                btn.style.setProperty('padding', '6px 16px', 'important');
                btn.style.setProperty('line-height', '1.2', 'important');
            } else if (txt.includes("撤銷上一筆")) {
                // 統一撤銷按鈕高度（只針對撤銷按鈕，不影響父容器）
                // 檢查是否真的是撤銷按鈕（通過 data-testid 確認）
                var testId = btn.getAttribute('data-testid') || '';
                if (testId.includes('undo_') && !testId.includes('undo_completed') && !testId.includes('undo_dialog')) {
                    btn.style.setProperty('height', '50px', 'important');
                    btn.style.setProperty('min-height', '50px', 'important');
                    btn.style.setProperty('max-height', '50px', 'important');
                    btn.style.setProperty('font-size', '18px', 'important');
                    btn.style.setProperty('font-weight', 'bold', 'important');
                    btn.style.setProperty('box-sizing', 'border-box', 'important');
                }
            }
        }
    }
    
    function showCheckboxes() {
        // 強制顯示 data_editor 中的所有 checkbox
        var doc = window.parent && window.parent.document ? window.parent.document : document;
        var checkboxes = doc.querySelectorAll('div[data-testid="stDataEditor"] tbody td input[type="checkbox"]');
        for (var i = 0; i < checkboxes.length; i++) {
            var cb = checkboxes[i];
            if (cb) {
                cb.style.setProperty('opacity', '1', 'important');
                cb.style.setProperty('visibility', 'visible', 'important');
                cb.style.setProperty('display', 'block', 'important');
                // 也處理父容器
                var parent = cb.closest('td');
                if (parent) {
                    var checkboxContainer = parent.querySelector('div[data-baseweb="checkbox"]');
                    if (checkboxContainer) {
                        checkboxContainer.style.setProperty('opacity', '1', 'important');
                        checkboxContainer.style.setProperty('visibility', 'visible', 'important');
                        checkboxContainer.style.setProperty('display', 'block', 'important');
                    }
                }
            }
        }
    }
    
    function clearStaleShiftCards() {
        // [修復殘影] 清除頁面切換時殘留的 shift-card 元素
        try {
            var doc = window.parent && window.parent.document ? window.parent.document : document;
            
            // 改進頁面檢測：檢查 .custom-main-title 的文字內容來判斷是否在生產頁面
            var titleElement = doc.querySelector('.custom-main-title');
            var isProductionPage = false;
            
            if (titleElement) {
                var titleText = titleElement.innerText || titleElement.textContent || '';
                // 如果標題包含 "現場作業" 或 "🏭"，則判定為生產頁面
                isProductionPage = titleText.includes('現場作業') || titleText.includes('🏭');
            }
            
            // 如果不在生產頁面（管理頁面），強制移除所有 shift-card 元素
            if (!isProductionPage) {
                var shiftCards = doc.querySelectorAll('.shift-card');
                for (var i = 0; i < shiftCards.length; i++) {
                    // 使用 remove() 完全移除元素，而非僅隱藏
                    shiftCards[i].remove();
                }
            } else {
                // 在生產頁面時，只隱藏非活動 tab 中的 shift-card
                var tabPanels = doc.querySelectorAll('div[data-baseweb="tab-panel"]');
                for (var j = 0; j < tabPanels.length; j++) {
                    var panel = tabPanels[j];
                    if (panel.getAttribute('aria-hidden') === 'true') {
                        var cards = panel.querySelectorAll('.shift-card');
                        for (var k = 0; k < cards.length; k++) {
                            cards[k].style.display = 'none';
                            cards[k].style.visibility = 'hidden';
                            cards[k].style.opacity = '0';
                            cards[k].style.height = '0';
                            cards[k].style.margin = '0';
                            cards[k].style.padding = '0';
                            cards[k].style.overflow = 'hidden';
                        }
                    }
                }
                
                // 額外檢查：清除任何不在可見 tab 中的 shift-card 元素
                var allShiftCards = doc.querySelectorAll('.shift-card');
                for (var m = 0; m < allShiftCards.length; m++) {
                    var card = allShiftCards[m];
                    // 檢查元素是否在任何 tab-panel 中
                    var isInTabPanel = false;
                    var parent = card.parentElement;
                    while (parent && parent !== doc.body) {
                        if (parent.getAttribute && parent.getAttribute('data-baseweb') === 'tab-panel') {
                            isInTabPanel = true;
                            // 檢查這個 tab-panel 是否可見
                            if (parent.getAttribute('aria-hidden') === 'true') {
                                // 在隱藏的 tab 中，移除元素
                                card.remove();
                                break;
                            }
                        }
                        parent = parent.parentElement;
                    }
                    // 如果 shift-card 不在任何 tab-panel 中，也移除它（可能是殘留的）
                    if (!isInTabPanel) {
                        card.remove();
                    }
                }
            }
        } catch(e) {
            // 忽略錯誤
        }
    }
    
    // 隱藏多頁面導航
    hidePageNavigation();
    setInterval(hidePageNavigation, 500);
    // [修復殘影] 清除殘留的 shift-card 元素
    clearStaleShiftCards();
    setInterval(clearStaleShiftCards, 100);
    // [優化] 增加執行頻率，確保 PASS 按鈕顏色正確應用
    setInterval(styleButtons, 100);
    setTimeout(styleButtons, 50);
    setTimeout(styleButtons, 100);
    setTimeout(styleButtons, 200);
    setTimeout(styleButtons, 300);
    setTimeout(styleButtons, 500);
    // 強制顯示 checkbox
    setInterval(showCheckboxes, 100);
    setTimeout(showCheckboxes, 50);
    setTimeout(showCheckboxes, 100);
    setTimeout(showCheckboxes, 200);
    setTimeout(showCheckboxes, 300);
    setTimeout(showCheckboxes, 500);
    </script>
    """, unsafe_allow_html=True)

