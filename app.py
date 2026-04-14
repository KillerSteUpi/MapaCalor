import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from shapely.geometry import Point
import json

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Tablero Territorial CDMX", layout="wide")
st.title("📍 Sistema de Inteligencia Territorial")
st.markdown("---")

# ==========================================
# 2. CARGA Y PREPARACIÓN DE DATOS
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        # El parámetro orient="index" es clave para leer tu estructura de JSON
        df = pd.read_json("mis_datos.json", orient="index")
        
        # Eliminamos filas que no tengan coordenadas válidas para evitar errores
        df = df.dropna(subset=['lat', 'lon'])
        
        # Convertir a formato espacial (GeoDataFrame)
        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
        
    except FileNotFoundError:
        st.error("⚠️ No se encontró el archivo 'mis_datos.json'. Asegúrate de que esté en la misma carpeta que este script.")
        return pd.DataFrame(), gpd.GeoDataFrame()
    except Exception as e:
        st.error(f"⚠️ Hubo un error al leer el archivo: {e}")
        return pd.DataFrame(), gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()

# ==========================================
# 3. INTERFAZ DE USUARIO (Panel Lateral)
# ==========================================
# Solo mostramos la interfaz si los datos cargaron correctamente
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

    # Centramos el mapa en las coordenadas promedio de tu base
    vista_inicial = pdk.ViewState(
        latitude=df_datos['lat'].mean(), 
        longitude=df_datos['lon'].mean(), 
        zoom=11, 
        pitch=45
    )

    capas_mapa = []

    # ==========================================
    # 4. LÓGICA DE LAS CAPAS
    # ==========================================

    if modo_vista == "1. Radios de Influencia (Operativo)":
        st.sidebar.markdown("---")
        radio_metros = st.sidebar.slider("Ajustar radio (metros):", 50, 2000, 500, step=50)
        st.subheader(f"Zonas de cobertura a {radio_metros} metros")
        
        capa_radios = pdk.Layer(
            "ScatterplotLayer",
            data=df_datos,
            get_position="[lon, lat]",
            get_radius=radio_metros,
            # Se usa un color fijo semitransparente
            get_fill_color="[0, 150, 255, 120]", 
            get_line_color="[255, 255, 255]",
            pickable=True,
            opacity=0.8,
            stroked=True,
            filled=True,
        )
        capas_mapa.append(capa_radios)

    elif modo_vista == "2. Sectores Naturales (Huella Real)":
        st.subheader("Polígonos de operación real agrupados por Delegación")
        
        # Agrupamos por tu llave "delegacion"
        sectores = gdf_datos.dissolve(by='delegacion')
        sectores['geometry'] = sectores.geometry.convex_hull
        
        sectores_json = json.loads(sectores.to_json())
        
        capa_poligonos = pdk.Layer(
            "GeoJsonLayer",
            sectores_json,
            opacity=0.4,
            stroked=True,
            filled=True,
            extruded=False,
            wireframe=True,
            get_fill_color="[255, 100, 0, 80]",
            get_line_color="[255, 255, 255]",
            get_line_width=150,
            pickable=True
        )
        capas_mapa.append(capa_poligonos)

    elif modo_vista == "3. Mapa de Calor (Densidad)":
        st.subheader("Concentración de registros")
        
        capa_calor = pdk.Layer(
            "HexagonLayer",
            data=df_datos,
            get_position="[lon, lat]",
            radius=400,
            elevation_scale=50,
            elevation_range=[0, 3000],
            pickable=True,
            extruded=True
        )
        capas_mapa.append(capa_calor)

    # ==========================================
    # 5. RENDERIZADO DEL MAPA Y MÉTRICAS
    # ==========================================
    st.pydeck_chart(pdk.Deck(
       map_style="carto-darkmatter",
        initial_view_state=vista_inicial,
        layers=capas_mapa,
        tooltip={"text": "Registro detectado"}
    ))

    st.markdown("### Resumen Ejecutivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Registros", len(df_datos))
    
    # Manejamos los valores min y max según tu estructura
    if 'max' in df_datos.columns:
        col2.metric("Presión Máx. Promedio", round(df_datos['max'].mean(), 3))
    
    col3.metric("Delegaciones Activas", df_datos['delegacion'].nunique())