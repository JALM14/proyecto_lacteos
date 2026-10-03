# IMPORTACIÓN DE LIBRERÍAS DEL SISTEMA
import datetime
import hashlib
import io
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

# IMPORTACIÓN DE MÓDULOS LOCALES
from database import get_engine, cargar_datos_desde_bd
from external_gov_data import (
    obtener_inflacion_leche_entera_inegi,
    obtener_precios_sniim_leche_entera,
    analizar_iqr_merma,
    analizar_zscore_merma
)

# CONFIGURACIÓN DE STREAMLIT
st.set_page_config(page_title="TPV 1 - Abonares la Dinamita", layout="wide")

# ESTILOS CSS
st.markdown("""
<style>
    .banner-verde {
        background-color: #4CAF50;
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .stMetric {
        background-color: #1E222B;
        padding: 10px;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# VARIABLES DE SESIÓN
if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = False
if "datos_usuario" not in st.session_state:
    st.session_state.datos_usuario = None
if "ticket" not in st.session_state:
    st.session_state.ticket = {}

# CONEXIÓN A BASE DE DATOS
engine = get_engine()

# FUNCIONES DE AUTENTICACIÓN
def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def validar_credenciales(username, password):
    h = hash_pass(password)
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT username, nombre_completo, rol FROM usuarios WHERE username = :u AND password_hash = :p"),
            {"u": username, "p": h}
        ).fetchone()
        if res:
            return {"username": res[0], "nombre": res[1], "rol": res[2]}
    return None

# ==============================================================================
# 1. PANTALLA DE INICIO DE SESIÓN
# ==============================================================================
if not st.session_state.usuario_autenticado:
    col_izq, col_centro, col_der = st.columns([1, 1.4, 1])
    with col_centro:
        st.markdown('<div class="banner-verde" style="text-align: center;">🔐 TPV • INICIAR SESIÓN</div>', unsafe_allow_html=True)
        st.markdown("### Acceso al sistema del departamento de lácteos")
        
        with st.form("form_login"):
            user_input = st.text_input("Username:", placeholder="Ej. cajero, gerente, admin o superadmin")
            pass_input = st.text_input("Contraseña:", type="password")
            btn_login = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
            
            if btn_login:
                usuario_valido = validar_credenciales(user_input.strip(), pass_input.strip())
                if usuario_valido:
                    st.session_state.usuario_autenticado = True
                    st.session_state.datos_usuario = usuario_valido
                    st.success(f"Bienvenido, {usuario_valido['nombre']}")
                    st.rerun()
                else:
                    st.error("Username o contraseña incorrectos.")
        st.caption("¡Bienvenid@! List@ para un gran día de trabajo")

# ==============================================================================
# 2. SISTEMA PRINCIPAL AUTENTICADO
# ==============================================================================
else:
    user_info = st.session_state.datos_usuario
    rol = user_info['rol']

    # Barra lateral
    st.sidebar.markdown(f"### 👤 {user_info['nombre']}")
    st.sidebar.markdown(f"**Username:** `{user_info['username']}`")
    st.sidebar.markdown(f"**ROL:** `{rol}`")
    st.sidebar.markdown("**PROYECTO TPV** \n *EQUIPO DINAMITA* \n 'VERSIÓN 3.18'")
    
    if st.sidebar.button("🚪 Cerrar sesión", type="secondary"):
        st.session_state.usuario_autenticado = False
        st.session_state.datos_usuario = None
        st.session_state.ticket = {}
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Navegación")

    # MATRIZ DE PERMISOS 
    modulos_posibles = {
        "Ventas": ["Cajero", "Gerente", "Admin", "Admin", "Super Admin"],
        "Recibidos": ["Cajero", "Gerente", "Admin", "Admin", "Super Admin"],
        "Turno": ["Cajero", "Gerente", "Admin", "Admin", "Super Admin"],
        "Artículos": ["Gerente", "Admin", "Admin", "Super Admin"],
        "📊 Dashboard & Ciencia de Datos": [ "Admin",  "Super Admin"],
        "👥 Registrar Usuarios": ["Super Admin"]
    }

    modulos_autorizados = [mod for mod, roles in modulos_posibles.items() if rol in roles]
    menu = st.sidebar.radio("Secciones disponibles:", modulos_autorizados)

    st.sidebar.markdown("---")
    st.sidebar.caption("Proyecto de Ciencia de Datos • Lácteos")

    # --------------------------------------------------------------------------
    # MÓDULO: VENTAS
    # --------------------------------------------------------------------------
    if menu == "Ventas":
        st.markdown('<div class="banner-verde">🛒 Ticket • Cobro en tienda</div>', unsafe_allow_html=True)
        col_prod, col_ticket = st.columns([1.6, 1.2])
        
        with col_prod:
            buscar = st.text_input("🔍 Buscar artículo:", placeholder="Escribe el nombre del lácteo...")
            df_art = pd.read_sql("SELECT * FROM articulos", con=engine)
            
            if buscar:
                df_art = df_art[df_art['nombre'].str.contains(buscar, case=False)]
                
            for _, row in df_art.iterrows():
                c1, c2, c3 = st.columns([3, 1.5, 1])
                with c1:
                    st.markdown(f"**{row['nombre']}** \n<small style='color:gray;'>{row['inventario']} pzas disponibles</small>", unsafe_allow_html=True)
                with c2:
                    st.write(f"**{row['precio']:.2f} $**")
                with c3:
                    if st.button("➕", key=f"add_{row['id']}"):
                        if row['inventario'] > 0:
                            st.session_state.ticket[row['nombre']] = st.session_state.ticket.get(row['nombre'], 0) + 1
                        else:
                            st.warning("Sin stock")
                st.divider()

        with col_ticket:
            st.subheader("Detalle del Ticket")
            if not st.session_state.ticket:
                st.info("El ticket está vacío.")
            else:
                total_monto = 0.0
                items_resumen = []
                for item, cant in list(st.session_state.ticket.items()):
                    p = float(df_art[df_art['nombre'] == item]['precio'].values[0])
                    subtotal = cant * p
                    total_monto += subtotal
                    items_resumen.append(f"{item} ({cant})")
                    
                    t1, t2, t3 = st.columns([2.5, 1, 1])
                    t1.write(f"{item} x{cant}")
                    t2.write(f"${subtotal:.2f}")
                    if t3.button("❌", key=f"del_{item}"):
                        del st.session_state.ticket[item]
                        st.rerun()
                        
                st.markdown(f"### Total: ${total_monto:.2f}")
                metodo = st.selectbox("Método de Pago:", ["Efectivo", "Tarjeta"])
                
                if st.button("Cobrar e Imprimir Recibo", type="primary"):
                    folio = f"#{datetime.datetime.now().strftime('%m%d%H%M%S')}"
                    resumen_txt = ", ".join(items_resumen)
                    now = datetime.datetime.now()
                    
                    with engine.begin() as conn:
                        conn.execute(
                            text("INSERT INTO recibos (folio, fecha_hora, monto, metodo, articulos_vendidos, cajero) VALUES (:f, :fh, :m, :met, :art, :c)"),
                            {"f": folio, "fh": now, "m": total_monto, "met": metodo, "art": resumen_txt, "c": user_info['nombre']}
                        )
                        for item, cant in st.session_state.ticket.items():
                            conn.execute(
                                text("UPDATE articulos SET inventario = inventario - :cant WHERE nombre = :n"),
                                {"cant": cant, "n": item}
                            )
                    st.session_state.ticket = {}
                    st.success(f"Venta guardada con folio {folio}")
                    st.rerun()

    # --------------------------------------------------------------------------
    # MÓDULO: RECIBIDOS
    # --------------------------------------------------------------------------
    elif menu == "Recibidos":
        st.markdown('<div class="banner-verde">📑 Recibos emitidos</div>', unsafe_allow_html=True)
        st.markdown("### 🔍 Filtrar Recibos")
        df_rec = pd.read_sql("SELECT folio as 'Folio', fecha_hora as 'Fecha y Hora', monto as 'Monto ($)', metodo as 'Método', articulos_vendidos as 'Artículos vendidos', cajero as 'Atendió' FROM recibos ORDER BY fecha_hora DESC", con=engine)
        if df_rec.empty:
            st.info("No hay recibos registrados aún.")
        else:
            st.caption(f"Mostrando {len(df_rec)} recibos encontrados.")
            st.dataframe(df_rec, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # MÓDULO: TURNO
    # --------------------------------------------------------------------------
    elif menu == "Turno":
        st.markdown('<div class="banner-verde">⏰ Control de turno y caja</div>', unsafe_allow_html=True)
        df_turno = pd.read_sql("SELECT * FROM turnos WHERE estado = 'ABIERTO' ORDER BY id DESC LIMIT 1", con=engine)
        
        if df_turno.empty:
            st.subheader("Abrir Turno")
            monto_ini = st.number_input("Monto Inicial en Caja ($MXN):", min_value=0.0, value=500.0, step=50.0)
            if st.button("Abrir Turno", type="primary"):
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO turnos (usuario, fecha_apertura, monto_inicial, estado) VALUES (:u, :fa, :m, 'ABIERTO')"),
                        {"u": user_info['nombre'], "fa": datetime.datetime.now(), "m": monto_ini}
                    )
                st.success("Turno abierto exitosamente.")
                st.rerun()
        else:
            turno_actual = df_turno.iloc[0]
            st.info(f"Turno activo iniciado por **{turno_actual['usuario']}** el {turno_actual['fecha_apertura']}.")
            
            df_ventas_turno = pd.read_sql(
                text("SELECT SUM(monto) as total FROM recibos WHERE fecha_hora >= :fa"),
                con=engine,
                params={"fa": turno_actual['fecha_apertura']}
            )
            total_acumulado = df_ventas_turno['total'].values[0] or 0.0
            
            c1, c2 = st.columns(2)
            c1.metric("Fondo Inicial", f"${turno_actual['monto_inicial']:.2f}")
            c2.metric("Ventas Acumuladas", f"${total_acumulado:.2f}")
            
            st.markdown("---")
            st.subheader("Cierre de Turno")
            monto_real_caja = st.number_input("Efectivo contado al cierre ($MXN):", min_value=0.0, step=50.0)
            if st.button("Cerrar Turno Definitivamente"):
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE turnos SET fecha_cierre = :fc, monto_final = :mf, total_ventas = :tv, estado = 'CERRADO' WHERE id = :id"),
                        {"fc": datetime.datetime.now(), "mf": monto_real_caja, "tv": total_acumulado, "id": int(turno_actual['id'])}
                    )
                st.success("Turno cerrado con éxito.")
                st.rerun()

    # --------------------------------------------------------------------------
    # MÓDULO: ARTÍCULOS
    # --------------------------------------------------------------------------
    elif menu == "Artículos":
        st.markdown('<div class="banner-verde">📦 Artículos • Departamento de lácteos</div>', unsafe_allow_html=True)
        tab_list, tab_create = st.tabs(["📋 Lista de artículos", "➕ Crear Artículo"])
        
        with tab_list:
            df_art = pd.read_sql("SELECT nombre as 'Artículo', precio as 'Precio Venta ($)', costo as 'Coste ($)', inventario as 'Inventario Actual' FROM articulos", con=engine)
            st.dataframe(df_art, use_container_width=True, hide_index=True)
            
        with tab_create:
            st.subheader("Registrar Nuevo Producto")
            with st.form("form_crear_art"):
                nombre_art = st.text_input("Nombre del producto:")
                precio_v = st.number_input("Precio de venta ($):", min_value=0.0, step=0.5)
                coste_v = st.number_input("Costo de compra ($):", min_value=0.0, step=0.5)
                stock_ini = st.number_input("Inventario inicial (pzas):", min_value=0, step=1)
                submit = st.form_submit_button("Guardar en Catálogo")
                
                if submit and nombre_art:
                    try:
                        with engine.begin() as conn:
                            conn.execute(
                                text("INSERT INTO articulos (nombre, precio, costo, inventario) VALUES (:n, :p, :c, :i)"),
                                {"n": nombre_art, "p": precio_v, "c": coste_v, "i": stock_ini}
                            )
                        st.success(f"Artículo '{nombre_art}' registrado exitosamente.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error al guardar: {ex}")

    # --------------------------------------------------------------------------
    # MÓDULO: REGISTRAR USUARIOS 
    # --------------------------------------------------------------------------
    elif menu == "👥 Registrar Usuarios":
        if rol != "Super Admin":
            st.error("⚠️ Acceso denegado. Solo el Super Admin puede registrar usuarios.")
            st.stop()

        st.markdown('<div class="banner-verde">👥 Administración de Usuarios</div>', unsafe_allow_html=True)
        st.subheader("Registrar nuevo usuario")
        st.info("El Super Admin puede registrar las cuentas que tendrán acceso al sistema y asignarles el rol correspondiente.")

        with st.form("form_registrar_usuario", clear_on_submit=True):
            username_nuevo = st.text_input("Username:", placeholder="Ej. cajero2")
            password_nueva = st.text_input("Contraseña:", type="password", placeholder="Ingresa una contraseña")
            nombre_nuevo = st.text_input("Nombre completo:", placeholder="Nombre y apellidos")
            edad_nueva = st.number_input("Edad:", min_value=18, max_value=100, value=18, step=1)
            genero_nuevo = st.selectbox("Género:", ["Masculino", "Femenino", "Otro"])
            correo_nuevo = st.text_input("Correo electrónico:", placeholder="correo@ejemplo.com")
            rol_nuevo = st.selectbox("Rol del usuario:", ["Cajero", "Gerente", "Admin", "Propietario"])
            boton_registrar = st.form_submit_button("👤 Registrar Usuario", type="primary", use_container_width=True)

            if boton_registrar:
                u_limpio = username_nuevo.strip()
                p_limpia = password_nueva.strip()
                n_limpio = nombre_nuevo.strip()
                c_limpio = correo_nuevo.strip()

                if not u_limpio or not p_limpia or not n_limpio or not c_limpio:
                    st.warning("Todos los campos son obligatorios.")
                elif "@" not in c_limpio:
                    st.warning("Ingresa un correo electrónico válido.")
                else:
                    try:
                        with engine.connect() as conn:
                            user_ex = conn.execute(
                                text("SELECT id FROM usuarios WHERE username = :u"),
                                {"u": u_limpio}
                            ).fetchone()

                        if user_ex:
                            st.error(f"El username '{u_limpio}' ya está registrado.")
                        else:
                            p_hash = hash_pass(p_limpia)
                            with engine.begin() as conn:
                                conn.execute(
                                    text("INSERT INTO usuarios (username, password_hash, nombre_completo, rol, edad, genero, correo_electronico) VALUES (:u, :p, :n, :r, :e, :g, :c)"),
                                    {"u": u_limpio, "p": p_hash, "n": n_limpio, "r": rol_nuevo, "e": int(edad_nueva), "g": genero_nuevo, "c": c_limpio}
                                )
                            st.success(f"✅ Usuario '{u_limpio}' registrado correctamente con el rol '{rol_nuevo}'.")
                    except Exception as ex:
                        st.error(f"Error al registrar usuario: {ex}")

    # --------------------------------------------------------------------------
    # MÓDULO: DASHBOARD & CIENCIA DE DATOS 
    # --------------------------------------------------------------------------
    elif menu == "📊 Dashboard & Ciencia de Datos":
        if rol not in ["Gerente", "Admin", "Propietario", "Super Admin"]:
            st.error("⚠️ Acceso denegado. Este módulo analítico está reservado para Administradores, Propietarios o Super Admin.")
        else:
            st.markdown('<div class="banner-verde">📊 Dashboard & Ciencia de Datos • Analítica y Comparativa Oficial</div>', unsafe_allow_html=True)
            
            df_bi = cargar_datos_desde_bd()
            if df_bi.empty:
                st.warning("⚠️ No hay registros en 'ventas_lacteos'. Asegúrate de haber ejecutado 'seed_data.py'.")
            else:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    prod_sel = st.selectbox("Filtrar por Producto en Panel General:", ["Todos"] + sorted(list(df_bi['producto'].unique())))
                with col_f2:
                    fecha_min = df_bi['fecha'].min().date()
                    fecha_max = df_bi['fecha'].max().date()
                    fechas = st.date_input("Rango de Fechas del Análisis:", [fecha_min, fecha_max])
                    
                df_filtrado = df_bi.copy()
                if prod_sel != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['producto'] == prod_sel]
                if len(fechas) == 2:
                    df_filtrado = df_filtrado[(df_filtrado['fecha'].dt.date >= fechas[0]) & (df_filtrado['fecha'].dt.date <= fechas[1])]

                tab_interna, tab_comparativa, tab_merma_stats, tab_dist, tab_export = st.tabs([
                    "🏪 Rendimiento de Tienda", 
                    "🥛 Leche Entera 1L (INEGI & SNIIM)", 
                    "⚠️ Análisis Estadístico Merma (IQR & Z-Score)",
                    "📈 Distribución y Dispersión", 
                    "💾 Descargas (CSV / Excel)"
                ])

                with tab_interna:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Ingresos Totales", f"${df_filtrado['ingreso_total'].sum():,.2f}")
                    k2.metric("Ganancia Neta", f"${df_filtrado['ganancia'].sum():,.2f}")
                    k3.metric("Pérdidas Merma", f"${df_filtrado['perdida_merma'].sum():,.2f}")
                    k4.metric("Unidades Faltantes", f"{df_filtrado['faltantes'].sum():,}")

                    st.markdown("---")
                    g1, g2 = st.columns(2)
                    with g1:
                        st.subheader("Ingresos por Producto (Barras)")
                        ventas_p = df_filtrado.groupby('producto')['ingreso_total'].sum().reset_index()
                        fig_bar = px.bar(ventas_p, x='producto', y='ingreso_total', color='ingreso_total', color_continuous_scale='Greens')
                        fig_bar.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig_bar, use_container_width=True)

                    with g2:
                        st.subheader("Margen de Ganancia (Pastel)")
                        gan_p = df_filtrado.groupby('producto')['ganancia'].sum().reset_index()
                        gan_p = gan_p[gan_p['ganancia'] > 0]
                        fig_pie = px.pie(gan_p, values='ganancia', names='producto', hole=0.4)
                        st.plotly_chart(fig_pie, use_container_width=True)

                with tab_comparativa:
                    st.subheader("🥛 Análisis Especializado: Leche Entera 1L frente a Fuentes Oficiales")
                    st.caption("Contraste del precio y evolución de ventas de 'Leche Entera 1L' frente a los precios de la Secretaría de Economía (SNIIM) y la inflación del INEGI.")
                    
                    df_sniim_leche = obtener_precios_sniim_leche_entera()
                    precio_prom_tienda = df_bi[df_bi['producto'] == 'Leche Entera 1L']['precio_unitario'].mean()
                    
                    c_sniim1, c_sniim2 = st.columns([1.2, 2])
                    with c_sniim1:
                        st.write("**Referencia Oficial de Precios (SNIIM):**")
                        st.dataframe(df_sniim_leche, use_container_width=True)
                    
                    with c_sniim2:
                        df_bar_comp = pd.DataFrame([
                            {"Indicador": "Mínimo Oficial SNIIM", "Precio ($MXN)": df_sniim_leche['Precio_Min_MXN'].iloc[0]},
                            {"Indicador": "Promedio Tu Tienda", "Precio ($MXN)": round(precio_prom_tienda, 2)},
                            {"Indicador": "Máximo Oficial SNIIM", "Precio ($MXN)": df_sniim_leche['Precio_Max_MXN'].iloc[0]}
                        ])
                        fig_sniim = px.bar(df_bar_comp, x="Indicador", y="Precio ($MXN)", color="Indicador", color_discrete_sequence=["#6baed6", "#2ca02c", "#fd8d3c"], title="Precio Leche Entera 1L: Tienda vs. Rango SNIIM")
                        st.plotly_chart(fig_sniim, use_container_width=True)

                with tab_merma_stats:
                    st.subheader("⚠️ Análisis estadístico avanzado Detección de anomalías de pérdida por merma")
                    st.caption("Criterio operativo: Los valores normales de merma son 0.00; cualquier registro superior a 0.00 se cataloga como evento atípico o incidencia a vigilar.")
                    
                    res_iqr = analizar_iqr_merma(df_filtrado)
                    df_outliers_z = analizar_zscore_merma(df_filtrado, umbral=2)
                    
                    if res_iqr:
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Q1 (25% Merma)", f"{res_iqr['Q1']:.2f}")
                        m2.metric("Q3 (75% Merma)", f"{res_iqr['Q3']:.2f}")
                        m3.metric("IQR (Rango Intercuartil)", f"{res_iqr['IQR']:.2f}")
                        m4.metric("Incidencias con Merma > $0", f"{res_iqr['total_con_merma']:,}")
                        
                        st.markdown("---")
                        col_est1, col_est2 = st.columns(2)
                        with col_est1:
                            st.markdown("#### 📐 Parámetros estadísticos IQR")
                            st.success(f"* **Límite Inferior:** `{res_iqr['Limite_Inferior']:.2f}`\n* **Límite Superior:** `{res_iqr['Limite_Superior']:.2f}`\n* **Total Registros Evaluados:** `{res_iqr['total_analizados']:,}`\n* **Eventos Atípicos Detectados:** `{len(res_iqr['df_outliers']):,}`")
                            
                        with col_est2:
                            st.markdown("#### 📊 Parámetros Z-Score (|Z| > 2)")
                            st.success(f"* **Criterio de Desviación:** `Z > 2.0`\n* **Anomalías Críticas Detectadas:** `{len(df_outliers_z):,}`\n* **Estado del Módulo:** `Activo e Interactivo`")
                            
                        st.markdown("---")
                        st.markdown("### 📈 Visualización avanzada de anomalías de merma")
                        st.caption("Gráfico interactivo de dispersión: Muestra la magnitud de la pérdida por merma en el tiempo. Desglosada por producto.")
                    
                        if not res_iqr['df_outliers'].empty:
                            fig_scatter = px.scatter(
                                res_iqr['df_outliers'], x="fecha", y="perdida_merma", color="producto", size="perdida_merma",
                                hover_data=["faltantes", "ingreso_total"], labels={"fecha": "Fecha del registro", "perdida_merma": "Pérdida por merma", "producto": "Lácteo"},
                                title="Magnitud y distribución temporal de pérdidas por merma (> 0.00)"
                            )
                            fig_scatter.update_layout(plot_bgcolor="#1E222B", paper_bgcolor="#0E1117", font_color="white", xaxis_tickangle=-30, height=450)
                            st.plotly_chart(fig_scatter, use_container_width=True)
                        else:
                            st.info("No hay incidencias de merma mayores a cero para graficar en este rango.")

                        st.markdown("---")
                        st.markdown("### 📋 Tabla interactiva de registros con anomalías de merma")
                        if not res_iqr['df_outliers'].empty:
                            df_tabla_mostrar = res_iqr['df_outliers'][['fecha', 'producto', 'perdida_merma', 'faltantes', 'ingreso_total']].copy()
                            df_tabla_mostrar.columns = ['Fecha', 'Producto', 'Pérdida merma', 'Unidades faltantes', 'Ingreso total']
                            st.dataframe(df_tabla_mostrar, use_container_width=True, hide_index=True)
                        else:
                            st.info("No se registraron pérdidas por merma mayores a cero en el filtro seleccionado.")
                    else:
                        st.info("No hay suficientes datos de pérdida por merma en el rango seleccionado.")

                with tab_dist:
                    st.subheader("Análisis de distribución")
                    d1, d2 = st.columns(2)
                    with d1:
                        fig_h = px.histogram(df_filtrado, x="cantidad_vendida", nbins=20, marginal="box", color_discrete_sequence=['#4CAF50'], title="Histograma de ventas diarias")
                        st.plotly_chart(fig_h, use_container_width=True)
                    with d2:
                        fig_b = px.box(df_filtrado, x="producto", y="ganancia", color_discrete_sequence=['#2E7D32'], title="Detección de valores atípicos")
                        fig_b.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig_b, use_container_width=True)

                with tab_export:
                    st.subheader("Exportación de datos")
                    col_c, col_e = st.columns(2)
                    csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
                    col_c.download_button("📥 Descargar CSV", data=csv_data, file_name="analisis_lacteos.csv", mime="text/csv")
                    
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        df_filtrado.to_excel(writer, index=False, sheet_name='Lácteos')
                    buf.seek(0)
                    col_e.download_button("📊 Descargar Excel (.xlsx)", data=buf, file_name="analisis_lacteos.xlsx")