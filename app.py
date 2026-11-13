"""ECDS | Environmental Crime Detection System — Increment 1 interface.

This is a functional UI/AOI prototype. NO satellite detection is performed yet.
"""
from __future__ import annotations

import json
from datetime import date

import folium
import streamlit as st
from folium.plugins import Draw, Fullscreen, MeasureControl
from streamlit_folium import st_folium

from geo_utils import AOIError, MAX_HA, MIN_HA, validate_aoi

st.set_page_config(
    page_title="ECDS | Environmental Crime Detection System",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1600px; }
  [data-testid="stSidebar"] { background-color: #f1f5f8; }
  [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {color: #17364a;}
  .ecds-header {background: #17364a; color: #fff; padding: 18px 22px; border-radius: 10px; margin-bottom: 13px; }
  .ecds-title {font-size: 1.9rem; font-weight: 750; letter-spacing: .02em;}
  .ecds-subtitle {font-size: .95rem; color: #d5e5ee; margin-top: 3px;}
  .ecds-pill {display: inline-block; color: #dce8ed; border: 1px solid #7996a8; border-radius: 20px; font-size:.73rem; padding:2px 10px; margin-top:9px;}
  .section-hint {color:#596b78; font-size:.87rem;}
</style>
""", unsafe_allow_html=True)

MUNICIPALITIES = {
    "Sweden (overview)": (62.0, 16.0, 5),
    "Stockholm": (59.3293, 18.0686, 11),
    "Norrtälje": (59.7580, 18.7049, 11),
    "Uppsala": (59.8586, 17.6389, 11),
    "Göteborg": (57.7089, 11.9746, 11),
    "Malmö": (55.6050, 13.0038, 11),
    "Umeå": (63.8258, 20.2630, 11),
    "Östersund": (63.1792, 14.6357, 11),
    "Luleå": (65.5848, 22.1547, 11),
}

for key, initial in {
    "accepted_aoi": None,
    "aoi_origin": None,
    "last_drawing_signature": None,
    "map_city": "Sweden (overview)",
    "map_epoch": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = initial

st.markdown("""
<div class="ecds-header">
<div class="ecds-title">ECDS</div>
<div class="ecds-subtitle">Environmental Crime Detection System</div>
<div class="ecds-pill">Prototype · Geospatial screening · Analyst review required</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("Analysis Configuration")
    st.caption("Increment 1 — Interface and AOI controls")
    st.divider()
    st.subheader("1 · Study Area")
    municipality = st.selectbox(
        "Navigate to municipality", list(MUNICIPALITIES),
        index=list(MUNICIPALITIES).index(st.session_state.map_city),
        help="Map navigation only. This does not select a complete municipal boundary or create an AOI.",
    )
    st.session_state.map_city = municipality
    st.caption("Select a location, then draw a polygon/rectangle on the map or upload one GeoJSON polygon.")
    st.info(f"Allowed AOI: **{MIN_HA:,.0f}–{MAX_HA:,.0f} ha** (0.5–50 km²). One AOI per analysis, within Sweden.")
    uploaded = st.file_uploader("Upload AOI (.geojson or .json)", type=["geojson", "json"])
    if uploaded is not None:
        file_signature = f"{uploaded.name}:{uploaded.size}:{hash(uploaded.getvalue())}"
        if st.session_state.get("uploaded_signature") != file_signature:
            try:
                accepted = validate_aoi(uploaded.getvalue())
                st.session_state.accepted_aoi = accepted
                st.session_state.aoi_origin = "Uploaded GeoJSON"
                st.session_state.uploaded_signature = file_signature
                st.success("Uploaded AOI accepted.")
            except (AOIError, ValueError, json.JSONDecodeError) as exc:
                st.error(str(exc))
    if st.session_state.accepted_aoi:
        st.success(f"AOI accepted · {st.session_state.accepted_aoi['area_ha']:,.2f} ha")
        st.caption(f"Source: {st.session_state.aoi_origin}")
    else:
        st.warning("No valid AOI selected.")
    if st.button("Remove AOI", use_container_width=True):
        st.session_state.accepted_aoi = None
        st.session_state.aoi_origin = None
        st.session_state.uploaded_signature = None
        st.session_state.last_drawing_signature = None
        st.session_state.map_epoch += 1
        st.rerun()

    st.divider()
    st.subheader("2 · Analysis Period")
    season = st.selectbox("Season", ["Summer (Jun–Aug)", "Late summer (Jul–Sep)", "Growing season (May–Sep)"], index=0)
    complete_year = date.today().year if date.today().month >= 10 else date.today().year - 1
    years = list(range(complete_year, 2018, -1))
    before_year = st.selectbox("Reference year", years, index=min(1, len(years)-1))
    after_year = st.selectbox("Comparison year", years, index=0)
    season_bounds = {"Summer (Jun–Aug)": ((6,1), (8,31)), "Late summer (Jul–Sep)": ((7,1), (9,30)), "Growing season (May–Sep)": ((5,15), (9,15))}
    (sm, sd), (em, ed) = season_bounds[season]
    with st.expander("Review or edit exact dates", expanded=False):
        before_start = st.date_input("Reference start", date(before_year, sm, sd))
        before_end = st.date_input("Reference end", date(before_year, em, ed))
        after_start = st.date_input("Comparison start", date(after_year, sm, sd))
        after_end = st.date_input("Comparison end", date(after_year, em, ed))
    dates_valid = before_start < before_end < after_start < after_end <= date.today()
    if not dates_valid:
        st.error("Dates must be valid, sequential and not extend into the future.")

    st.divider()
    st.subheader("3 · Detection Settings")
    st.caption("Defaults preserved from the existing GEE application.")
    with st.expander("Advanced spectral and processing thresholds", expanded=False):
        ndvi_drop = st.slider("Minimum NDVI decrease", 0.10, 0.50, 0.25, 0.01)
        bsi_rise = st.slider("Minimum BSI increase", 0.00, 0.30, 0.08, 0.01)
        nbr_drop = st.slider("Minimum NBR decrease", 0.05, 0.40, 0.15, 0.01)
        min_patch = st.slider("Minimum patch size (ha)", 0.25, 10.0, 1.0, 0.25)
        cloud_score = st.slider("Cloud Score+ clear threshold", 0.40, 0.90, 0.65, 0.05)
    if st.session_state.accepted_aoi is None:
        st.caption("An accepted AOI is required before detection.")
    run_disabled = True  # Detection engine intentionally reserved for Increment 2.
    st.button("🛰️ Run Detection", type="primary", disabled=run_disabled, use_container_width=True,
              help="Enabled in Increment 2 when the verified GEE processing engine is connected.")
    st.caption("Detection is not connected in Increment 1.")

workspace, candidates_tab, analytics_tab, reports_tab = st.tabs(
    ["Detection Workspace", "Candidate Intelligence", "Spatial Analytics", "Reports & Data"]
)

with workspace:
    lhs, rhs = st.columns([0.26, 0.74], gap="medium")
    with lhs:
        st.subheader("Study Area")
        aoi = st.session_state.accepted_aoi
        if aoi:
            st.metric("Selected area", f"{aoi['area_ha']:,.1f} ha")
            st.caption(f"{aoi['area_km2']:.2f} km² · {st.session_state.aoi_origin}")
            st.caption("Sweden boundary: preliminary coarse screening, not cadastral precision.")
        else:
            st.metric("Selected area", "—")
            st.caption("Draw a polygon or rectangle with the map tools.")
        st.markdown("**Analysis comparison**")
        st.write(f"{before_start.isoformat()} → {before_end.isoformat()}")
        st.write(f"{after_start.isoformat()} → {after_end.isoformat()}")
        st.caption("The two periods must cover comparable seasons.")
        st.markdown("**Detection status**")
        st.info("Engine not yet connected · Increment 2")

    with rhs:
        h1, h2 = st.columns([0.7, 0.3])
        h1.subheader("Interactive GIS Map")
        base_map = h2.selectbox("Basemap", ["Satellite", "OpenStreetMap"], label_visibility="collapsed")
        lat, lon, zoom = MUNICIPALITIES[municipality]
        if st.session_state.accepted_aoi:
            lat, lon = st.session_state.accepted_aoi["center"]
            zoom = 12
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=True,
                       prefer_canvas=True)
        folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=base_map == "OpenStreetMap").add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles © Esri and contributors", name="Satellite", show=base_map == "Satellite"
        ).add_to(m)
        if st.session_state.accepted_aoi:
            folium.GeoJson(st.session_state.accepted_aoi["geometry"], name="Accepted AOI",
                           style_function=lambda _: {"color":"#00e5ff", "weight":3, "fillOpacity":0.08}).add_to(m)
        Draw(export=False, draw_options={"polyline":False,"circle":False,"circlemarker":False,
                "marker":False,"polygon":True,"rectangle":True},
             edit_options={"edit":False,"remove":True}).add_to(m)
        Fullscreen().add_to(m)
        MeasureControl(primary_length_unit="kilometers", primary_area_unit="sqmeters").add_to(m)
        folium.LayerControl(collapsed=True).add_to(m)
        output = st_folium(m, height=550, use_container_width=True,
                           returned_objects=["last_active_drawing"], key=f"ecds-map-{st.session_state.map_epoch}")
        drawn = output.get("last_active_drawing") if output else None
        if drawn and drawn.get("geometry"):
            signature = json.dumps(drawn["geometry"], sort_keys=True)
            if signature != st.session_state.last_drawing_signature:
                st.session_state.last_drawing_signature = signature
                try:
                    accepted = validate_aoi(drawn["geometry"])
                    st.session_state.accepted_aoi = accepted
                    st.session_state.aoi_origin = "Drawn on map"
                    st.rerun()
                except AOIError as exc:
                    st.error(f"Drawn AOI rejected: {exc}")
        st.caption("Draw one AOI using the toolbar. Satellite tiles load from an external public map service. No police data are used.")

    st.divider()
    k1, k2, k3 = st.columns(3)
    k1.metric("Detected Sites", "—")
    k2.metric("Protected Areas", "—")
    k3.metric("Disturbed Area", "—")
    st.subheader("Candidate Results")
    st.dataframe([], column_config={"Rank":"Rank", "Location":"Location", "Area (ha)":"Area (ha)",
                                    "Change severity":"Change severity", "Protected status":"Protected status",
                                    "Review status":"Review status"}, use_container_width=True)
    st.caption("Results will appear after detection is implemented and executed in Increment 2.")

with candidates_tab:
    st.subheader("Candidate Intelligence")
    st.info("No detections yet. Candidate ranking, map-linked review and analyst status are reserved for subsequent increments.")
    st.dataframe([], use_container_width=True)

with analytics_tab:
    st.subheader("Spatial Analytics")
    st.info("No analysis results. Candidate distributions and change statistics will appear after the detection engine is connected.")

with reports_tab:
    st.subheader("Reports & Data")
    if st.session_state.accepted_aoi:
        st.download_button(
            "Download accepted AOI (GeoJSON)",
            data=json.dumps({"type":"FeatureCollection","features":[{"type":"Feature", "properties":{
                "area_ha":st.session_state.accepted_aoi["area_ha"]},
                "geometry":st.session_state.accepted_aoi["geometry"]}]}, indent=2),
            file_name="ecds_accepted_aoi.geojson", mime="application/geo+json"
        )
    settings = {"application":"ECDS", "increment":1, "analysis_executed":False,
                "reference_period":[before_start.isoformat(),before_end.isoformat()],
                "comparison_period":[after_start.isoformat(),after_end.isoformat()],
                "thresholds":{"ndvi_decrease":ndvi_drop, "bsi_increase":bsi_rise,
                              "nbr_decrease":nbr_drop, "min_patch_ha":min_patch,
                              "cloud_score_clear_threshold":cloud_score},
                "aoi_area_ha":st.session_state.accepted_aoi["area_ha"] if st.session_state.accepted_aoi else None}
    st.download_button("Download configuration (JSON)", json.dumps(settings,indent=2),
                       file_name="ecds_configuration.json",mime="application/json")
    st.caption("Detection products and analytical reports will be enabled after the underlying processing exists.")

st.divider()
st.caption("ECDS · Environmental change screening prototype · Detected changes are leads for analyst review, never proof of an offence.")
