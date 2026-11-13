# ECDS — Environmental Crime Detection System

## Increment 1: Locked Streamlit interface

An analyst-facing **interface and AOI-validation prototype** built from the existing Förändringsradar GEE workflow. **It does not run satellite imagery detection yet.** The four approved tabs, configuration sidebar, central map and empty results structure are present. Detection integration is Increment 2.

### Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Publish using GitHub + Streamlit Community Cloud

1. Create a GitHub repository named `ECDS` and upload the **contents** of this folder, including `.streamlit/config.toml` and `data/sweden_boundary.geojson`.
2. In Streamlit Community Cloud, select the repository, branch and `app.py` entry point; deploy.
3. No Earth Engine credentials are needed for Increment 1. Do not upload credentials or sensitive information to GitHub.

### Implemented

- Four approved tabs: Detection Workspace, Candidate Intelligence, Spatial Analytics, Reports & Data.
- Analysis sidebar with municipality **navigation**, AOI draw / GeoJSON polygon upload, two comparison periods and the original spectral defaults.
- Draw Polygon and Rectangle tools; accepted AOI outline and map controls.
- **Hard AOI area validation**: one Polygon, 50–5,000 ha, EPSG:4326, geodesic area. Rejected AOIs are never accepted.
- Coarse preliminary Sweden boundary screening (bundled Natural Earth low-resolution outline); not authoritative municipal/border validation.
- GeoJSON AOI and analysis-configuration downloads.
- Map satellite tiles use Esri World Imagery (external public tiles); OSM alternative.

### Deliberately not implemented

- No GEE authentication or satellite detection (Run Detection disabled).
- Municipality selection navigates the map; **it does not automatically select municipal geometry**, since most municipalities exceed the 50 km² limit.
- No protected-area analysis, felling notifications, candidate scores, analyst review storage, database or reports. Those require processing and authoritative datasets in later increments.
- The boundary is low-resolution and can reject valid near-coast AOIs or pass small border discrepancies; replace with a licensed authoritative Swedish boundary before operational use.

### Safety and data handling

Use public data only. Do not upload case records, personally identifying information or confidential policing data to this publicly hosted proof of concept. The application screens physical land disturbances and cannot establish criminal activity.
