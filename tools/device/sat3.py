import sys, os, json, glob
sys.path.insert(0, "/data/openpilot")
from tools.lib.logreader import LogReader
prefix = sys.argv[1]
ps = sorted(glob.glob(prefix + "*"), key=lambda p: int(p.split("--")[-1]) if p.split("--")[-1].isdigit() else -1)
out = []
for name in ps:
    f = name + "/qlog.zst"
    if not os.path.exists(f): continue
    cs = None; n = 0; n_lat = 0; sat = 0; sat_lat = 0; sat_lat_low = 0; sat_lat_big = 0
    tau_lat = 0.0; tau_lat_n = 0; vmax = 0.0; lat_v = []
    for m in LogReader(f):
        w = m.which()
        if w == "carState":
            cs = m.carState
            if abs(cs.vEgo) > vmax: vmax = abs(cs.vEgo)
        elif w == "carControl":
            n += 1
            try:
                lat = bool(m.carControl.latActive)
                t = abs(m.carControl.actuators.torque)
            except Exception:
                continue
            if lat:
                n_lat += 1; tau_lat += t; tau_lat_n += 1
                if cs is not None: lat_v.append(abs(cs.vEgo))
                if t > 0.95:
                    sat_lat += 1
                    if cs is not None:
                        if abs(cs.vEgo) < 5: sat_lat_low += 1
                        if abs(getattr(cs, "steeringAngleDeg", 0.0)) > 25: sat_lat_big += 1
            if t > 0.95: sat += 1
    lat_v.sort()
    out.append({"seg": int(name.split("--")[-1]), "vmax": round(vmax, 1), "cc": n, "lat": n_lat,
                "lat_pct": round(100.0 * n_lat / n, 1) if n else 0,
                "sat": sat, "sat_lat": sat_lat, "sat_lat_low": sat_lat_low, "sat_lat_big": sat_lat_big,
                "tau_lat": round(tau_lat / tau_lat_n, 3) if tau_lat_n else 0,
                "lat_v_med": round(lat_v[len(lat_v) // 2], 1) if lat_v else 0})
print(json.dumps(out, ensure_ascii=False))