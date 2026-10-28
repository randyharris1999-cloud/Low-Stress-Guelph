"""Low-Stress Guelph: replace the 30 m hills in data/network.json with Ontario's 0.5 m LIDAR ground model,
and make data/hillshade.jpg for the map.

Input: an elevation grid in Web Mercator (EPSG:3857), float32 GeoTIFF, made in QGIS from the LIDAR tiles
(same grid the Guelph Transit Planner uses; see README "Rebuilding the hills").

For every segment it rewrites the five elevation numbers the app reads: climb, descent, steepest stretch
(per mille, over 30 m or more), and the elevation at each end. Bridges flagged in the City data ride level
from end to end, as before. Other dips narrower than about 80 m (trail bridges and culverts the City data
doesn't flag) are filled, because the ground model has no bridge decks.

Run from the repo folder:  python scripts/build_lidar.py path/to/guelph_dem_6m_3857.tif
"""
import json, math, os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = 6378137.0
mx = lambda lon: np.radians(lon) * R
my = lambda lat: R * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))

def main(dem_path):
    im = Image.open(dem_path); dem = np.array(im, dtype=np.float32); t = im.tag_v2
    SX, SY = t[33550][0], t[33550][1]; X0, Y0 = t[33922][3], t[33922][4]
    dem[(dem < 100) | (dem > 600)] = np.nan
    H, W = dem.shape; fill = np.where(np.isnan(dem), np.nanmedian(dem), dem)
    def sample(x, y):
        c = (x - X0) / SX - 0.5; r = (Y0 - y) / SY - 0.5
        c0 = np.clip(np.floor(c).astype(int), 0, W - 2); r0 = np.clip(np.floor(r).astype(int), 0, H - 2)
        fc = np.clip(c - c0, 0, 1); fr = np.clip(r - r0, 0, 1)
        return (fill[r0, c0] * (1 - fc) * (1 - fr) + fill[r0, c0 + 1] * fc * (1 - fr) + fill[r0 + 1, c0] * (1 - fc) * fr + fill[r0 + 1, c0 + 1] * fc * fr)

    path = os.path.join(ROOT, "data", "network.json"); g = json.load(open(path))
    nodes = np.array(g["nodes"], dtype=np.float64).reshape(-1, 2) / 1e5
    E = len(g["edges"]) // 5; old = np.array(g["elev"]).reshape(-1, 5); new = []
    STEP = 5.0
    for e in range(E):
        a, b, L, at = g["edges"][5 * e], g["edges"][5 * e + 1], g["edges"][5 * e + 2], g["edges"][5 * e + 3]
        fl = g["geom"][e]
        pts = np.array([nodes[a]] + [np.array(fl[j:j + 2]) / 1e5 for j in range(0, len(fl), 2)] + [nodes[b]])
        px, py = mx(pts[:, 0]), my(pts[:, 1]); k = math.cos(math.radians(pts[:, 1].mean()))
        cum = np.concatenate([[0], np.cumsum(np.hypot(np.diff(px), np.diff(py)) * k)]); tot = cum[-1]
        n = max(2, int(math.ceil(tot / STEP)) + 1); s = np.linspace(0, max(tot, 0.01), n)
        z = sample(np.interp(s, cum, px), np.interp(s, cum, py))
        if g["attrs"][at]["bridge"]:
            z = z[0] + (z[-1] - z[0]) * s / max(s[-1], 1)                    # flagged bridges ride level end to end
        elif n > 2:
            w = max(1, int(40 / (s[-1] / (n - 1))))                          # fill dips under ~80 m wide
            zl = np.array([z[max(0, i - w):i + 1].max() for i in range(n)]); zr = np.array([z[i:i + w + 1].max() for i in range(n)])
            z = np.maximum(z, np.minimum(zl, zr))
            z = np.convolve(np.pad(z, 1, mode="edge"), np.ones(3) / 3, mode="valid")   # ~10 m smoothing of LIDAR noise
        dz = np.diff(z); up = dz[dz > 0].sum(); down = -dz[dz < 0].sum()
        # steepest stretch of 30 m or more (same rule as before)
        gmax = 0.0
        for i in range(n):
            j = np.searchsorted(s, s[i] + 30)
            if j >= n: break
            gmax = max(gmax, abs(z[j] - z[i]) / (s[j] - s[i]))
        if L >= 10 and gmax == 0: gmax = abs(z[-1] - z[0]) / max(L, 1)
        new.append([round(float(up), 1), round(float(down), 1), int(round(gmax * 1000)), round(float(z[0]), 1), round(float(z[-1]), 1)])
    new = np.array(new)
    for lbl, o, nw in [("climb km", old[:, 0].sum() / 1000, new[:, 0].sum() / 1000)]: print(lbl, "30 m:", round(o, 1), "LIDAR:", round(nw, 1))
    print("steepest stretch per mille p50/p90/p99/max  30 m:", np.percentile(old[:, 2], [50, 90, 99, 100]), " LIDAR:", np.percentile(new[:, 2], [50, 90, 99, 100]))
    g["elev"] = [v for row in new.tolist() for v in row]
    g["elev"] = [int(v) if float(v).is_integer() else v for v in g["elev"]]
    json.dump(g, open(path, "w"), separators=(",", ":"))

    # hillshade (z-factor 2, sun from the north-west), 128 = flat
    k = math.cos(math.radians(43.53)); gy, gx = np.gradient(fill, SY * k, SX * k)
    az, alt = math.radians(315), math.radians(45)
    sl = np.arctan(2.0 * np.hypot(gx, gy)); asp = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(sl) + np.cos(alt) * np.sin(sl) * np.cos(az - asp - math.pi / 2)
    enc = np.clip(128 + (hs - math.sin(alt)) * 300, 0, 255); enc[np.isnan(dem)] = 128
    img = Image.fromarray(enc.astype(np.uint8), "L"); img = img.resize((1800, round(H * 1800 / W)), Image.LANCZOS)
    img.save(os.path.join(ROOT, "data", "hillshade.jpg"), quality=82, optimize=True, progressive=True)
    lon = lambda x: math.degrees(x / R); lat = lambda y: math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    print("hillshade bounds [W,S,E,N]:", [round(lon(X0), 6), round(lat(Y0 - SY * H), 6), round(lon(X0 + SX * W), 6), round(lat(Y0), 6)])

if __name__ == "__main__":
    main(sys.argv[1])
