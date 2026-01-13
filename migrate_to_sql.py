"""
資料遷移腳本：將 CSV 檔案遷移到 SQLite 資料庫
執行此腳本一次即可完成遷移
"""

import pandas as pd
import sqlite3
import os
import config
from db_schema import create_tables, DB_FILE

def migrate_csv_to_sql():
    """將所有 CSV 資料遷移到 SQL 資料庫"""
    
    print("=" * 60)
    print("🔄 開始遷移資料：CSV → SQLite")
    print("=" * 60)
    
    # 建立資料表
    create_tables()
    conn = sqlite3.connect(DB_FILE)
    
    # 1. 遷移產品資料
    if os.path.exists(config.FILE_PRODUCTS):
        try:
            df_products = pd.read_csv(config.FILE_PRODUCTS, encoding='utf-8-sig')
            if not df_products.empty:
                # 移除 id 欄位（如果存在），因為資料庫會自動產生
                if 'id' in df_products.columns:
                    df_products = df_products.drop(columns=['id'])
                
                df_products.to_sql('products', conn, if_exists='replace', index=False)
                print(f"✅ 產品資料已遷移：{len(df_products)} 筆")
            else:
                print("⚠️  產品資料檔案為空")
        except Exception as e:
            print(f"❌ 遷移產品資料時發生錯誤：{e}")
    else:
        print("⚠️  找不到產品資料檔案，跳過")
    
    # 2. 遷移工單資料
    if os.path.exists(config.FILE_ORDERS):
        try:
            df_orders = pd.read_csv(config.FILE_ORDERS, encoding='utf-8-sig')
            if not df_orders.empty:
                # 移除 id 欄位（如果存在）
                if 'id' in df_orders.columns:
                    df_orders = df_orders.drop(columns=['id'])
                
                # 確保數值欄位正確
                for col in ["排程順序", "預計數量", "已完成數量"]:
                    if col in df_orders.columns:
                        df_orders[col] = pd.to_numeric(df_orders[col], errors='coerce').fillna(0).astype(int)
                
                df_orders.to_sql('work_orders', conn, if_exists='replace', index=False)
                print(f"✅ 工單資料已遷移：{len(df_orders)} 筆")
            else:
                print("⚠️  工單資料檔案為空")
        except Exception as e:
            print(f"❌ 遷移工單資料時發生錯誤：{e}")
    else:
        print("⚠️  找不到工單資料檔案，跳過")
    
    # 3. 遷移生產紀錄
    if os.path.exists(config.FILE_LOGS):
        try:
            df_logs = pd.read_csv(config.FILE_LOGS, encoding='utf-8-sig')
            if not df_logs.empty:
                # 移除 id 欄位（如果存在）
                if 'id' in df_logs.columns:
                    df_logs = df_logs.drop(columns=['id'])
                
                df_logs.to_sql('production_logs', conn, if_exists='replace', index=False)
                print(f"✅ 生產紀錄已遷移：{len(df_logs)} 筆")
            else:
                print("⚠️  生產紀錄檔案為空")
        except Exception as e:
            print(f"❌ 遷移生產紀錄時發生錯誤：{e}")
    else:
        print("⚠️  找不到生產紀錄檔案，跳過")
    
    conn.close()
    
    print("=" * 60)
    print("✅ 資料遷移完成！")
    print(f"📦 資料庫位置：{DB_FILE}")
    print("=" * 60)
    print("\n⚠️  注意事項：")
    print("1. 原始 CSV 檔案已保留，可作為備份")
    print("2. 建議先測試系統運作正常後，再考慮刪除 CSV 檔案")
    print("3. 如需回退到 CSV，請修改 data_loader.py 和 data_manager.py")


if __name__ == "__main__":
    migrate_csv_to_sql()

