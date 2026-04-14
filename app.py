import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import json

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="Tablero Territorial CDMX", layout="wide")
st.title("📍 Sistema de Inteligencia Territorial")
st.markdown("---")

# ==========================================
# 2. CARGA Y LIMPIEZA DE DATOS (BLINDAJE OPERATIVO)
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = pd.read_json("mis_datos.json", orient="index")
        
        # Blindaje 1: Forzar números y quitar nulos
        df['lat'] = pd.to_numeric(df.get('lat'), errors='coerce')
        df['lon'] = pd.to_numeric(df.get('lon'), errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        # Blindaje 2: Caja Geográfica (Solo Zona Metropolitana)
        df = df[(df['lat'] > 19.0) & (df['lat'] < 19.8) & (df['lon'] > -99.6) & (df['lon'] < -98.8)]
        
        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
    except Exception as e:
        st.error(f"⚠️ Error al leer el archivo de datos: {e}")
        return pd.DataFrame(), gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()

if not df_datos.empty:
    st.sidebar.header("⚙️ Panel Directivo")
    modo_vista = st.sidebar.radio(
        "Selecciona la capa de análisis:",
        [
            "1. Agrupación Dinámica (Clusters)", 
            "2. Radios de Influencia (Operativo)", 
            "3. Sectores Naturales (Huella Real)",
            "4. Mapa de Calor (Densidad)"
        ]
    )

    # ==========================================
    # 3. INICIALIZACIÓN DEL MAPA (BLANCO / POSITRON)
    # ==========================================
    centro_lat = df_datos['lat'].mean()
    centro_lon = df_datos['lon'].mean()
    
    # CAMBIO A MAPA BLANCO: Usamos cartodbpositron
    mapa = folium.Map(
        location=[centro_lat, centro_lon], 
        zoom_start=10, 
        tiles="cartodbpositron" 
    )

    # ==========================================
    # 4. RENDERIZADO DE CAPAS SEGÚN SELECCIÓN
    # ==========================================
    
    if modo_vista == "1. Agrupación Dinámica (Clusters)":
        st.subheader("Puntos agrupados por concentración territorial")
        cluster = MarkerCluster().add_to(mapa)
        
        for index, row in df_datos.iterrows():
            nombre_sitio = str(index).replace("_", " ")
            # Usamos row.get() para evitar KeyError si las columnas no existen
            folium.Marker(
                location=[row['lat'], row['lon']],
                tooltip=f"🏢 Sitio: {nombre_sitio} | 📍 Delegación: {row.get('delegacion', 'N/A')} | 📊 Min: {row.get('min', '-')} Max: {row.get('max', '-')}"
            ).add_to(cluster)

    elif modo_vista == "2. Radios de Influencia (Operativo)":
        st.sidebar.markdown("---")
        radio_metros = st.sidebar.slider("Ajustar radio (metros):", 50, 2000, 500, step=50)
        st.subheader(f"Zonas de cobertura a {radio_metros} metros")
        
        for index, row in df_datos.iterrows():
            nombre_sitio = str(index).replace("_", " ")
            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=radio_metros,
                color="#0096FF",
                fill=True,
                fill_color="#0096FF",
                fill_opacity=0.4,
                tooltip=f"🏢 Sitio: {nombre_sitio} | 📍 Delegación: {row.get('delegacion', 'N/A')}"
            ).add_to(mapa)

    elif modo_vista == "3. Sectores Naturales (Huella Real)":
        st.subheader("Polígonos de operación real agrupados por Delegación")
        
        sectores = gdf_datos.dissolve(by='delegacion')
        sectores['geometry'] = sectores.geometry.convex_hull
        sectores_validos = sectores[sectores.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        
        if not sectores_validos.empty:
            folium.GeoJson(
                sectores_validos,
                style_function=lambda x: {
                    'fillColor': '#FF6400',
                    'color': '#FF6400', # Borde naranja en lugar de blanco para que resalte en el mapa claro
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Delegación:'])
            ).add_to(mapa)
        else:
            st.warning("No hay suficientes registros bien agrupados para trazar sectores poligonales.")

    elif modo_vista == "4. Mapa de Calor (Densidad)":
        st.subheader("Concentración histórica de registros")
        datos_calor = [[row['lat'], row['lon']] for index, row in df_datos.iterrows() if pd.notna(row['lat']) and pd.notna(row['lon'])]
        if len(datos_calor) > 0:
            HeatMap(datos_calor, radius=15, blur=10).add_to(mapa)

    # ==========================================
    # 5. DESPLIEGUE DEL MAPA Y MÉTRICAS
    # ==========================================
    st_folium(mapa, width=1200, height=600, returned_objects=[])

    st.markdown("### Resumen Ejecutivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Registros Operativos (Zona Centro)", len(df_datos))
    
    # BLINDAJE FINAL CONTRA KEYERROR:
    # Solo calcula si la columna existe y tiene datos numéricos válidos
    if 'max' in df_datos.columns:
        max_limpio = pd.to_numeric(df_datos['max'], errors='coerce')
        col2.metric("Presión Máx. Promedio", round(max_limpio.mean(), 3))
    else:
        col2.metric("Presión Máx. Promedio", "N/A (Sin datos)")
        
    if 'delegacion' in df_datos.columns:
        col3.metric("Delegaciones Activas", df_datos['delegacion'].nunique())
    else:
        col3.metric("Delegaciones Activas", "N/A")