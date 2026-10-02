import pandas as pd
from database import get_engine
from external_gov_data import obtener_inflacion_leche_entera_inegi, obtener_precios_sniim_leche_entera

def guardar_tablas_filtradas_leche_entera():
    engine = get_engine()
    
    print("1. Guardando historico INEGI exclusivo de Leche Entera 1L...")
    df_inegi_leche = obtener_inflacion_leche_entera_inegi()
    df_inegi_leche.to_sql('inegi_leche_entera_3anos', con=engine, if_exists='replace', index=False)
    
    print("2. Guardando referencia oficial SNIIM de Leche Entera 1L...")
    df_sniim_leche = obtener_precios_sniim_leche_entera()
    df_sniim_leche.to_sql('sniim_leche_entera', con=engine, if_exists='replace', index=False)
    
    print("3. Creando vista/tabla filtrada de Leche Entera 1L de tu tienda...")
    query_tienda = "SELECT * FROM ventas_lacteos WHERE producto = 'Leche Entera 1L' ORDER BY fecha ASC"
    df_tienda_leche = pd.read_sql(query_tienda, con=engine)
    df_tienda_leche.to_sql('ventas_tienda_leche_entera_3anos', con=engine, if_exists='replace', index=False)
    
    print("¡Listo! Tablas exclusivas creadas en MySQL.")

if __name__ == '__main__':
    guardar_tablas_filtradas_leche_entera()
