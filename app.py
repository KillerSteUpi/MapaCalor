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
# 2. CARGA DE DATOS OPERATIVOS (SENSORES)
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
        return pd.DataFrame(), gpd.GeoDataFrame()

# ==========================================
# NUEVO: CARGA DE CAPA DE COLONIAS OFICIALES
# ==========================================
@st.cache_data(ttl=3600)
def cargar_colonias():
    try:
        if not os.path.exists("georef-mexico-colonia.json"):
            return gpd.GeoDataFrame()
            
        with open("georef-mexico-colonia.json", encoding="utf-8") as f:
            datos_col = json.load(f)
            
        features = []
        for item in datos_col:
            feat = item.get("geo_shape")
            if not feat: continue
            
            # El JSON tiene los nombres dentro de listas, los extraemos
            nombre = item.get("col_name", [""])[0] if isinstance(item.get("col_name"), list) else item.get("col_name", "")
            alcaldia = item.get("mun_name", [""])[0] if isinstance(item.get("mun_name"), list) else item.get("mun_name", "")
            
            feat["properties"] = {
                "colonia": str(nombre).upper(),
                "alcaldia": str(alcaldia).upper()
            }
            features.append(feat)
            
        # Convertimos a formato geográfico
        gdf_col = gpd.GeoDataFrame.from_features({"type": "FeatureCollection", "features": features})
        gdf_col = gdf_col.set_crs("EPSG:4326")
        return gdf_col
    except Exception as e:
        st.error(f"⚠️ Error en capa de colonias: {e}")
        return gpd.GeoDataFrame()

df_datos, gdf_datos = cargar_datos()
gdf_colonias = cargar_colonias()

if not df_datos.empty:
    st.sidebar.header("⚙️ Panel de Control")
    
    # ------------------------------------------
    # BUSCADOR GLOBAL DE COLONIAS (CAPA DORADA)
    # ------------------------------------------
    st.sidebar.markdown("### 🏘️ Visor de Colonias")
    if not gdf_colonias.empty:
        lista_todas_colonias = sorted(gdf_colonias['colonia'].dropna().unique())
        colonias_seleccionadas = st.sidebar.multiselect(
            "Selecciona la colonia para iluminar su límite:", 
            lista_todas_colonias,
            placeholder="Ej. CENTRO, NARVARTE..."
        )
    else:
        colonias_seleccionadas = []
        st.sidebar.warning("⚠️ Archivo de colonias no encontrado.")
        
    st.sidebar.markdown("---")
    
    # ------------------------------------------
    # FILTRO OPERATIVO DE SENSORES
    # ------------------------------------------
    st.sidebar.markdown("### 🔍 Buscador de Sensores")
    texto_filtro = st.sidebar.text_input("Filtrar por nombre de sitio:", placeholder="Ej: ZARAGOZA, POZO...")
    lista_deleg = sorted(df_datos['delegacion'].dropna().unique())
    deleg_selec = st.sidebar.multiselect("Filtrar sensores por Demarcación:", lista_deleg)
    
    df_f = df_datos.copy()
    if texto_filtro:
        df_f = df_f[df_f['nombre_sitio'].str.contains(texto_filtro, case=False, na=False)]
    if deleg_selec:
        df_f = df_f[df_f['delegacion'].isin(deleg_selec)]

    st.sidebar.markdown("---")
    modo_vista = st.sidebar.radio(
        "Capa Operativa (Aplica a Sensores):",
        ["1. Clusters", "2. Radios", "3. Sectores", "4. Calor", "5. Voronoi"]
    )

    # ==========================================
    # 3. CONSTRUCCIÓN DEL MAPA
    # ==========================================
    # Sistema de Auto-Enfoque: Si busca una colonia, la cámara vuela hacia allá
    if colonias_seleccionadas and not gdf_colonias.empty:
        gdf_col_filtradas = gdf_colonias[gdf_colonias['colonia'].isin(colonias_seleccionadas)]
        # Usamos warning capture para el centroid de zonas no proyectadas
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c_lat = gdf_col_filtradas.geometry.centroid.y.mean()
            c_lon = gdf_col_filtradas.geometry.centroid.x.mean()
    elif not df_f.empty:
        c_lat, c_lon = df_f['lat'].mean(), df_f['lon'].mean()
    else:
        c_lat, c_lon = 19.4326, -99.1332
        
    mapa = folium.Map(location=[c_lat, c_lon], zoom_start=13 if colonias_seleccionadas else 11, tiles="cartodbpositron")
    
    # Capa Perimetral CDMX
    try:
        folium.GeoJson("perimetro_cdmx.json", name="CDMX", style_function=lambda x: {'color': '#2C3E50', 'weight': 2, 'dashArray': '5, 5'}).add_to(mapa)
    except: pass

    # ------------------------------------------
    # DIBUJO DE POLÍGONOS DE COLONIAS (NUEVO)
    # ------------------------------------------
    if colonias_seleccionadas and not gdf_colonias.empty:
        folium.GeoJson(
            gdf_col_filtradas,
            name="Colonias Seleccionadas",
            style_function=lambda x: {
                'fillColor': '#F1C40F', # Color dorado
                'color': '#E67E22',     # Borde naranja
                'weight': 3,
                'fillOpacity': 0.3
            },
            tooltip=folium.GeoJsonTooltip(fields=['colonia', 'alcaldia'], aliases=['Colonia:', 'Demarcación:'])
        ).add_to(mapa)

    # ------------------------------------------
    # DIBUJO DE SENSORES OPERATIVOS
    # ------------------------------------------
    if not df_f.empty:
        if modo_vista == "1. Clusters":
            cluster = MarkerCluster().add_to(mapa)
            for i, r in df_f.iterrows():
                folium.Marker([r['lat'], r['lon']], tooltip=f"🏢 {r['nombre_sitio']}").add_to(cluster)
        
        elif modo_vista == "2. Radios":
            for i, r in df_f.iterrows():
                folium.Circle([r['lat'], r['lon']], radius=500, color="#0096FF", fill=True).add_to(mapa)
        
        elif modo_vista == "3. Sectores":
            if 'delegacion' in df_f.columns:
                gdf_f = gpd.GeoDataFrame(df_f, geometry=[Point(xy) for xy in zip(df_f['lon'], df_f['lat'])], crs="EPSG:4326")
                sectores = gdf_f.dissolve(by='delegacion')
                sectores['geometry'] = sectores.geometry.convex_hull
                sectores_validos = sectores[sectores.geometry.type.isin(['Polygon', 'MultiPolygon'])]
                if not sectores_validos.empty:
                    folium.GeoJson(sectores_validos, style_function=lambda x: {'fillColor': '#FF6400', 'color': '#FF6400', 'weight': 2, 'fillOpacity': 0.4}, tooltip=folium.GeoJsonTooltip(fields=['delegacion'], aliases=['Delegación:'])).add_to(mapa)

        elif modo_vista == "4. Calor":
            datos_calor = [[r['lat'], r['lon']] for i, r in df_f.iterrows()]
            HeatMap(datos_calor, radius=15, blur=10).add_to(mapa)

        elif modo_vista == "5. Voronoi":
            if len(df_f) > 3:
                try:
                    puntos = MultiPoint([(r.lon, r.lat) for i, r in df_f.iterrows()])
                    regiones = voronoi_diagram(puntos)
                    gdf_voronoi = gpd.GeoDataFrame(geometry=[geom for geom in regiones_voronoi.geoms], crs="EPSG:4326")
                    folium.GeoJson(gdf_voronoi, style_function=lambda x: {'fillColor': '#28B463', 'opacity': 0.2}).add_to(mapa)
                    for i, r in df_f.iterrows():
                        folium.CircleMarker([r['lat'], r['lon']], radius=4, color='#E74C3C', fill=True, tooltip=f"🏢 {r['nombre_sitio']}").add_to(mapa)
                except:
                    pass

    st_folium(mapa, width=1200, height=550)

    # ==========================================
    # 4. MÉTRICAS EJECUTIVAS
    # ==========================================
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Sensores en pantalla", len(df_f))
    if 'max' in df_f.columns:
        c2.metric("Presión Promedio", round(pd.to_numeric(df_f['max'], errors='coerce').mean(), 3))
    c3.metric("Demarcaciones Filtradas", df_f['delegacion'].nunique())

    if not df_f.empty:
        st.markdown("### 📋 Listado de Sensores")
        st.dataframe(df_f[['nombre_sitio', 'delegacion', 'max']].sort_values(by='nombre_sitio'), use_container_width=True)

else:
    st.info("💡 Cargue registros operativos con coordenadas válidas para iniciar el tablero.")