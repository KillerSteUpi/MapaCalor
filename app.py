import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import json

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="Tablero Territorial CDMX", layout="wide")
st.title("📍 Sistema de Inteligencia Territorial")
st.markdown("---")

# ==========================================
# 2. CARGA DE DATOS
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = pd.read_json("mis_datos.json", orient="index")
        df = df.dropna(subset=['lat', 'lon'])
        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
    except Exception as e:
        st.error(f"⚠️ Error al leer datos: {e}")
        return pd.DataFrame(), gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()

if not df_datos.empty:
    st.sidebar.header("⚙️ Panel Directivo")
    modo_vista = st.sidebar.radio(
        "Selecciona la capa de análisis:",
        [
            "1. Radios de Influencia (Operativo)", 
            "2. Sectores Naturales (Huella Real)",
            "3. Mapa de Calor (Densidad)"
        ]
    )

    # ==========================================
    # 3. CREACIÓN DEL MAPA FOLIUM
    # ==========================================
    # Inicializamos el mapa centrado en tus datos con fondo oscuro nativo
    centro_lat = df_datos['lat'].mean()
    centro_lon = df_datos['lon'].mean()
    
    mapa = folium.Map(
        location=[centro_lat, centro_lon], 
        zoom_start=11, 
        tiles="CartoDB dark_matter" # Este es 100% libre y siempre funciona
    )

    # ==========================================
    # 4. CAPAS DEL MAPA
    # ==========================================
    if modo_vista == "1. Radios de Influencia (Operativo)":
        st.sidebar.markdown("---")
        radio_metros = st.sidebar.slider("Ajustar radio (metros):", 50, 2000, 500, step=50)
        st.subheader(f"Zonas de cobertura a {radio_metros} metros")
        
        # Dibujamos un círculo por cada punto
        for _, row in df_datos.iterrows():
            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=radio_metros,
                color="#0096FF", # Borde azul
                fill=True,
                fill_color="#0096FF",
                fill_opacity=0.4,
                tooltip=f"Delegación: {row.get('delegacion', 'N/A')}"
            ).add_to(mapa)

    elif modo_vista == "2. Sectores Naturales (Huella Real)":
        st.subheader("Polígonos de operación real agrupados por Delegación")
        
        sectores = gdf_datos.dissolve(by='delegacion')
        sectores['geometry'] = sectores.geometry.convex_hull
        
        # Agregamos los polígonos al mapa
        folium.GeoJson(
            sectores,
            style_function=lambda x: {
                'fillColor': '#FF6400', # Naranja
                'color': '#FFFFFF',     # Borde blanco
                'weight': 2,
                'fillOpacity': 0.4
            },
            tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Delegación:'])
        ).add_to(mapa)

    elif modo_vista == "3. Mapa de Calor (Densidad)":
        st.subheader("Concentración de registros")
        
        # Extraemos solo las coordenadas para el mapa de calor
        datos_calor = [[row['lat'], row['lon']] for index, row in df_datos.iterrows()]
        HeatMap(datos_calor, radius=15, blur=10).add_to(mapa)

    # ==========================================
    # 5. RENDERIZADO DEL MAPA
    # ==========================================
    # st_folium dibuja el mapa en Streamlit
    st_folium(mapa, width=1200, height=600, returned_objects=[])

    st.markdown("### Resumen Ejecutivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Registros", len(df_datos))
    if 'max' in df_datos.columns:
        col2.metric("Presión Máx. Promedio", round(df_datos['max'].mean(), 3))
    col3.metric("Delegaciones Activas", df_datos['delegacion'].nunique())