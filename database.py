import os
from dotenv import load_dotenv
import pandas as pd
import pymssql

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER", "")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# List all tables in the connected database and return their names as a list
def list_tables():
    conn = pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM sys.tables')
    rows = cursor.fetchall() or []
    tables = [row[0] for row in rows]
    conn.close()
    return tables

# Preview the first n rows of a specified table as a pandas DataFrame
def preview_table(table_name, n=5):
    conn = pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )
    query = f"SELECT TOP {n} * FROM [{table_name}]"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Run any SQL query and return the result as a pandas DataFrame
def run_query(query, params=None):
    """
    Execute a SQL query and return results as DataFrame.
    
    Args:
        query: SQL query string (can include %s placeholders for params)
        params: Optional tuple of parameters for parameterized queries
    
    Example:
        run_query("SELECT * FROM UserProfile WHERE UserName = %s", ("TCube360",))
    """
    try:
        print(f"DEBUG: Attempting database connection to {DB_SERVER}:{DB_PORT}")
        conn = pymssql.connect(
            server=DB_SERVER,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        print(f"DEBUG: Database connection successful")
        
        if params:
            # Use parameterized query
            df = pd.read_sql(query, conn, params=params)
        else:
            # Regular query
            df = pd.read_sql(query, conn)
            
        conn.close()
        print(f"DEBUG: Query executed successfully, returned {len(df)} rows")
        return df
    except Exception as e:
        print(f"DEBUG: Database connection error: {e}")
        # Return empty DataFrame with error info
        return pd.DataFrame({"error": [str(e)]})

# Get the column names and data types for a specified table
def get_table_columns(table_name):
    conn = pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'")
    columns = cursor.fetchall()
    conn.close()
    return columns

if __name__ == "__main__":
    tables = list_tables() or []
    print("Tables in the database:")
    print(tables)

    # Test preview_table
    if 'Shipment' in tables:
        print(f"\nPreview of Shipment:")
        print(preview_table('Shipment'))
    else:
        print("'Shipment' table not found.")

    # Test get_table_columns
    if tables:
        print(f"\nColumns in {tables[0]}:")
        print(get_table_columns(tables[0]))

    # Test run_query
    if 'Shipment' in tables:
        print("\nRunning custom query on Shipment:")
        print(run_query('SELECT TOP 3 * FROM [Shipment]'))

