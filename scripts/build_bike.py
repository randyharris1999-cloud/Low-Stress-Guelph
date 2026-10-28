"""Low-Stress Guelph: build a cycling network with a Level of Traffic Stress (LTS 1-4)
for every segment, signal-aware crossings, and grades from an elevation grid.

Inputs: City of Guelph StreetCentrelines, Bike Facilities, Trails, Street Intersections;
AWS Terrain Tiles (terrarium, z14) stitched into elev_z14.npy (decimetres)."""
import json, math, collections, os
import numpy as np

U = "/mnt/user-data/uploads/City of Guelph Data/"
B = U + "bike/"
OUT = "/home/claude/bike/app/data/"
os.makedirs(OUT, exist_ok=True)

LAT0, LON0 = 43.54, -80.25
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110574
def proj(lon, lat): return ((lon - LON0) * KX, (lat - LAT0) * KY)
def unproj(x, y): return (x / KX + LON0, y / KY + LAT0)
E5 = lambda v: round(v * 1e5)

# ---------------- elevation (bilinear on the z14 grid) ----------------
EL = np.load(B + "elev_z14.npy").astype(np.float32) / 10.0
TX0, TY0, Z = 4535, 5982, 14
def elev(lon, lat):
    n = 2 ** Z * 256
    px = (lon + 180) / 360 * n - TX0 * 256
    s = math.sin(math.radians(lat)); py = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n - TY0 * 256
    x0, y0 = int(px), int(py); fx, fy = px - x0, py - y0
    a = EL[y0, x0]; b = EL[y0, x0 + 1]; c = EL[y0 + 1, x0]; d = EL[y0 + 1, x0 + 1]
    return float(a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)

# ---------------- input lines with attributes ----------------
# attr tuple: (kind, roadclass, speed, lanes, facility, surface, name)
lines = []   # (attr, [(x,y)...], oneway)  oneway: 0 both, 1 forward only, -1 backward only
streets = json.load(open(U + "StreetCentrelines.geojson"))["features"]
for f in streets:
    p = f["properties"]; cls = p.get("ROADCLASS") or "Local"
    if cls in ("Expressway", "Ramp") or p.get("STATUS") == "Draft": continue
    pts = [proj(*c[:2]) for c in f["geometry"]["coordinates"]]
    ow = {"FT": 1, "TF": -1}.get(p.get("ONEWAY"), 0)
    lines.append((["road", cls, p.get("SPEED") or 40, p.get("LANES") or 2, "", "", (p.get("STREET") or "").strip(), 1 if p.get("SEGTYPE") in ("Bridge", "Overpass") else 0], pts, ow))

bf = json.load(open(B + "bike_facilities.geojson"))["features"]
onroad = []   # (type, buffer, [(x,y)...])
for f in bf:
    p = f["properties"]
    if p.get("STATUS") != "In Service" or not f.get("geometry"): continue
    pts = [proj(*c[:2]) for c in f["geometry"]["coordinates"]]
    t = p.get("FACILITYTYPE") or ""
    if p.get("ONROAD") == "No" or t in ("MUP",):
        lines.append((["path", "MUP" if t == "MUP" else t, 0, 0, t, "Asphalt", (p.get("STREETNAME") or "").strip(), 0], pts, 0))
    elif t not in ("Left-Turn Curb Cut",):
        onroad.append((t, p.get("BUFFERTYPE") or "None", pts))

trails = json.load(open(B + "trails_full.geojson"))["features"]
for f in trails:
    g = f["geometry"]
    if not g: continue
    parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
    p = f["properties"]
    for part in parts:
        lines.append((["trail", "Trail", 0, 0, "", (p.get("Surface_Type") or "").title(), (p.get("Trail_Name") or "").strip().title(), 0], [proj(*c[:2]) for c in part], 0))
print("lines", len(lines), "on-road facilities", len(onroad))

# ---------------- on-road facilities -> street lines (by proximity + direction) ----------------
fac_rank = {"Cycle Track": 5, "Bike Lane - Green": 4, "Bike Lane": 4, "Bike Lane - Intersection": 4, "Contraflow": 3, "Crossride": 2, "Signed Route": 1, "Other": 1}
fgrid = collections.defaultdict(list)
fsegs = []
for t, buf, pts in onroad:
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        k = len(fsegs); fsegs.append((x1, y1, x2, y2, t, buf))
        for gx in range(int(min(x1, x2) // 40), int(max(x1, x2) // 40) + 1):
            for gy in range(int(min(y1, y2) // 40), int(max(y1, y2) // 40) + 1): fgrid[(gx, gy)].append(k)
def segd(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)
matched = 0
for ln in lines:
    attr, pts, ow = ln
    if attr[0] != "road": continue
    L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    if L < 1: continue
    votes = collections.Counter(); n = 0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        seglen = math.hypot(x2 - x1, y2 - y1); steps = max(1, int(seglen // 10))
        for s in range(steps):
            t_ = (s + 0.5) / steps; px, py = x1 + (x2 - x1) * t_, y1 + (y2 - y1) * t_; n += 1
            best = None
            for k in fgrid.get((int(px // 40), int(py // 40)), ()):
                fx1, fy1, fx2, fy2, ft, fb = fsegs[k]
                d = segd(px, py, fx1, fy1, fx2, fy2)
                if d > 14: continue
                # parallel check
                a1 = math.atan2(y2 - y1, x2 - x1); a2 = math.atan2(fy2 - fy1, fx2 - fx1); da = abs((a1 - a2 + math.pi / 2) % math.pi - math.pi / 2)
                if da > 0.5: continue
                if not best or fac_rank.get(ft, 0) > fac_rank.get(best[0], 0): best = (ft, fb)
            if best: votes[best] += 1
    if votes:
        (ft, fb), c = votes.most_common(1)[0]
        if c >= 0.5 * n:
            attr[4] = ft; attr[5] = fb; matched += 1
print("streets with an on-road facility", matched)

# ---------------- level of traffic stress ----------------
def lts(attr):
    kind, cls, speed, lanes, fac, extra, name = attr[:7]
    if kind in ("trail", "path"): return 1
    speed = speed or 40; lanes = lanes or 2
    if fac == "Cycle Track" or (fac.startswith("Bike Lane") and extra in ("Curbed", "Barrier and Bollard", "Bollard", "Rolled Curb")):
        return 1 if speed <= 50 else 2
    if fac.startswith("Bike Lane") or fac == "Contraflow":
        base = 2 if (speed <= 50 and lanes <= 2) else 3 if (speed <= 60 and lanes <= 4) else 4
        if extra in ("Painted", "Rumble Strip"): base = max(2, base - 1)
        return base
    # mixed traffic (signed routes are still mixed traffic)
    if cls in ("Local", "Private", "University"):
        return 1 if speed <= 40 and lanes <= 2 else 2 if speed <= 50 else 3
    if cls == "Collector":
        return 2 if speed <= 40 and lanes <= 2 else 3 if speed <= 50 and lanes <= 2 else 4
    # arterials
    return 3 if (speed <= 40 and lanes <= 2) else 4

# ---------------- vertex graph (1 m snapping, densified) ----------------
def densify(pts, step=40):
    out = [pts[0]]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        d = math.hypot(x2 - x1, y2 - y1); n = int(d // step)
        for i in range(1, n + 1):
            t = i / (n + 1); out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
        out.append((x2, y2))
    return out
key_of = {}; vx = []; vy = []
def vid(x, y):
    k = (round(x), round(y)); i = key_of.get(k)
    if i is None: i = len(vx); key_of[k] = i; vx.append(x); vy.append(y)
    return i
ATTRS = []; attr_idx = {}
def aid(attr, l):
    key = (tuple(attr), l); i = attr_idx.get(key)
    if i is None: i = len(ATTRS); attr_idx[key] = i; ATTRS.append(key)
    return i
adj = collections.defaultdict(dict)   # v -> {w: (len, attr_id, dir)} dir: 0 both, 1 v->w only, -1 w->v only
line_of_v = collections.defaultdict(set); endpoints = []
for li, (attr, pts, ow) in enumerate(lines):
    ids = [vid(x, y) for x, y in densify(pts)]
    ids = [v for i, v in enumerate(ids) if i == 0 or v != ids[i - 1]]
    if len(ids) < 2: continue
    a_ = aid(attr, lts(attr))
    for a, b in zip(ids, ids[1:]):
        d = math.hypot(vx[a] - vx[b], vy[a] - vy[b])
        prev = adj[a].get(b)
        if prev and ATTRS[prev[1]][1] <= ATTRS[a_][1]: continue   # keep the lower-stress of overlapping lines
        adj[a][b] = (d, a_, ow); adj[b][a] = (d, a_, -ow)
    for v in ids: line_of_v[v].add(li)
    endpoints += [ids[0], ids[-1]]
print("vertices", len(vx))

# connect dangling ends (paths that stop just short of a road) with short connectors
CELL = 30
grid = collections.defaultdict(list)
for i in range(len(vx)): grid[(int(vx[i] // CELL), int(vy[i] // CELL))].append(i)
LINK = aid(["link", "Link", 0, 0, "", "", "", 0], 1)
added = 0
for v in set(endpoints):
    if len(adj[v]) != 1: continue
    best = None
    for gx in range(int(vx[v] // CELL) - 1, int(vx[v] // CELL) + 2):
        for gy in range(int(vy[v] // CELL) - 1, int(vy[v] // CELL) + 2):
            for j in grid.get((gx, gy), ()):
                if j == v or j in adj[v] or (line_of_v[j] & line_of_v[v]): continue
                d = math.hypot(vx[j] - vx[v], vy[j] - vy[v])
                if d <= 20 and (best is None or d < best[1]): best = (j, d)
    if best:
        j, d = best; adj[v][j] = (max(d, 1), LINK, 0); adj[j][v] = (max(d, 1), LINK, 0); added += 1
print("connectors", added)

# node at-grade crossings (paths crossing roads, roads crossing roads) that share no vertex
vx = list(vx); vy = list(vy)
segs = [(a, b) for a in adj for b in adj[a] if a < b]
sgrid = collections.defaultdict(list)
for i, (a, b) in enumerate(segs):
    for gx in range(int(min(vx[a], vx[b]) // 50), int(max(vx[a], vx[b]) // 50) + 1):
        for gy in range(int(min(vy[a], vy[b]) // 50), int(max(vy[a], vy[b]) // 50) + 1): sgrid[(gx, gy)].append(i)
def orient(a, b, c): return (vx[b] - vx[a]) * (vy[c] - vy[a]) - (vy[b] - vy[a]) * (vx[c] - vx[a])
splits = collections.defaultdict(list); seen = set()
for ids in sgrid.values():
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            i, j = ids[x], ids[y]
            if (i, j) in seen: continue
            seen.add((i, j)); (a, b), (c, d) = segs[i], segs[j]
            if len({a, b, c, d}) < 4: continue
            d1, d2, d3, d4 = orient(c, d, a), orient(c, d, b), orient(a, b, c), orient(a, b, d)
            if d1 * d2 < 0 and d3 * d4 < 0:
                t = d1 / (d1 - d2); nv = len(vx); vx.append(vx[a] + t * (vx[b] - vx[a])); vy.append(vy[a] + t * (vy[b] - vy[a]))
                splits[i].append((t, nv)); splits[j].append((d3 / (d3 - d4), nv))
for i, lst in splits.items():
    a, b = segs[i]; d, at, ow = adj[a][b]
    del adj[a][b]; del adj[b][a]
    chain = [a] + [v for _, v in sorted(lst)] + [b]
    for p, q in zip(chain, chain[1:]):
        L = max(math.hypot(vx[p] - vx[q], vy[p] - vy[q]), 0.1); adj[p][q] = (L, at, ow); adj[q][p] = (L, at, -ow)
print("crossings noded", sum(len(l) for l in splits.values()) // 2)

# largest component only
comp = {}; sizes = []
for s in list(adj):
    if s in comp: continue
    st = [s]; comp[s] = len(sizes); n = 0
    while st:
        u = st.pop(); n += 1
        for w in adj[u]:
            if w not in comp: comp[w] = len(sizes); st.append(w)
    sizes.append(n)
big = int(np.argmax(sizes)); keep = {v for v, c in comp.items() if c == big}
print("components", len(sizes), "largest", sizes[big])

# ---------------- collapse into edges; split where attributes change or every ~80 m ----------------
def is_key(v):
    if v not in keep: return False
    nb = list(adj[v])
    if len(nb) != 2: return True
    (a1, a2) = (adj[v][nb[0]], adj[v][nb[1]])
    return a1[1] != a2[1]
keyset = {v for v in keep if is_key(v)}
done = set(); edges = []
def walk(a, b):
    path = [a, b]; L = adj[a][b][0]; at = adj[a][b][1]; ow = adj[a][b][2]; prev, cur = a, b
    while cur not in keyset and L < 80:
        nxt = [w for w in adj[cur] if w != prev][0]; L += adj[cur][nxt][0]; path.append(nxt); prev, cur = cur, nxt
    keyset.add(cur)
    return path, L, at, ow
pending = list(keyset)
while pending:
    a = pending.pop()
    for b in list(adj[a]):
        if b not in keep or (a, b) in done: continue
        path, L, at, ow = walk(a, b)
        for p, q in zip(path, path[1:]): done.add((p, q)); done.add((q, p))
        edges.append((path, L, at, ow))
        if path[-1] not in pending: pending.append(path[-1])
for v in keep:   # pure loops
    for b in adj[v]:
        if (v, b) not in done:
            keyset.add(v); path, L, at, ow = walk(v, b)
            for p, q in zip(path, path[1:]): done.add((p, q)); done.add((q, p))
            edges.append((path, L, at, ow))
nodes = sorted({e[0][0] for e in edges} | {e[0][-1] for e in edges}); nidx = {v: i for i, v in enumerate(nodes)}
print("nodes", len(nodes), "edges", len(edges))

# ---------------- elevation per vertex -> climb per edge, max grade ----------------
velev = {}
def ev(v):
    if v not in velev: velev[v] = elev(*unproj(vx[v], vy[v]))
    return velev[v]
eout = []
for path, L, at, ow in edges:
    # resample every ~15 m for smoother grades on the 30 m DEM
    zs = []; dist = [0.0]
    for p, q in zip(path, path[1:]): dist.append(dist[-1] + math.hypot(vx[q] - vx[p], vy[q] - vy[p]))
    zs = [ev(v) for v in path]
    if ATTRS[at][0][7]: zs = [zs[0] + (zs[-1] - zs[0]) * (dd / max(dist[-1], 1)) for dd in dist]   # bridges ride level over the valley
    up = sum(max(0, b - a) for a, b in zip(zs, zs[1:])); down = sum(max(0, a - b) for a, b in zip(zs, zs[1:]))
    gmax = 0.0
    for i in range(len(path)):     # steepest ~40 m stretch
        for j in range(i + 1, len(path)):
            if dist[j] - dist[i] >= 30:
                gmax = max(gmax, abs(zs[j] - zs[i]) / (dist[j] - dist[i])); break
    if L >= 10 and gmax == 0: gmax = abs(zs[-1] - zs[0]) / max(L, 1)
    eout.append((up, down, gmax, zs[0], zs[-1]))

# ---------------- signals and crossings ----------------
inter = json.load(open(B + "intersections.geojson"))["features"]
NX = np.array([vx[v] for v in nodes]); NY = np.array([vy[v] for v in nodes])
ngrid = collections.defaultdict(list)
for i in range(len(nodes)): ngrid[(int(NX[i] // 40), int(NY[i] // 40))].append(i)
signal = set()
for f in inter:
    if f["properties"].get("SIGNALIZED") != "Yes" or not f.get("geometry"): continue
    x, y = proj(*f["geometry"]["coordinates"][:2])
    for gx in range(int(x // 40) - 1, int(x // 40) + 2):
        for gy in range(int(y // 40) - 1, int(y // 40) + 2):
            for i in ngrid.get((gx, gy), ()):
                if math.hypot(NX[i] - x, NY[i] - y) <= 30: signal.add(i)
inc = collections.defaultdict(list)
for ei, (path, L, at, ow) in enumerate(edges):
    inc[nidx[path[0]]].append(ei); inc[nidx[path[-1]]].append(ei)
# a node is a "busy crossing" when a quiet edge (LTS<=2) meets a road edge of LTS>=3 and there is no signal
crossing = {}
for n, es in inc.items():
    if n in signal: continue
    hi = [ATTRS[edges[e][2]][1] for e in es if ATTRS[edges[e][2]][0][0] == "road" and ATTRS[edges[e][2]][1] >= 3]
    lo = [e for e in es if ATTRS[edges[e][2]][1] <= 2]
    if hi and len(lo) >= 1 and len(es) >= 3: crossing[n] = max(hi)
print("signals matched", len(signal), "unsignalized busy crossings", len(crossing))

# ---------------- write ----------------
def ll(x, y): lon, lat = unproj(x, y); return [E5(lon), E5(lat)]
gn = []
for v in nodes: gn += ll(vx[v], vy[v])
# attribute table for the client
A = [{"kind": a[0][0], "cls": a[0][1], "speed": a[0][2], "lanes": a[0][3], "fac": a[0][4], "x": a[0][5], "name": a[0][6], "bridge": a[0][7], "lts": a[1]} for a in ATTRS]
ge = []; geo = []; elv = []
for (path, L, at, ow), (up, down, gmax, z0, z1) in zip(edges, eout):
    ge += [nidx[path[0]], nidx[path[-1]], round(L, 1), at, ow]
    elv += [round(up, 1), round(down, 1), round(gmax * 1000), round(z0, 1), round(z1, 1)]
    pts = [path[0]]
    for v in path[1:-1]:
        if math.hypot(vx[v] - vx[pts[-1]], vy[v] - vy[pts[-1]]) >= 6: pts.append(v)
    pts.append(path[-1]); flat = []
    for v in pts[1:-1]: flat += ll(vx[v], vy[v])
    geo.append(flat)
json.dump({"nodes": gn, "edges": ge, "elev": elv, "geom": geo, "attrs": A, "signals": sorted(signal), "crossings": [[n, c] for n, c in sorted(crossing.items())]},
          open(OUT + "network.json", "w"), separators=(",", ":"))
# addresses snapped to this network
addrs = json.load(open("/home/claude/guelph/app/data/addresses.json"))
an = []; ac = []
for lon5, lat5 in zip(addrs["lon"], addrs["lat"]):
    x, y = proj(lon5 / 1e5, lat5 / 1e5); best = (0, 1e18)
    for r in range(1, 6):
        for gx in range(int(x // 40) - r, int(x // 40) + r + 1):
            for gy in range(int(y // 40) - r, int(y // 40) + r + 1):
                for i in ngrid.get((gx, gy), ()):
                    d = (NX[i] - x) ** 2 + (NY[i] - y) ** 2
                    if d < best[1]: best = (i, d)
        if best[1] < 1e18: break
    an.append(best[0]); ac.append(round(math.sqrt(best[1])))
json.dump({"text": addrs["text"], "lon": addrs["lon"], "lat": addrs["lat"], "node": an, "conn": ac}, open(OUT + "addresses.json", "w"), separators=(",", ":"))
tot = collections.Counter();
for path, L, at, ow in edges: tot[ATTRS[at][1]] += L
print("km by LTS", {k: round(v / 1000, 1) for k, v in sorted(tot.items())})
for fn in os.listdir(OUT): print(fn, os.path.getsize(OUT + fn) // 1024, "KB")
