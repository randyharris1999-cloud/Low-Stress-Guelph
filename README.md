# Low-Stress Guelph

A bike map of Guelph, Ontario that rates every street and path for **traffic stress** and **hills**, and plans calm routes between any two addresses.

- **Stress map:** every segment rated with the Level of Traffic Stress (LTS) method, from 1 (calm enough for kids) to 4 (only the bold). It uses each street's speed limit, lane count and road type, plus the City's bike facility data: painted lanes, buffers, curbs, cycle tracks and multi-use paths.
- **Busy crossings:** places where a quiet route has to cross a busy road with no traffic signal are marked, and the planner avoids them.
- **Route planner:** search two addresses or tap the map. You get the calmest route alongside the fastest, with distance, time, climbing, the share of low-stress riding, busy crossings, an elevation profile and the streets along the way. Options are three comfort levels, avoid hills, and paved only.
- **Hills:** the steepest stretch of every segment, from a 30 m elevation model. Bridges are levelled so they don't show the valley below.
- **Islands:** the connected low-stress networks and the gaps between them. Today the largest island reaches 37% of Guelph's addresses.
- **Bike lanes:** Guelph's cycling infrastructure by type.

## Data
| Data | Source |
|---|---|
| Street centrelines (speed, lanes, class, one-way), bike facilities, trails, signalized intersections, addresses, buildings, parks, watercourses | City of Guelph Open Data |
| Elevation | AWS Terrain Tiles (Mapzen), derived from Canadian government elevation data, ~30 m |

`scripts/build_bike.py` builds `data/network.json` from those layers. The file paths at the top point to where it first ran.

## Notes
- Ratings are estimates from City data. Parked cars, traffic volumes and pavement condition aren't in the data. Always ride to the conditions you find.
- The 30 m elevation model smooths short, steep blocks. Ontario's LiDAR terrain model (Ontario GeoHub) would sharpen the grades.

An independent project built on City of Guelph open data. Not an official City of Guelph service.
