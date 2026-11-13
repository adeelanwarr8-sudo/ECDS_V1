# ECDS — Environmental Crime Detection System

## Increment 2: Satellite change detection (Streamlit + Earth Engine)

This project retains the **locked Increment 1 UI**: four tabs, left analysis configuration, central interactive GIS map, candidate table, analytics and export. It now runs the original Sentinel-2 land-change detection pipeline using the Earth Engine Python API.

**This is a research/prototype screening system, not a system for confirming crimes or evaluating individuals.** Detection results are land-disturbance leads requiring independent analyst review. No police-sensitive data should be uploaded to Google Earth Engine or Streamlit Community Cloud.

### What works

- GeoJSON or drawn-polygon AOI, with **50–5,000 ha** guardrails and preliminary Sweden-only screening
- Comparison dates **2016–2025 inclusive** (default 2024 vs 2025 summer)
- Cloud Score+-masked Sentinel-2 median composites, NDVI/BSI/NBR comparison
- Dynamic World masking of water, cropland, built-up land, snow/ice
- 8-connected change-patch filtering; 0.25–10 ha minimum selectable patch size
- Ranked polygon candidates with area, mean ΔNDVI and transparent size × severity score
- Earth Engine map tiles: before, after, ΔNDVI and flagged pixels
- Candidate table, site inspection, statistics, GeoJSON and CSV downloads
- Valid paired imagery area indicator, scene counts and processing errors

**Not yet connected**: Swedish protected-area boundaries, forestry notifications, permits, PostGIS, persistent reviews, and calibrated detection accuracy (planned future increments). 'Protected Areas' dashboard metric therefore reads 'Not assessed'. Data export is capped at **250 ranked polygons per run** (total count still reported) to keep the Streamlit session responsive. `candidate_id` values are **within-run IDs**, not persistent references. Map tile URLs may expire; rerun detection to refresh them.

### Repository layout

Upload the **contents** of this folder to your GitHub repository root, so `app.py` is at the top level. Do not upload the ZIP or commit secrets.

```
app.py
gee_engine.py
geo_utils.py
requirements.txt
README.md
.gitignore
.streamlit/config.toml
.streamlit/secrets.toml.example
data/sweden_boundary.geojson
test_geo_utils.py
test_gee_engine.py
```

### Earth Engine prerequisites

You need a Google Cloud project registered for Earth Engine and access to Earth Engine through a service account or user identity. The Google Cloud project must have the Earth Engine API enabled and appropriate permissions. This step is **essential**: GitHub deployment by itself does not grant Earth Engine access.

For **Streamlit Community Cloud**, open the app's **Settings → Secrets** and paste your values (not into GitHub):

```toml
EE_PROJECT = "your-google-cloud-project-id"
EE_SERVICE_ACCOUNT_JSON = '''{"type":"service_account","project_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n","client_email":"...","token_uri":"https://oauth2.googleapis.com/token"}'''
```

The `EE_SERVICE_ACCOUNT_JSON` string must contain the **entire real JSON key** exactly as downloaded. An easier alternative is to copy the JSON *verbatim* between the triple single quotes. The linked Google Cloud project and service-account identity must actually have permission to use Earth Engine. Do not publish key files or screenshots containing credentials.

For **local use** you can instead run `earthengine authenticate` (or `ee.Authenticate()` interactively in a trusted Python environment) and set `EE_PROJECT` in local `.streamlit/secrets.toml`, or rely on an existing configured default Earth Engine project.

### Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Test

```bash
pip install pytest
pytest -q
```

Tests cover local AOI and parameter validation. **Live Earth Engine execution has not been run here because valid user credentials are not available.** After connecting the app, validate with a small AOI and inspect the resulting imagery and polygons.

### Validation caveats

- Scene counts indicate scene presence, not cloud-free coverage. The paired valid-area metric provides additional data-coverage context.
- The coarse Sweden boundary can reject some legitimate coastal/island AOIs or accept some near-border polygons; authoritative boundaries are a future improvement.
- The current candidate score is `area_ha × abs(mean_dNDVI)`, **not crime probability**.
- Detection scores are not yet calibrated against independent reference sites.
- The service uses external imagery and basemap providers; it is for open-data demonstration only.

## Increment 2 diagnostic update (2026-11-13)

This update preserves the locked interface, 2016–2025 study period, 50–5,000 ha AOI limits and original detection thresholds. It adds *stage-specific* server-side error reporting; no credentials or raw third-party authentication messages are displayed in the browser.

When a detection fails, the UI now displays a stage and a short **Diagnostic ID**, e.g. `Earth Engine failed at Dynamic World availability. Diagnostic ID: abc1234567`. In Streamlit Community Cloud, open **Manage app → Logs** and search for the same ID. The server-side record includes the processing stage, exception class and a filtered/truncated error message. Never share service-account JSON, credentials, access tokens, or unredacted logs with secrets.

The tracked stages are initialization/authentication; AOI geometry; Sentinel-2 scene availability; composite/index construction; Dynamic World availability; change mask; raster area reduction; vectorisation; candidate count/retrieval; and map tile generation. Authentication/permission errors may first manifest at a later Earth Engine API call because server-side expressions are lazy.

**Verification:** Python syntax compilation and 13 local unit tests passed. Live Earth Engine execution and actual browser functionality still require checking on the Streamlit deployment. No Google Cloud IAM roles were modified.
