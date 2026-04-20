import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap, MarkerCluster, Search
from streamlit_folium import st_folium
import json
import os

# ==========================================
# 1. CONFIGURACIÓN DE LA PLATAFORMA
# ==========================================
st.set_page_config(page_title="Tablero Territorial CDMX", layout="wide")
st.title("📍 Sistema de Inteligencia Territorial")
st.markdown("---")

# ==========================================
# 2. MOTOR DE CARGA Y LIMPIEZA (ESCUDO ANTIFALLAS)
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        # Verificamos si el archivo existe antes de abrirlo
        if not os.path.exists("mis_datos.json"):
            return pd.DataFrame(), gpd.GeoDataFrame()
            
        df = pd.read_json("mis_datos.json", orient="index")
        if df.empty: return pd.DataFrame(), gpd.GeoDataFrame()

        # Limpieza de nombres para el buscador
        df['nombre_sitio'] = df.index.astype(str).str.replace("_", " ")
        
        # Aseguramos existencia de columnas de coordenadas
        if 'lat' not in df.columns: df['lat'] = None
        if 'lon' not in df.columns: df['lon'] = None
            
        # Conversión numérica y limpieza de nulos
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        # Filtro Geográfico Metropolitano (Evita puntos fuera de zona)
        df = df[(df['lat'] > 19.0) & (df['lat'] < 19.8) & (df['lon'] > -99.6) & (df['lon'] < -98.8)]
        
        if df.empty: return pd.DataFrame(), gpd.GeoDataFrame()

        # Creación de Geometría
        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
    except Exception as e:
        st.error(f"⚠️ Error Crítico en Base de Datos: {e}")
        return pd.DataFrame(), gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()

# ==========================================
# 3. INTERFAZ DE CONTROL (SIDEBAR)
# ==========================================
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
    # 4. INICIALIZACIÓN DEL MAPA (ESTILO CLARO)
    # ==========================================
    centro_lat = df_datos['lat'].mean()
    centro_lon = df_datos['lon'].mean()
    
    mapa = folium.Map(
        location=[centro_lat, centro_lon], 
        zoom_start=11, 
        tiles="cartodbpositron" 
    )

    # ==========================================
    # 5. CAPAS TERRITORIALES AUTÓNOMAS (LOCALES)
    # ==========================================
    
    # Capa A: Perímetro CDMX (Línea Principal)
    try:
        with open("limites_cdmx.json", encoding='utf-8') as f:
            datos_perimetro = json.load(f)
            folium.GeoJson(
                datos_perimetro,
                name="Límite Ciudad de México",
                style_function=lambda x: {
                    'fillColor': 'transparent',
                    'color': '#2C3E50',
                    'weight': 3,
                    'dashArray': '5, 5'
                }
            ).add_to(mapa)
    except:
        st.sidebar.warning("⚠️ Perímetro CDMX no cargado (Archivo faltante).")

    # Capa B: División de Alcaldías (Líneas Finas)
    try:
        with open("limites_cdmx.json", encoding='utf-8') as f:
            datos_alcaldias = json.load(f)
            folium.GeoJson(
                datos_alcaldias,
                name="División de Alcaldías",
                style_function=lambda x: {
                    'fillColor': 'transparent',
                    'color': '#BDC3C7',
                    'weight': 1,
                    'opacity': 0.6
                }
            ).add_to(mapa)
    except:
        st.sidebar.warning("⚠️ División de Alcaldías no cargada.")

    # ==========================================
    # 6. BUSCADOR DE SITIOS
    # ==========================================
    capa_busqueda = folium.GeoJson(
        gdf_datos,
        name="Capa de Búsqueda",
        marker=folium.CircleMarker(radius=0, fill_opacity=0, opacity=0),
        tooltip=folium.GeoJsonTooltip(fields=['nombre_sitio', 'delegacion'], aliases=['Sitio:', 'Demarcación:'])
    ).add_to(mapa)

    Search(
        layer=capa_busqueda,
        geom_type='Point',
        placeholder="🔍 Buscar sitio (ej: HMG COYOACAN)...",
        collapsed=False,
        search_label='nombre_sitio',
        position='topright'
    ).add_to(mapa)

    # ==========================================
    # 7. CAPAS OPERATIVAS DINÁMICAS
    # ==========================================
    if modo_vista == "1. Agrupación Dinámica (Clusters)":
        st.subheader("Concentración de Sitios por Zona")
        cluster = MarkerCluster().add_to(mapa)
        for index, row in df_datos.iterrows():
            folium.Marker(
                location=[row['lat'], row['lon']],
                tooltip=f"🏢 {row['nombre_sitio']} | 📍 {row.get('delegacion', 'N/A')}"
            ).add_to(cluster)

    elif modo_vista == "2. Radios de Influencia (Operativo)":
        st.sidebar.markdown("---")
        radio_metros = st.sidebar.slider("Ajustar radio (metros):", 100, 3000, 500, step=100)
        st.subheader(f"Área de Cobertura: {radio_metros}m")
        for index, row in df_datos.iterrows():
            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=radio_metros,
                color="#0096FF",
                fill=True,
                fill_opacity=0.3,
                tooltip=f"🏢 {row['nombre_sitio']}"
            ).add_to(mapa)

    elif modo_vista == "3. Sectores Naturales (Huella Real)":
        st.subheader("Polígonos de Operación por Demarcación")
        if 'delegacion' in gdf_datos.columns:
            sectores = gdf_datos.dissolve(by='delegacion')
            sectores['geometry'] = sectores.geometry.convex_hull
            # Solo dibujamos si tienen al menos 3 puntos (forman área)
            validos = sectores[sectores.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            if not validos.empty:
                folium.GeoJson(
                    validos,
                    style_function=lambda x: {'fillColor': '#FF6400', 'color': '#FF6400', 'weight': 2, 'fillOpacity': 0.3},
                    tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Demarcación:'])
                ).add_to(mapa)
            else:
                st.warning("Puntos muy dispersos para generar polígonos.")

    elif modo_vista == "4. Mapa de Calor (Densidad)":
        st.subheader("Densidad de Infraestructura Territorial")
        HeatMap([[r['lat'], r['lon']] for i, r in df_datos.iterrows()]).add_to(mapa)

    # ==========================================
    # 8. DESPLIEGUE FINAL Y MÉTRICAS
    # ==========================================
    st_folium(mapa, width=1200, height=600, returned_objects=[])

    st.markdown("### Resumen de Mando")
    c1, c2, c3 = st.columns(3)
    c1.metric("Sitios Monitoreados", len(df_datos))
    
    # Métrica blindada de presión
    if 'max' in df_datos.columns:
        val_max = pd.to_numeric(df_datos['max'], errors='coerce').mean()
        c2.metric("Presión Máx. Promedio", f"{round(val_max, 2)}" if not pd.isna(val_max) else "N/A")
    else:
        c2.metric("Presión Máx. Promedio", "N/A")
        
    # Métrica de demarcaciones (Alcaldías + Municipios)
    if 'delegacion' in df_datos.columns:
        c3.metric("Demarcaciones Operativas", df_datos['delegacion'].nunique())
else:
    st.info("💡 Esperando archivo 'mis_datos.json' con coordenadas válidas para iniciar el tablero.")