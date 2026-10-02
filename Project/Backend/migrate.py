import sqlite3
import mysql.connector
import os
import sys

def migrate():
    print("=== SQLite to MySQL Migration ===")
    
    sqlite_db_path = "insta_automate.db"
    if not os.path.exists(sqlite_db_path):
        print(f"[ERROR] SQLite database file '{sqlite_db_path}' not found. Nothing to migrate.")
        return False
        
    mysql_config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "insta_automate"
    }
    
    # 1. Connect to both databases
    try:
        lite_conn = sqlite3.connect(sqlite_db_path)
        lite_cur = lite_conn.cursor()
        print("[SUCCESS] Connected to SQLite database.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to SQLite: {e}")
        return False
        
    try:
        my_conn = mysql.connector.connect(**mysql_config)
        my_cur = my_conn.cursor()
        print("[SUCCESS] Connected to MySQL database.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MySQL: {e}")
        lite_conn.close()
        return False
        
    # List of tables to migrate (in correct dependency order)
    tables = [
        "users",
        "workspaces",
        "workspace_members",
        "subscriptions",
        "accounts",
        "targets",
        "message_templates",
        "bot_logs",
        "settings",
        "meta_connections",
        "monitored_posts",
        "processed_comments",
        "opt_outs",
        "tg_bot_configs",
        "tg_channels",
        "tg_message_templates",
        "tg_scheduled_posts",
        "tg_moderation_rules",
        "tg_post_logs",
        "notifications",
        "media_files",
        "contacts",
        "feature_flags",
        "campaigns",
        "automation_runners",
        "audit_logs"
    ]
    
    try:
        # Disable foreign key checks in MySQL for smooth bulk insert
        my_cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
        
        for table in tables:
            print(f"Migrating table '{table}'...")
            
            # Check if table exists in SQLite
            lite_cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not lite_cur.fetchone():
                print(f"  [WARNING] Table '{table}' does not exist in SQLite. Skipping.")
                continue
                
            # Truncate table in MySQL
            try:
                my_cur.execute(f"TRUNCATE TABLE {table}")
            except mysql.connector.Error as err:
                # If truncate fails because it's not created yet, create it using sqlalchemy later
                print(f"  [WARNING] Failed to truncate '{table}' (might not exist yet): {err}")
                continue
                
            # Get data from SQLite
            lite_cur.execute(f"SELECT * FROM {table}")
            rows = lite_cur.fetchall()
            if not rows:
                print(f"  No rows in '{table}'.")
                continue
                
            # Get columns description to prepare MySQL statement
            lite_cur.execute(f"PRAGMA table_info({table})")
            columns_info = lite_cur.fetchall()
            columns_names = [col[1] for col in columns_info]
            
            placeholders = ", ".join(["%s"] * len(columns_names))
            cols_str = ", ".join([f"`{name}`" for name in columns_names])
            insert_query = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"
            
            # Insert into MySQL
            # Convert row values (e.g. handle SQLite booleans/dates)
            converted_rows = []
            for row in rows:
                converted_row = []
                for val in row:
                    # SQLite returns booleans as 0 or 1, which works fine with tinyint in MySQL
                    converted_row.append(val)
                converted_rows.append(tuple(converted_row))
                
            my_cur.executemany(insert_query, converted_rows)
            print(f"  [SUCCESS] Migrated {len(rows)} rows into MySQL.")
            
        my_conn.commit()
        print("[SUCCESS] All data committed to MySQL database successfully!")
        
    except Exception as e:
        my_conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        return False
    finally:
        my_cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
        lite_conn.close()
        my_conn.close()
        
    return True

if __name__ == "__main__":
    migrate()
