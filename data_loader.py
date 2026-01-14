"""
資料載入與儲存模組
處理所有資料庫的載入、儲存和初始化邏輯
使用 SQLite 資料庫
"""

import pandas as pd
import os
from datetime import datetime
import streamlit as st
import sqlite3
import config
import data_manager as dm
from db_schema import get_connection, init_database

PRODUCT_COLUMNS = [
    "產品ID", "客戶名", "溫度等級", "品種", "密度", "長", "寬", "高",
    "下限", "準重", "上限", "備註1", "備註2", "備註3"
]


def reload_products():
    """從資料庫重新載入 products 到 session_state（避免用記憶體資料覆蓋 DB）"""
    init_database()
    conn = get_connection()
    try:
        query = f"SELECT {', '.join(PRODUCT_COLUMNS)} FROM products"
        st.session_state.products_db = pd.read_sql_query(query, conn)

        # 清理備註欄位中的 HTML 標籤（防止從 Excel 複製貼上時帶入 HTML）
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
    finally:
        conn.close()


def upsert_products(df_products: pd.DataFrame):
    """
    將產品資料增量寫入資料庫：
    - 若 產品ID 不存在：INSERT
    - 若 產品ID 已存在：UPDATE
    """
    if df_products is None or df_products.empty:
        return

    # 只保留 products 欄位，避免夾帶 id/時間戳等欄位
    df = df_products.copy()
    for col in ['id', 'created_at', 'updated_at']:
        if col in df.columns:
            df = df.drop(columns=[col])
    df = df[PRODUCT_COLUMNS]

    init_database()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout = 30000")

        sql = """
            INSERT INTO products (
                產品ID, 客戶名, 溫度等級, 品種, 密度, 長, 寬, 高,
                下限, 準重, 上限, 備註1, 備註2, 備註3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(產品ID) DO UPDATE SET
                客戶名=excluded.客戶名,
                溫度等級=excluded.溫度等級,
                品種=excluded.品種,
                密度=excluded.密度,
                長=excluded.長,
                寬=excluded.寬,
                高=excluded.高,
                下限=excluded.下限,
                準重=excluded.準重,
                上限=excluded.上限,
                備註1=excluded.備註1,
                備註2=excluded.備註2,
                備註3=excluded.備註3,
                updated_at=CURRENT_TIMESTAMP
        """

        rows = [
            (
                r["產品ID"], r["客戶名"], r["溫度等級"], r["品種"], r["密度"],
                r["長"], r["寬"], r["高"], r["下限"], r["準重"], r["上限"],
                r["備註1"], r["備註2"], r["備註3"]
            )
            for _, r in df.iterrows()
        ]
        cursor.executemany(sql, rows)
        conn.commit()
    finally:
        conn.close()


def delete_products(product_ids: list[str]):
    """依產品ID清單刪除 products 記錄"""
    if not product_ids:
        return
    init_database()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout = 30000")
        placeholders = ",".join(["?"] * len(product_ids))
        cursor.execute(f"DELETE FROM products WHERE 產品ID IN ({placeholders})", product_ids)
        conn.commit()
    finally:
        conn.close()


def load_data():
    """從 SQL 資料庫載入所有資料到 session_state"""
    # 初始化資料庫（如果不存在）
    init_database()
    
    conn = get_connection()
    
    # 載入產品資料庫
    if 'products_db' not in st.session_state:
        try:
            query = f"SELECT {', '.join(PRODUCT_COLUMNS)} FROM products"
            st.session_state.products_db = pd.read_sql_query(query, conn)
            
            # 清理備註欄位中的 HTML 標籤（防止從 Excel 複製貼上時帶入 HTML）
            import re
            def clean_note_field(val):
                """清理備註欄位中的 HTML 標籤"""
                if pd.isna(val) or str(val).lower() == 'none':
                    return ""
                val_str = str(val)
                # 移除 HTML 標籤
                val_str = re.sub(r'<[^>]+>', '', val_str)
                # 移除多餘的空白字符
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
    
    # 載入工單資料庫
    # [修正] 每次載入時都從資料庫重新讀取，確保資料同步
    try:
        query = f"SELECT {', '.join(config.ORDER_COLUMNS)} FROM work_orders ORDER BY 產線, 排程順序"
        st.session_state.work_orders_db = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"載入工單資料時發生錯誤: {e}")
        # 如果載入失敗，確保至少有一個空的 DataFrame
        if 'work_orders_db' not in st.session_state:
            st.session_state.work_orders_db = pd.DataFrame(columns=config.ORDER_COLUMNS)
    
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

    # 載入生產紀錄
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
    
    # [優化] 初始化已保存的記錄計數器（用於增量更新）
    # 當從資料庫載入資料時，所有記錄都已經保存，所以計數器等於記錄數量
    if 'production_logs_saved_count' not in st.session_state:
        st.session_state['production_logs_saved_count'] = len(st.session_state.production_logs)
    
    conn.close()


def save_data():
    """儲存所有資料到 SQL 資料庫（優化版：使用增量更新提升效能）"""
    conn = get_connection()
    cursor = conn.cursor()
    
    def convert_timestamps_to_string(df):
        """將 DataFrame 中的 Timestamp 類型欄位轉換為字符串"""
        df = df.copy()
        for col in df.columns:
            # 檢查是否為 datetime 或 Timestamp 類型
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                # 將 Timestamp 轉換為字符串格式
                df[col] = df[col].astype(str)
            else:
                # 檢查欄位中是否有 Timestamp 對象（處理 object 類型的欄位）
                try:
                    sample = df[col].dropna()
                    if len(sample) > 0:
                        # 檢查是否有任何值是 Timestamp 類型
                        has_timestamp = any(isinstance(val, pd.Timestamp) for val in sample.head(10))
                        if has_timestamp:
                            # 將整個欄位轉換為字符串
                            df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else x)
                except Exception:
                    # 如果轉換失敗，跳過該欄位
                    pass
        return df
    
    def convert_value_to_sqlite_compatible(value):
        """將單個值轉換為 SQLite 相容的類型"""
        if pd.isna(value) or value is None:
            return None
        elif isinstance(value, pd.Timestamp):
            # 轉換為字符串格式
            return str(value)
        elif isinstance(value, datetime):
            # 轉換為字符串格式
            return str(value)
        elif isinstance(value, (int, float, str)):
            return value
        elif isinstance(value, bool):
            # SQLite 支援 INTEGER (0/1) 表示布林值
            return 1 if value else 0
        else:
            # 對於其他類型（如 numpy 類型），轉換為字符串
            try:
                return str(value)
            except Exception:
                return None
    
    try:
        # ⚠️ 注意：products 不在這裡儲存！
        # 產品資料改為在後台以 upsert_products/delete_products 直接對 DB 增量寫入，
        # 避免任何一台/任何 session 以空的 products_db 觸發全表刪除造成資料消失。
        
        # 儲存工單資料（使用全量替換：先刪除所有，再插入新的，確保刪除操作能正確反映）
        if 'work_orders_db' in st.session_state:
            # [關鍵修正] 先刪除所有舊資料，然後插入新資料
            # 這樣可以確保刪除操作能正確反映到資料庫中
            cursor.execute("DELETE FROM work_orders")
            
            if not st.session_state.work_orders_db.empty:
                # 準備資料（移除 id 和自動生成的時間戳欄位）
                df_orders = st.session_state.work_orders_db.copy()
                if 'id' in df_orders.columns:
                    df_orders = df_orders.drop(columns=['id'])
                # 移除自動生成的時間戳欄位（由資料庫自動處理）
                for col in ['created_at', 'updated_at']:
                    if col in df_orders.columns:
                        df_orders = df_orders.drop(columns=[col])
                # 轉換任何 Timestamp 類型欄位
                df_orders = convert_timestamps_to_string(df_orders)
                
                # 插入所有工單
                for _, row in df_orders.iterrows():
                    cursor.execute("""
                        INSERT INTO work_orders (
                            產線, 排程順序, 工單號碼, 產品ID, 顯示內容, 品種, 密度,
                            準重, 預計數量, 已完成數量, 狀態, 建立時間, 詳細規格字串
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['產線'], row['排程順序'], row['工單號碼'], row['產品ID'], row['顯示內容'],
                        row['品種'], row['密度'], row['準重'], row['預計數量'], row['已完成數量'],
                        row['狀態'], row['建立時間'], row['詳細規格字串']
                    ))
        
        # [關鍵優化] 儲存生產紀錄：只插入新記錄，不刪除舊記錄
        # 這樣可以大幅提升效能，特別是當記錄數量很大時
        if 'production_logs' in st.session_state:
            saved_count_key = 'production_logs_saved_count'
            saved_count = st.session_state.get(saved_count_key, 0)
            current_count = len(st.session_state.production_logs) if not st.session_state.production_logs.empty else 0
            
            # 處理記錄數量減少的情況（撤銷操作）
            if current_count < saved_count:
                # 如果記錄數量減少，需要從資料庫中刪除對應的記錄
                # 由於撤銷操作會刪除最後一筆記錄，我們需要找到並刪除資料庫中對應的記錄
                # 這裡使用時間戳來匹配（取 session_state 中最後一筆記錄的時間作為參考）
                if not st.session_state.production_logs.empty:
                    # 獲取 session_state 中所有記錄的時間戳
                    saved_times = set(st.session_state.production_logs['時間'].astype(str).tolist())
                    # 刪除資料庫中不在 saved_times 中的記錄（這些是被撤銷的記錄）
                    cursor.execute("SELECT 時間 FROM production_logs")
                    db_times = [row[0] for row in cursor.fetchall()]
                    times_to_delete = [t for t in db_times if t not in saved_times]
                    if times_to_delete:
                        placeholders = ','.join(['?' for _ in times_to_delete])
                        cursor.execute(f"DELETE FROM production_logs WHERE 時間 IN ({placeholders})", times_to_delete)
                # 更新已保存的記錄數量
                st.session_state[saved_count_key] = current_count
            # 處理新增記錄的情況
            elif current_count > saved_count and not st.session_state.production_logs.empty:
                # 取得新增的記錄（從 saved_count 開始到結尾）
                new_logs = st.session_state.production_logs.iloc[saved_count:].copy()
                
                # 準備資料（移除 id 和自動生成的時間戳欄位）
                if 'id' in new_logs.columns:
                    new_logs = new_logs.drop(columns=['id'])
                if 'created_at' in new_logs.columns:
                    new_logs = new_logs.drop(columns=['created_at'])
                # 轉換任何 Timestamp 類型欄位
                new_logs = convert_timestamps_to_string(new_logs)
                
                # [改進] 檢查資料庫中是否已存在相同記錄（防止重複寫入）
                if not new_logs.empty:
                    filtered_logs = []
                    for _, row in new_logs.iterrows():
                        # 檢查是否存在相同的記錄（時間、產線、工單號、重量）
                        cursor.execute("""
                            SELECT COUNT(*) FROM production_logs 
                            WHERE 時間 = ? AND 產線 = ? AND 工單號 = ? 
                            AND ABS(實測重 - ?) < 0.01
                        """, (row['時間'], row['產線'], row['工單號'], row['實測重']))
                        exists = cursor.fetchone()[0] > 0
                        
                        if not exists:
                            filtered_logs.append(row)
                        else:
                            print(f"⚠️ 跳過重複記錄：{row['時間']} - {row['產線']} - {row['工單號']} - {row['實測重']} kg")
                    
                    # 只插入不重複的記錄
                    if filtered_logs:
                        filtered_df = pd.DataFrame(filtered_logs)
                        filtered_df.to_sql('production_logs', conn, if_exists='append', index=False)
                        # 更新已保存的記錄數量（只計算實際插入的記錄數）
                        st.session_state[saved_count_key] = saved_count + len(filtered_logs)
                    else:
                        # 如果所有記錄都是重複的，仍然更新計數器（避免無限循環）
                        st.session_state[saved_count_key] = current_count
                else:
                    # 更新已保存的記錄數量
                    st.session_state[saved_count_key] = current_count
        
        conn.commit()
    except Exception as e:
        import traceback
        error_detail = str(e)
        traceback_str = traceback.format_exc()
        print(f"儲存資料時發生錯誤: {error_detail}")
        print(traceback_str)
        conn.rollback()
        # 重新拋出異常，讓調用端能夠處理
        raise Exception(f"儲存資料時發生錯誤: {error_detail}")
    finally:
        conn.close()


def add_work_orders(new_orders):
    """新增工單到資料庫（用於批次加入）"""
    if not new_orders:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # [關鍵修正] 直接插入到資料庫，不依賴 session_state
        # 這樣可以確保即使 session_state 有問題，資料也能正確保存
        for order_data in new_orders:
            # 將列表轉換為字典
            order_dict = dict(zip(config.ORDER_COLUMNS, order_data))
            
            # 檢查該工單是否已存在（避免重複插入）
            cursor.execute("""
                SELECT id FROM work_orders 
                WHERE 產線 = ? AND 工單號碼 = ?
            """, (order_dict['產線'], order_dict['工單號碼']))
            
            existing = cursor.fetchone()
            
            if not existing:
                # 工單不存在，插入新記錄
                # 轉換時間戳為字符串
                create_time = str(order_dict['建立時間']) if pd.notna(order_dict['建立時間']) else None
                
                cursor.execute("""
                    INSERT INTO work_orders (
                        產線, 排程順序, 工單號碼, 產品ID, 顯示內容, 品種, 密度,
                        準重, 預計數量, 已完成數量, 狀態, 建立時間, 詳細規格字串
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_dict['產線'], order_dict['排程順序'], order_dict['工單號碼'], 
                    order_dict['產品ID'], order_dict['顯示內容'], order_dict['品種'], 
                    order_dict['密度'], order_dict['準重'], order_dict['預計數量'], 
                    order_dict['已完成數量'], order_dict['狀態'], create_time, 
                    order_dict['詳細規格字串']
                ))
        
        conn.commit()
        
        # [修正] 插入完成後，重新載入 session_state 以保持同步
        reload_work_orders()
        
    except Exception as e:
        print(f"新增工單時發生錯誤: {e}")
        import traceback
        print(traceback.format_exc())
        conn.rollback()
        raise
    finally:
        conn.close()


def get_next_work_order_sequence():
    """
    從資料庫查詢下一個工單序號（用於生成唯一的工單號碼）
    工單號碼格式：WO-{MMDD}-{序號:04d}
    此函數會查詢今天的所有工單，找出最大的序號，然後加 1
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 取得今天的日期字串（MMDD 格式）
        today_str = datetime.now().strftime('%m%d')
        
        # 查詢今天的所有工單號碼
        cursor.execute("""
            SELECT 工單號碼 FROM work_orders 
            WHERE 工單號碼 LIKE ?
            ORDER BY 工單號碼 DESC
        """, (f"WO-{today_str}-%",))
        
        results = cursor.fetchall()
        
        max_sequence = 0
        
        # 解析每個工單號碼，找出最大的序號
        for (wo_id,) in results:
            try:
                # 工單號碼格式：WO-{MMDD}-{序號:04d}
                # 例如：WO-1225-0001
                parts = wo_id.split('-')
                if len(parts) == 3 and parts[0] == 'WO' and parts[1] == today_str:
                    sequence = int(parts[2])
                    if sequence > max_sequence:
                        max_sequence = sequence
            except (ValueError, IndexError):
                # 如果解析失敗，跳過這個工單號碼
                continue
        
        # 返回下一個序號
        return max_sequence + 1
        
    except Exception as e:
        print(f"查詢工單序號時發生錯誤: {e}")
        # 如果發生錯誤，返回 1（從頭開始）
        return 1
    finally:
        conn.close()


def reload_work_orders():
    """強制重新載入工單資料（用於同步伺服器資料）"""
    conn = get_connection()
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
        print(f"重新載入工單資料時發生錯誤: {e}")
    finally:
        conn.close()


def update_work_order_status(work_order_id, status):
    """更新工單狀態"""
    if 'work_orders_db' not in st.session_state:
        load_data()
    
    mask = st.session_state.work_orders_db["工單號碼"] == work_order_id
    if mask.any():
        idx = st.session_state.work_orders_db[mask].index[0]
        st.session_state.work_orders_db.at[idx, "狀態"] = status
        st.session_state.work_orders_db = dm.normalize_sequences(st.session_state.work_orders_db)
        save_data()
        return True
    return False
