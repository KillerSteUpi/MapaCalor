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
# 2. CARGA Y LIMPIEZA DE DATOS
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = pd.read_json("mis_datos.json", orient="index")
        
        # BLINDAJE 1: Forzar que lat y lon sean números (ignora textos erróneos)
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        
        # BLINDAJE 2: Eliminar cualquier fila que no tenga coordenadas válidas
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
    centro_lat = df_datos['lat'].mean()
    centro_lon = df_datos['lon'].mean()
    
    # CORRECCIÓN DEL MAPA NEGRO: El string exacto es "cartodbdark_matter"
    mapa = folium.Map(
        location=[centro_lat, centro_lon], 
        zoom_start=11, 
        tiles="cartodbdark_matter" 
    )

    # ==========================================
    # 4. CAPAS DEL MAPA
    # ==========================================
    if modo_vista == "1. Radios de Influencia (Operativo)":
        st.sidebar.markdown("---")
        radio_metros = st.sidebar.slider("Ajustar radio (metros):", 50, 2000, 500, step=50)
        st.subheader(f"Zonas de cobertura a {radio_metros} metros")
        
        for _, row in df_datos.iterrows():
            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=radio_metros,
                color="#0096FF",
                fill=True,
                fill_color="#0096FF",
                fill_opacity=0.4,
                tooltip=f"Delegación: {row.get('delegacion', 'N/A')}"
            ).add_to(mapa)

    elif modo_vista == "2. Sectores Naturales (Huella Real)":
        st.subheader("Polígonos de operación real agrupados por Delegación")
        
        sectores = gdf_datos.dissolve(by='delegacion')
        sectores['geometry'] = sectores.geometry.convex_hull
        
        # BLINDAJE 3: Solo dibujar delegaciones que sí formaron un polígono (min 3 puntos)
        sectores_validos = sectores[sectores.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        
        if not sectores_validos.empty:
            folium.GeoJson(
                sectores_validos,
                style_function=lambda x: {
                    'fillColor': '#FF6400',
                    'color': '#FFFFFF',
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Delegación:'])
            ).add_to(mapa)
        else:
            st.warning("No hay suficientes registros en las delegaciones para formar polígonos cerrados.")

    elif modo_vista == "3. Mapa de Calor (Densidad)":
        st.subheader("Concentración de registros")
        
        # BLINDAJE 4: Evitar el IndexError asegurando que la lista tenga datos válidos
        datos_calor = [[row['lat'], row['lon']] for index, row in df_datos.iterrows() if pd.notna(row['lat']) and pd.notna(row['lon'])]
        
        if len(datos_calor) > 0:
            HeatMap(datos_calor, radius=15, blur=10).add_to(mapa)
        else:
            st.warning("No hay coordenadas válidas para generar el mapa de calor.")

    # ==========================================
    # 5. RENDERIZADO DEL MAPA
    # ==========================================
    st_folium(mapa, width=1200, height=600, returned_objects=[])

    st.markdown("### Resumen Ejecutivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Registros Válidos", len(df_datos))
    if 'max' in df_datos.columns:
        col2.metric("Presión Máx. Promedio", round(df_datos['max'].mean(), 3))
    col3.metric("Delegaciones Activas", df_datos['delegacion'].nunique())