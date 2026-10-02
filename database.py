from sqlalchemy import create_engine
import pandas as pd

# Parámetros por defecto de Laragon (usuario 'root' y sin contraseña)
DB_USER = "root"
DB_PASS = ""
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "tienda_lacteos_db"

def get_engine():
    connection_url = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(connection_url)

def cargar_datos_desde_bd():
    engine = get_engine()
    query = "SELECT * FROM ventas_lacteos ORDER BY fecha ASC"
    df = pd.read_sql(query, con=engine)
    if not df.empty and 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'])
    return df

def guardar_datos_en_bd(df: pd.DataFrame):
    engine = get_engine()
    df.to_sql('ventas_lacteos', con=engine, if_exists='append', index=False)
