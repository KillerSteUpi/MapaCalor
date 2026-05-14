import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from shapely.ops import voronoi_diagram
import folium
from folium.plugins import HeatMap, MarkerCluster, Search
from streamlit_folium import st_folium
import json
import os

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="Tablero Territorial CDMX", layout="wide")
st.title("📍 Sistema de Inteligencia Territorial")
st.markdown("---")

# ==========================================
# 2. CARGA Y LIMPIEZA DE DATOS
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = pd.read_json("mis_datos.json", orient="index")
        if df.empty: return pd.DataFrame(), gpd.GeoDataFrame()

        # El 'nombre_sitio' es nuestra clave para buscar calles/referencias
        df['nombre_sitio'] = df.index.astype(str).str.replace("_", " ")
        
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        # Filtro de seguridad geográfica
        df = df[(df['lat'] > 19.0) & (df['lat'] < 19.8) & (df['lon'] > -99.6) & (df['lon'] < -98.8)]
        
        if df.empty: return pd.DataFrame(), gpd.GeoDataFrame()

        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
    except Exception as e:
        st.error(f"⚠️ Alerta: Error al leer base de datos. {e}")
        return pd.DataFrame(), gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()

if not df_datos.empty:
    st.sidebar.header("⚙️ Panel de Control")
    
    # ==========================================
    # NUEVO: BUSCADOR POR CALLE / COLONIA / COINCIDENCIA
    # ==========================================
    st.sidebar.markdown("### 🔍 Localizador por Calle o Colonia")
    # Este campo es la clave: busca cualquier palabra dentro del nombre descriptivo
    texto_filtro = st.sidebar.text_input("Escribe Calle, Colonia o Referencia:", placeholder="Ej: ZARAGOZA, VILLA, POZO...")
    
    lista_deleg = sorted(df_datos['delegacion'].dropna().unique())
    deleg_selec = st.sidebar.multiselect("Filtrar por Demarcación:", lista_deleg)
    
    # Lógica de Filtrado Inteligente
    df_f = df_datos.copy()
    if texto_filtro:
        # Buscamos la coincidencia en el nombre del sitio (que suele traer la calle/colonia)
        df_f = df_f[df_f['nombre_sitio'].str.contains(texto_filtro, case=False, na=False)]
    if deleg_selec:
        df_f = df_f[df_f['delegacion'].isin(deleg_selec)]

    st.sidebar.markdown("---")
    modo_vista = st.sidebar.radio(
        "Capa Operativa:",
        ["1. Clusters", "2. Radios", "3. Sectores", "4. Calor", "5. Voronoi"]
    )

    # ==========================================
    # 3. MAPA DINÁMICO
    # ==========================================
    c_lat, c_lon = (df_f['lat'].mean(), df_f['lon'].mean()) if not df_f.empty else (19.4326, -99.1332)
    mapa = folium.Map(location=[c_lat, c_lon], zoom_start=11, tiles="cartodbpositron")
    
    # Límites territoriales
    try:
        folium.GeoJson("perimetro_cdmx.json", name="CDMX", style_function=lambda x: {'color': '#2C3E50', 'weight': 2, 'dashArray': '5, 5'}).add_to(mapa)
    except: pass

    # Dibujado de puntos filtrados
    if not df_f.empty:
        if modo_vista == "1. Clusters":
            cluster = MarkerCluster().add_to(mapa)
            for i, r in df_f.iterrows():
                folium.Marker([r['lat'], r['lon']], tooltip=f"🏢 {r['nombre_sitio']}").add_to(cluster)
        
        elif modo_vista == "2. Radios":
            for i, r in df_f.iterrows():
                folium.Circle([r['lat'], r['lon']], radius=500, color="#0096FF", fill=True).add_to(mapa)
        
        elif modo_vista == "5. Voronoi":
            if len(df_f) > 3:
                puntos = MultiPoint([(r.lon, r.lat) for i, r in df_f.iterrows()])
                regiones = voronoi_diagram(puntos)
                folium.GeoJson(regiones, style_function=lambda x: {'fillColor': '#28B463', 'opacity': 0.2}).add_to(mapa)

    st_folium(mapa, width=1200, height=550)

    # ==========================================
    # 4. LISTADO DE RESULTADOS (SOLUCIÓN A TU PREGUNTA)
    # ==========================================
    st.markdown(f"### 📋 Listado de Sitios en '{texto_filtro if texto_filtro else 'Toda la Red'}'")
    if not df_f.empty:
        # Mostramos una tabla con los nombres reales para que los identifiquen
        st.write(f"Se encontraron **{len(df_f)}** puntos que coinciden con su búsqueda:")
        st.dataframe(df_f[['nombre_sitio', 'delegacion', 'max']].sort_values(by='nombre_sitio'), use_container_width=True)
    else:
        st.warning("No se encontraron puntos con esa referencia. Intenta con una palabra más corta (ej: en lugar de 'Avenida Insurgentes', busca solo 'Insurgentes').")

    # Resumen Ejecutivo
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Sitios Filtrados", len(df_f))
    if 'max' in df_f.columns:
        c2.metric("Presión Promedio", round(pd.to_numeric(df_f['max'], errors='coerce').mean(), 3))
    c3.metric("Demarcaciones", df_f['delegacion'].nunique())

else:
    st.info("💡 Cargue registros con coordenadas válidas para iniciar.")