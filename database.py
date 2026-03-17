import pyodbc

def get_connection():
    try:
        conn_str = (
            'DRIVER={ODBC Driver 13 for SQL Server};'
            'SERVER=VCCS099143;' 
            'DATABASE=ProyectoUnicasa;'
            'UID=proyectounicasa;'            
            'PWD=12345;'
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"--- ERROR DE SQL ---: {e}") 
        return None