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
# 2. CARGA Y LIMPIEZA DE DATOS (BLINDAJE ABSOLUTO)
# ==========================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = pd.read_json("mis_datos.json", orient="index")
        
        if df.empty: return pd.DataFrame(), gpd.GeoDataFrame()

        df['nombre_sitio'] = df.index.astype(str).str.replace("_", " ")
        if 'lat' not in df.columns: df['lat'] = None
        if 'lon' not in df.columns: df['lon'] = None
            
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        df = df[(df['lat'] > 19.0) & (df['lat'] < 19.8) & (df['lon'] > -99.6) & (df['lon'] < -98.8)]
        
        if df.empty: return pd.DataFrame(), gpd.GeoDataFrame()

        geometria = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometria, crs="EPSG:4326")
        return df, gdf
    except Exception as e:
        st.error(f"⚠️ Alerta Operativa: El archivo JSON tiene un error de estructura. Detalle: {e}")
        return pd.DataFrame(), gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()

if not df_datos.empty:
    st.sidebar.header("⚙️ Panel Directivo")
    
    # ==========================================
    # NUEVO: MOTOR DE FILTRADO DINÁMICO
    # ==========================================
    st.sidebar.markdown("### 🔍 Filtros de Búsqueda")
    
    texto_busqueda = st.sidebar.text_input("Coincidencia en nombre (ej. VILLA, SUR):", "")
    lista_demarcaciones = sorted(df_datos['delegacion'].dropna().unique())
    demarcaciones_seleccionadas = st.sidebar.multiselect("Filtrar por Demarcación:", lista_demarcaciones)
    
    # Aplicar los filtros a la base de datos
    df_filtrado = df_datos.copy()
    
    if texto_busqueda:
        df_filtrado = df_filtrado[df_filtrado['nombre_sitio'].str.contains(texto_busqueda, case=False, na=False)]
        
    if demarcaciones_seleccionadas:
        df_filtrado = df_filtrado[df_filtrado['delegacion'].isin(demarcaciones_seleccionadas)]
        
    # Reconstruir la geometría si hay datos después del filtro
    if not df_filtrado.empty:
        geometria_filtro = [Point(xy) for xy in zip(df_filtrado['lon'], df_filtrado['lat'])]
        gdf_filtrado = gpd.GeoDataFrame(df_filtrado, geometry=geometria_filtro, crs="EPSG:4326")
    else:
        gdf_filtrado = gpd.GeoDataFrame()

    st.sidebar.markdown("---")
    modo_vista = st.sidebar.radio(
        "Selecciona la capa de análisis:",
        [
            "1. Agrupación Dinámica (Clusters)", 
            "2. Radios de Influencia (Operativo)", 
            "3. Sectores Naturales (Huella Real)",
            "4. Mapa de Calor (Densidad)",
            "5. Áreas de Influencia (Voronoi)"
        ]
    )

    # ==========================================
    # 3. INICIALIZACIÓN DEL MAPA
    # ==========================================
    if not df_filtrado.empty:
        centro_lat = df_filtrado['lat'].mean()
        centro_lon = df_filtrado['lon'].mean()
    else:
        centro_lat, centro_lon = 19.4326, -99.1332 # Zócalo por defecto si el filtro vacía el mapa
        
    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=11, tiles="cartodbpositron")
    
    # ==========================================
    # 4. CAPAS TERRITORIALES OFICIALES
    # ==========================================
    try:
        folium.GeoJson("perimetro_cdmx.json", name="Límite Ciudad de México", style_function=lambda x: {'fillColor': 'transparent', 'color': '#2C3E50', 'weight': 3, 'dashArray': '5, 5'}).add_to(mapa)
    except: pass 

    try:
        folium.GeoJson("alcaldias_cdmx.json", name="División de Alcaldías", style_function=lambda x: {'fillColor': 'transparent', 'color': '#BDC3C7', 'weight': 1, 'opacity': 0.6}).add_to(mapa)
    except: pass
    
    # ==========================================
    # 5. BUSCADOR INTERNO DEL MAPA (Mantiene compatibilidad)
    # ==========================================
    if not gdf_filtrado.empty:
        capa_busqueda = folium.GeoJson(
            gdf_filtrado,
            name="Buscador de Sitios",
            marker=folium.CircleMarker(radius=0, fill_opacity=0, opacity=0),
            tooltip=folium.GeoJsonTooltip(fields=['nombre_sitio', 'delegacion'], aliases=['Sitio:', 'Delegación:'])
        ).add_to(mapa)

        Search(
            layer=capa_busqueda,
            geom_type='Point',
            placeholder="🔍 Buscar punto específico en el mapa...",
            collapsed=False,
            search_label='nombre_sitio',
            position='topright'
        ).add_to(mapa)

    # ==========================================
    # 6. RENDERIZADO DE CAPAS OPERATIVAS (USANDO DF_FILTRADO)
    # ==========================================
    if not df_filtrado.empty:
        if modo_vista == "1. Agrupación Dinámica (Clusters)":
            st.subheader("Puntos agrupados por concentración territorial")
            cluster = MarkerCluster().add_to(mapa)
            for index, row in df_filtrado.iterrows():
                folium.Marker(location=[row['lat'], row['lon']], tooltip=f"🏢 Sitio: {row['nombre_sitio']} | 📍 Delegación: {row.get('delegacion', 'N/A')} | 📊 Min: {row.get('min', '-')} Max: {row.get('max', '-')}").add_to(cluster)

        elif modo_vista == "2. Radios de Influencia (Operativo)":
            st.sidebar.markdown("---")
            radio_metros = st.sidebar.slider("Ajustar radio (metros):", 50, 2000, 500, step=50)
            st.subheader(f"Zonas de cobertura a {radio_metros} metros")
            for index, row in df_filtrado.iterrows():
                folium.Circle(location=[row['lat'], row['lon']], radius=radio_metros, color="#0096FF", fill=True, fill_color="#0096FF", fill_opacity=0.4, tooltip=f"🏢 Sitio: {row['nombre_sitio']}").add_to(mapa)

        elif modo_vista == "3. Sectores Naturales (Huella Real)":
            st.subheader("Polígonos de operación agrupados por Demarcación")
            if 'delegacion' in gdf_filtrado.columns:
                sectores = gdf_filtrado.dissolve(by='delegacion')
                sectores['geometry'] = sectores.geometry.convex_hull
                sectores_validos = sectores[sectores.geometry.type.isin(['Polygon', 'MultiPolygon'])]
                if not sectores_validos.empty:
                    folium.GeoJson(sectores_validos, style_function=lambda x: {'fillColor': '#FF6400', 'color': '#FF6400', 'weight': 2, 'fillOpacity': 0.4}, tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Delegación:'])).add_to(mapa)
                else:
                    st.warning("Los puntos filtrados están muy dispersos para formar polígonos.")

        elif modo_vista == "4. Mapa de Calor (Densidad)":
            st.subheader("Concentración de la búsqueda actual")
            datos_calor = [[row['lat'], row['lon']] for index, row in df_filtrado.iterrows() if pd.notna(row['lat']) and pd.notna(row['lon'])]
            if len(datos_calor) > 0:
                HeatMap(datos_calor, radius=15, blur=10).add_to(mapa)

        elif modo_vista == "5. Áreas de Influencia (Voronoi)":
            st.subheader("Zonas de Jurisdicción Exacta de los sitios filtrados")
            if len(df_filtrado) >= 4:
                try:
                    puntos = MultiPoint(gdf_filtrado.geometry.tolist())
                    regiones_voronoi = voronoi_diagram(puntos)
                    gdf_voronoi = gpd.GeoDataFrame(geometry=[geom for geom in regiones_voronoi.geoms], crs="EPSG:4326")
                    folium.GeoJson(gdf_voronoi, style_function=lambda x: {'fillColor': '#28B463', 'color': '#196F3D', 'weight': 2, 'fillOpacity': 0.2}).add_to(mapa)
                    for index, row in df_filtrado.iterrows():
                        folium.CircleMarker(location=[row['lat'], row['lon']], radius=4, color='#E74C3C', fill=True, fill_opacity=1, tooltip=f"🏢 {row['nombre_sitio']}").add_to(mapa)
                except Exception as e:
                    st.error(f"⚠️ Error matemático de Voronoi al filtrar: {e}")
            else:
                st.warning("Se necesitan al menos 4 puntos para trazar zonas de Voronoi. Amplía tu búsqueda.")
    else:
        st.warning("No hay sitios que coincidan con tu búsqueda.")

    # ==========================================
    # 7. DESPLIEGUE DEL MAPA Y MÉTRICAS (MÉTRICAS DINÁMICAS)
    # ==========================================
    st_folium(mapa, width=1200, height=600, returned_objects=[])

    st.markdown("### Resumen de la Búsqueda")
    col1, col2, col3 = st.columns(3)
    col1.metric("Sensores en pantalla", len(df_filtrado))
    
    if 'max' in df_filtrado.columns and not df_filtrado.empty:
        max_limpio = pd.to_numeric(df_filtrado['max'], errors='coerce')
        if not max_limpio.isna().all():
            col2.metric("Presión Máx. (Filtro)", round(max_limpio.mean(), 3))
        else:
            col2.metric("Presión Máx. (Filtro)", "N/A")
    else:
        col2.metric("Presión Máx. (Filtro)", "N/A")
        
    if 'delegacion' in df_filtrado.columns and not df_filtrado.empty:
        col3.metric("Demarcaciones afectadas", df_filtrado['delegacion'].nunique())
    else:
        col3.metric("Demarcaciones afectadas", "0")

    # ==========================================
    # 8. DESGLOSE POR DEMARCACIÓN 
    # ==========================================
    st.markdown("---")
    st.subheader("📊 Distribución de la Búsqueda")
    if 'delegacion' in df_filtrado.columns and not df_filtrado.empty:
        conteo_delegaciones = df_filtrado['delegacion'].value_counts().reset_index()
        conteo_delegaciones.columns = ['Demarcación', 'Sensores Encontrados']
        st.dataframe(conteo_delegaciones, use_container_width=True)
    else:
        st.info("No hay datos para mostrar en la tabla con los filtros actuales.")

    # ==========================================
    # 9. AUDITORÍA DE CALIDAD DE DATOS (Mantiene el total)
    # ==========================================
    st.markdown("---")
    st.subheader("🛑 Auditoría Operativa: Sitios descartados del total original")
    df_crudo = pd.read_json("mis_datos.json", orient="index")
    descartados = df_crudo[~df_crudo.index.isin(df_datos.index)]
    
    if not descartados.empty:
        st.warning(f"Se aislaron {len(descartados)} registros por errores de captura en coordenadas:")
        st.dataframe(descartados[['delegacion', 'lat', 'lon']])
    else:
        st.success("Todos los registros tienen coordenadas correctas.")

else:
    st.info("💡 La plataforma está en línea. Esperando registros.")