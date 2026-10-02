# Importar librerias para manipulacion numerica, fechas y conexion a MySQL
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from database import guardar_datos_en_bd, get_engine
from sqlalchemy import text

def generar_dataset_3_anos():
    """
    Genera y almacena registros diarios de ventas, faltantes, mermas
    y gastos para 12 productos lacteos a lo largo de 3 anos (1,095 dias).
    """
    print("Limpiando tabla 'ventas_lacteos' previa...")
    # Limpiar tabla para evitar duplicados si ya teniamos datos de 3 meses
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE ventas_lacteos"))

    print("Generando dataset historico de 3 anos (esto puede tardar unos segundos)...")
    
    # Fijar semilla para garantizar reproducibilidad en las pruebas
    np.random.seed(42)
    
    # Catalogo base: (Nombre del producto, Costo base inicial, Precio base inicial)
    productos = [
        ("Leche Entera 1L", 16.0, 22.0),
        ("Leche Deslactosada 1L", 17.5, 24.5),
        ("Leche Semidescremada 1L", 16.5, 23.0),
        ("Yogurt Natural 1kg", 25.0, 36.0),
        ("Yogurt Fresa 1kg", 26.0, 38.0),
        ("Queso Panela 400g", 38.0, 54.0),
        ("Queso Oaxaca 400g", 44.0, 64.0),
        ("Queso Manchego 400g", 48.0, 70.0),
        ("Crema Entera 450ml", 20.0, 29.0),
        ("Crema Acida 450ml", 19.0, 27.5),
        ("Mantequilla con Sal 90g", 12.0, 19.0),
        ("Mantequilla sin Sal 90g", 12.5, 20.0)
    ]
    
    # Total de dias en 3 anos (365 * 3 = 1095 dias)
    total_dias = 1095
    fecha_inicio = datetime.now() - timedelta(days=total_dias)
    filas = []
    
    # Iterar dia por dia a traves de los 3 anos
    for dia in range(total_dias + 1):
        fecha_actual = (fecha_inicio + timedelta(days=dia)).date()
        
        # Factor inflacionario suave: simula el incremento gradual de costos/precios cada ano (~5% anual)
        factor_inflacion = 1.0 + (dia / total_dias) * 0.16
        
        for prod, costo_base, precio_base in productos:
            # Ajuste de precios segun la progresion temporal
            costo = round(costo_base * factor_inflacion, 2)
            precio = round(precio_base * factor_inflacion, 2)
            
            # Simulacion estadistica de transacciones diarias
            unidades = int(np.random.poisson(lam=18))                                           # Distribucion de Poisson para demanda diaria
            faltantes = int(np.random.choice([0, 1, 2, 3], p=[0.75, 0.15, 0.07, 0.03]))         # Probabilidad de faltante en anaquel
            devoluciones = int(np.random.choice([0, 1, 2], p=[0.85, 0.12, 0.03]))              # Probabilidad de devolucion por empaque
            merma_unidades = int(np.random.choice([0, 1, 2], p=[0.80, 0.15, 0.05]))            # Merma por caducidad
            
            # Calculos financieros del dia
            ingreso_total = round(unidades * precio, 2)
            costo_total = round(unidades * costo, 2)
            perdida_merma = round(merma_unidades * costo, 2)
            gastos_op = round(np.random.uniform(5.0, 15.0), 2)
            ganancia = round(ingreso_total - costo_total - perdida_merma - gastos_op, 2)
            
            # Agregar registro a la lista
            filas.append({
                "fecha": fecha_actual,
                "producto": prod,
                "categoria": "Lacteos",
                "cantidad_vendida": unidades,
                "precio_unitario": precio,
                "costo_unitario": costo,
                "ingreso_total": ingreso_total,
                "costo_total": costo_total,
                "ganancia": ganancia,
                "perdida_merma": perdida_merma,
                "faltantes": faltantes,
                "devoluciones": devoluciones,
                "gastos_operativos": gastos_op
            })
            
    # Convertir a DataFrame de Pandas e insertar por bloques en MySQL
    df = pd.DataFrame(filas)
    guardar_datos_en_bd(df)
    print(f"Exito: Se insertaron {len(df):,} registros historicos correspondientes a 3 anos en MySQL.")

# Bloque de ejecucion principal
if __name__ == "__main__":
    generar_dataset_3_anos()