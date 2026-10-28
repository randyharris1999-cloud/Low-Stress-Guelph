# Low-Stress Guelph

A bike map of Guelph, Ontario that rates every street and path for **traffic stress** and **hills**, and plans calm routes between any two addresses.

- **Stress map:** every segment rated with the Level of Traffic Stress (LTS) method, from 1 (calm enough for kids) to 4 (only the bold). It uses each street's speed limit, lane count and road type, plus the City's bike facility data: painted lanes, buffers, curbs, cycle tracks and multi-use paths.
- **Busy crossings:** places where a quiet route has to cross a busy road with no traffic signal are marked, and the planner avoids them.
- **Route planner:** search two addresses or tap the map. You get the calmest route alongside the fastest, with distance, time, climbing, the share of low-stress riding, busy crossings, an elevation profile and the streets along the way. Options are three comfort levels, avoid hills, and paved only.
- **Hills:** the steepest stretch of every segment, from Ontario's 0.5 m LIDAR ground model, with shaded relief on the map. Bridges are levelled so they don't show the valley below.
- **Islands:** the connected low-stress networks and the gaps between them. Today the largest island reaches 37% of Guelph's addresses.
- **Bike lanes:** Guelph's cycling infrastructure by type.

## Publish on GitHub Pages
1. Create a new public repository, for example `Low-Stress-Guelph`.
2. Open this folder, select **everything inside it** and drag it into GitHub's "uploading an existing file" page. Don't drag the folder itself. Commit.
3. Go to **Settings > Pages**, choose **Deploy from a branch**, then `main` and `/ (root)`, and save.
4. Your site will be at `https://randyharris1999-cloud.github.io/Low-Stress-Guelph/`.

No relay or setup is needed. Everything the app uses is in `data/`.

## Test locally
```
python -m http.server 8000
```
Then open http://localhost:8000.

## Data
| Data | Source |
|---|---|
| Street centrelines (speed, lanes, class, one-way), bike facilities, trails, signalized intersections, addresses, buildings, parks, watercourses | City of Guelph Open Data |
| Elevation | Ontario Digital Terrain Model (LIDAR-derived), 0.5 m, flown 2018, Ontario Ministry of Natural Resources. Resampled to a city-wide grid in QGIS |

`scripts/build_bike.py` builds `data/network.json` from those layers. The file paths at the top point to where it first ran.

## Notes
- Ratings are estimates from City data. Parked cars, traffic volumes and pavement condition aren't in the data. Always ride to the conditions you find.
- The LIDAR was flown in 2018, so streets and subdivisions graded since then may show the old ground.

## Rebuilding the hills
`scripts/build_lidar.py` rewrites the climbs and grades in `data/network.json` and makes `data/hillshade.jpg` from the city-wide LIDAR grid (`guelph_dem_6m_3857.tif` in `City of Guelph Data\LIDAR_derived`, made in QGIS; the Guelph Transit Planner README has the steps):
```
python scripts/build_lidar.py "path/to/guelph_dem_6m_3857.tif"
python scripts/build_html.py
```
Run it again after rebuilding the network with `scripts/build_bike.py`, which still reads the old 30 m grid.

An independent project built on City of Guelph open data. Not an official City of Guelph service.
