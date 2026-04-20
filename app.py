

#Mpa de alcaldias Unidas
import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap, MarkerCluster, Search
from streamlit_folium import st_folium

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="Tablero Territorial CDMX", layout="wide")
st.title("📍 Sistema de Inteligencia Territorial")
st.markdown("---")

# ==========================================
# 2. CARGA Y LIMPIEZA DE DATOS (BLINDAJE ABSOLUTO)
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = pd.read_json("mis_datos.json", orient="index")
        
        if df.empty:
            return pd.DataFrame(), gpd.GeoDataFrame()

        df['nombre_sitio'] = df.index.astype(str).str.replace("_", " ")
        
        if 'lat' not in df.columns: df['lat'] = None
        if 'lon' not in df.columns: df['lon'] = None
            
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        df = df[(df['lat'] > 19.0) & (df['lat'] < 19.8) & (df['lon'] > -99.6) & (df['lon'] < -98.8)]
        
        if df.empty:
            return pd.DataFrame(), gpd.GeoDataFrame()

        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
    except Exception as e:
        st.error(f"⚠️ Alerta Operativa: El archivo JSON tiene un error de estructura. Detalle: {e}")
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
    # 3. INICIALIZACIÓN DEL MAPA (BLANCO)
    # ==========================================
    centro_lat = df_datos['lat'].mean()
    centro_lon = df_datos['lon'].mean()
    
    mapa = folium.Map(
        location=[centro_lat, centro_lon], 
        zoom_start=10, 
        tiles="cartodbpositron" 
    )

    # NOTA: Se removió la capa externa del perímetro CDMX para evitar caídas de red.
    
    # ==========================================
    # 4. CAPAS TERRITORIALES OFICIALES (BLINDADAS)
    # ==========================================
    # Estas capas se leen desde los archivos que subiste a GitHub, eliminando la dependencia de internet.
    
    # Capa 1: Límite Estatal CDMX (Línea elegante)
    try:
        folium.GeoJson(
            "perimetro_cdmx.json",
            name="Límite Ciudad de México",
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': '#2C3E50', # Gris oscuro
                'weight': 3,
                'dashArray': '5, 5' # Línea punteada
            }
        ).add_to(mapa)
    except:
        st.sidebar.warning("⚠️ No se encontró el archivo del perímetro de CDMX.")

    # Capa 2: División de Alcaldías (Líneas finas)
    try:
        folium.GeoJson(
            "alcaldias_cdmx.json",
            name="División de Alcaldías",
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': '#BDC3C7', # Gris muy claro
                'weight': 1,
                'opacity': 0.6
            }
        ).add_to(mapa)
    except:
        st.sidebar.warning("⚠️ No se encontró el archivo de las alcaldías.")
    

    # ==========================================
    # 4. BUSCADOR INTELIGENTE
    # ==========================================
    capa_busqueda = folium.GeoJson(
        gdf_datos,
        name="Buscador de Sitios",
        marker=folium.CircleMarker(radius=0, fill_opacity=0, opacity=0),
        tooltip=folium.GeoJsonTooltip(fields=['nombre_sitio', 'delegacion'], aliases=['Sitio:', 'Delegación:'])
    ).add_to(mapa)

    Search(
        layer=capa_busqueda,
        geom_type='Point',
        placeholder="🔍 Buscar nombre de sitio...",
        collapsed=False,
        search_label='nombre_sitio',
        position='topright'
    ).add_to(mapa)

    # ==========================================
    # 5. RENDERIZADO DE CAPAS OPERATIVAS
    # ==========================================
    if modo_vista == "1. Agrupación Dinámica (Clusters)":
        st.subheader("Puntos agrupados por concentración territorial")
        cluster = MarkerCluster().add_to(mapa)
        
        for index, row in df_datos.iterrows():
            folium.Marker(
                location=[row['lat'], row['lon']],
                tooltip=f"🏢 Sitio: {row['nombre_sitio']} | 📍 Delegación: {row.get('delegacion', 'N/A')} | 📊 Min: {row.get('min', '-')} Max: {row.get('max', '-')}"
            ).add_to(cluster)

    elif modo_vista == "2. Radios de Influencia (Operativo)":
        st.sidebar.markdown("---")
        radio_metros = st.sidebar.slider("Ajustar radio (metros):", 50, 2000, 500, step=50)
        st.subheader(f"Zonas de cobertura a {radio_metros} metros")
        
        for index, row in df_datos.iterrows():
            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=radio_metros,
                color="#0096FF",
                fill=True,
                fill_color="#0096FF",
                fill_opacity=0.4,
                tooltip=f"🏢 Sitio: {row['nombre_sitio']} | 📍 Delegación: {row.get('delegacion', 'N/A')}"
            ).add_to(mapa)

   """ elif modo_vista == "3. Sectores Naturales (Huella Real)":
        st.subheader("Polígonos de operación real agrupados por Delegación")
        
        if 'delegacion' in gdf_datos.columns:
            sectores = gdf_datos.dissolve(by='delegacion')
            sectores['geometry'] = sectores.geometry.convex_hull
            sectores_validos = sectores[sectores.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            
            if not sectores_validos.empty:
                folium.GeoJson(
                    sectores_validos,
                    style_function=lambda x: {
                        'fillColor': '#FF6400',
                        'color': '#FF6400', 
                        'weight': 2,
                        'fillOpacity': 0.4
                    },
                    tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Delegación:'])
                ).add_to(mapa)
            else:
                st.warning("No hay suficientes registros agrupados para trazar sectores poligonales.")
"""
    elif modo_vista == "4. Mapa de Calor (Densidad)":
        st.subheader("Concentración histórica de registros")
        datos_calor = [[row['lat'], row['lon']] for index, row in df_datos.iterrows() if pd.notna(row['lat']) and pd.notna(row['lon'])]
        if len(datos_calor) > 0:
            HeatMap(datos_calor, radius=15, blur=10).add_to(mapa)

    # ==========================================
    # 6. DESPLIEGUE DEL MAPA Y MÉTRICAS
    # ==========================================
    st_folium(mapa, width=1200, height=600, returned_objects=[])

    st.markdown("### Resumen Ejecutivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Registros Operativos (Zona Centro)", len(df_datos))
    
    if 'max' in df_datos.columns:
        max_limpio = pd.to_numeric(df_datos['max'], errors='coerce')
        if not max_limpio.isna().all():
            #col2.metric("Presión Máx. Promedio")
            col2.metric("Presión Máx. Promedio", round(max_limpio.mean(), 3))
        else:
            col2.metric("Presión Máx. Promedio", "N/A")
    else:
        col2.metric("Presión Máx. Promedio", "N/A")
        
    if 'delegacion' in df_datos.columns:
        col3.metric("Demarcaciones Operativas", df_datos['delegacion'].nunique())
    else:
        col3.metric("Demarcaciones Operativas", "N/A")
else:
    st.info("💡 La plataforma está en línea. Esperando registros con coordenadas válidas para CDMX.")