"""臨時腳本：從 main.py 提取程式碼到模組檔案"""
import re

# 讀取 main.py
with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 提取後台管理部分 (382-757行，索引從0開始是381-756)
admin_lines = lines[381:757]
admin_code = ''.join(admin_lines)

# 轉換為函數格式
admin_code = admin_code.replace('if menu == "後台：系統管理中心":', 'def render_admin_page(all_line_statuses, save_data_func):')
admin_code = admin_code.replace('save_data()', 'save_data_func()')

# 加入必要的導入
admin_header = """\"\"\"
後台管理頁面模組
包含產品建檔、排程管理、報表中心等功能
\"\"\"

import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
import io
import config
import data_manager as dm
from data_loader import save_data

"""

admin_full = admin_header + admin_code

# 寫入檔案
with open('pages/admin.py', 'w', encoding='utf-8') as f:
    f.write(admin_full)

print("✅ pages/admin.py 已建立")

# 提取現場作業部分 (758-1075行，索引從0開始是757-1074)
production_lines = lines[757:1075]
production_code = ''.join(production_lines)

# 轉換為函數格式
production_code = production_code.replace('elif menu == "現場：產線秤重作業":', 'def render_production_page(all_line_statuses, save_data_func):')
production_code = production_code.replace('save_data()', 'save_data_func()')
production_code = production_code.replace('show_end_shift_dialog(line_name, cur_s, cur_g)', 'show_end_shift_dialog(line_name, cur_s, cur_g, all_line_statuses)')
production_code = production_code.replace('show_start_shift_dialog(line_name)', 'show_start_shift_dialog(line_name, all_line_statuses)')

# 加入必要的導入
production_header = """\"\"\"
現場作業頁面模組
包含產線秤重作業、工單管理、實時監控等功能
\"\"\"

import streamlit as st
import pandas as pd
from datetime import datetime
import time
import textwrap
import config
import data_manager as dm
from data_loader import save_data
from dialogs import show_undo_confirm, show_end_shift_dialog, show_start_shift_dialog

"""

production_full = production_header + production_code

# 寫入檔案
with open('pages/production.py', 'w', encoding='utf-8') as f:
    f.write(production_full)

print("✅ pages/production.py 已建立")
print("✅ 所有模組檔案已建立完成！")



