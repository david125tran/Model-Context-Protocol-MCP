# ---------------------------------- Libraries ----------------------------------
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
import os
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus


# ---------------------------------- Functions ----------------------------------
def print_banner(text: str) -> None:
    """
    Create a banner for easier visualization of what's going on
    """
    banner_len = len(text)
    mid = 49 - banner_len // 2

    print("\n\n\n")
    print("*" + "-*" * 50)
    if (banner_len % 2 != 0):
        print("*"  + " " * mid + text + " " * mid + "*")
    else:
        print("*"  + " " * mid + text + " " + " " * mid + "*")
    print("*" + "-*" * 50)


# ---------------------------------- Variables ----------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

file_path = script_dir + "\\Supplement_Sales_Weekly.csv"


# ---------------------------------- Load DB Environment Variables ----------------------------------
print_banner("Load DB Environment Variables")

# Load db environment variables
load_dotenv(dotenv_path=parent_dir + r"\db.env", override=True)

# Load database variables
DB_USER             = os.getenv("mysql_username")
DB_PW               = os.getenv("mysql_pw")
DB_HOST             = os.getenv("mysql_host")
DB_PORT             = os.getenv("mysql_port")
DB_DATABASE_NAME    = os.getenv("mysql_database")
DB_TABLE_NAME       = os.getenv("mysql_table_name")

# View the first few characters in the key
print(f"MYSQL_USER // MYSQL_PW: {DB_USER[:3]}//{DB_PW[:3]}...")


# ---------------------------------- Database Functions ----------------------------------
print_banner("Database Functions")

def get_sqlalchemy_engine():
    host = DB_HOST
    port = int(DB_PORT)
    db   = DB_DATABASE_NAME
    user = DB_USER
    pw   = DB_PW

    if not all([host, port, db, user, pw]):
        raise RuntimeError("Missing one or more required MYSQL_* env vars")

    # URL-encode special chars in password
    pw_enc = quote_plus(pw)
    url = f"mysql+pymysql://{user}:{pw_enc}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)

def ensure_database():
    """
    Create DB if it doesn't exist.
    """
    port = int(DB_PORT or 3306)
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=port, user=DB_USER, password=DB_PW
        )
        cur = conn.cursor()
        # Safely quote the DB name and pick a sane default charset/collation
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_DATABASE_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def write_df_to_mysql(df, table_name: str, if_exists: str = "replace", chunksize: int = 1000):
    # normalize NaN -> None so NULLs are stored
    df = df.where(pd.notnull(df), None)

    engine = get_sqlalchemy_engine()
    with engine.begin() as conn:
        df.to_sql(
            name=table_name,
            con=conn,
            if_exists=if_exists,
            index=False,
            chunksize=chunksize,
            method="multi",   # batched INSERTs
        )
    print(f"✅ Wrote {len(df):,} rows to `{table_name}`")

print("Database functions defined...")


# ---------------------------------- Push Data to DB ----------------------------------
print_banner("Push Data to DB")
df = pd.read_csv(file_path)

print(df.head())

ensure_database()
write_df_to_mysql(df, DB_TABLE_NAME)

