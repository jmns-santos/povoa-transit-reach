#!/usr/bin/env python3
"""
Gera os dados do modo "Transporte Público" (data/tp/meta.json + data/tp/c/HH.json)
a partir de um GTFS normal — mesmo formato que o front-end (index.html) consome,
adaptado do motor do projeto rhein-main-transit-reach (ilyas-ku), que corre
inteiramente no browser (Connection Scan + contornos d3).

Ao contrário do coletor privado do autor original (DuckDB próprio em
frankfurt-transit-delays), aqui não há ainda:
  - fiabilidade real (atrasos/cancelamentos por paragem+linha+hora) — os
    quantis q50/q80/q90/q95 ficam a 0 (equivalente ao horário) até existir
    essa agregação a partir do histórico GTFS-RT da UNIR já em produção;
  - grelha de população real — fica a 0 (a secção "pessoas alcançadas" é
    escondida pelo front-end quando a soma da grelha é 0). Substituir por
    uma grelha do INE/Censos quando disponível (ver README).

Uso:
    python build_explore_povoa.py <gtfs> [--dia AAAAMMDD] [--fonte demo|real]
                                   [--fiabilidade ficheiro.csv] [--out ../data/tp]
"""
import argparse
import base64
import csv
import io
import os
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

# caixa geográfica: Póvoa de Varzim + Vila do Conde + margem
BOX = (41.280, -8.820, 41.470, -8.580)   # (sul, oeste, norte, este) — todo o concelho da Póvoa de Varzim (inclui Balazar/Rates, a leste) + Vila do Conde
DLAT = 0.0018                             # ~200 m
LAT0 = 41.37
DLON = round(200 / (111320 * np.cos(np.radians(LAT0))), 6)  # ~200 m a esta latitude

Q = ["q50", "q80", "q90", "q95"]
LEVELS = ["Horário", "1 em 2 dias", "4 em 5 dias", "9 em 10 dias", "19 em 20 dias"]

MODE_NAMES = {0: "Elétrico", 1: "Metro", 2: "Comboio", 3: "Autocarro", 4: "Ferry", 5: "Teleférico", 6: "Teleférico suspenso", 7: "Funicular"}

# operadora de cada paragem/viagem, a partir do prefixo que o combine_gtfs.py põe no id
# (ex. "unir_prg:bar:3" -> "unir") — só serve para colorir/legendar camadas no mapa.
OPERADORAS = {"metro": "Metro do Porto", "unir": "UNIR", "cavado": "Mov Cávado"}


def op_of(prefixed_id):
    prefix = str(prefixed_id).split("_", 1)[0]
    return prefix if prefix in OPERADORAS else "outro"


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def open_gtfs_table(src, filename):
    if os.path.isdir(src):
        path = os.path.join(src, filename)
        if not os.path.exists(path):
            return None
        return open(path, newline="", encoding="utf-8-sig")
    zf = zipfile.ZipFile(src)
    names = [n for n in zf.namelist() if n.endswith(filename)]
    if not names:
        return None
    return io.TextIOWrapper(zf.open(names[0]), encoding="utf-8-sig")


def read_table(src, filename):
    f = open_gtfs_table(src, filename)
    if f is None:
        return pd.DataFrame()
    with f:
        return pd.DataFrame(list(csv.DictReader(f)))


def hms_to_s(hms):
    h, m, s = hms.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def pick_service_ids(calendar, service_date):
    if calendar.empty:
        return None  # sem calendar.txt: aceita tudo (ex.: GTFS já filtrado)
    weekday = service_date.weekday()
    col = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][weekday]
    ymd = service_date.strftime("%Y%m%d")
    ok = calendar[(calendar[col] == "1") & (calendar["start_date"] <= ymd) & (calendar["end_date"] >= ymd)]
    return set(ok["service_id"])


def build_connections(gtfs_path, service_date):
    stops_t = read_table(gtfs_path, "stops.txt")
    routes_t = read_table(gtfs_path, "routes.txt")
    trips_t = read_table(gtfs_path, "trips.txt")
    stop_times_t = read_table(gtfs_path, "stop_times.txt")
    calendar_t = read_table(gtfs_path, "calendar.txt")

    if stops_t.empty or stop_times_t.empty:
        sys.exit("GTFS sem stops.txt/stop_times.txt legíveis.")

    service_ids = pick_service_ids(calendar_t, service_date)
    if service_ids is not None:
        trips_t = trips_t[trips_t["service_id"].isin(service_ids)]
    valid_trips = set(trips_t["trip_id"])

    route_mode = dict(zip(routes_t.get("route_id", []), routes_t.get("route_type", [])))
    route_name = dict(zip(routes_t.get("route_id", []), routes_t.get("route_short_name", routes_t.get("route_long_name", routes_t.get("route_id", [])))))
    trip_route = dict(zip(trips_t["trip_id"], trips_t.get("route_id", [])))

    st = stop_times_t[stop_times_t["trip_id"].isin(valid_trips)].copy()
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st["dep_s"] = st["departure_time"].map(hms_to_s)
    st["arr_s"] = st["arrival_time"].map(hms_to_s)
    st = st.sort_values(["trip_id", "stop_sequence"])

    rows = []
    for trip_id, g in st.groupby("trip_id", sort=False):
        g = g.reset_index(drop=True)
        route_id = trip_route.get(trip_id, "")
        mode_code = route_mode.get(route_id, "3")
        mode_name = MODE_NAMES.get(int(mode_code) if str(mode_code).isdigit() else 3, "Autocarro")
        line = route_name.get(route_id, route_id)
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if a["arr_s"] >= 86400 or b["arr_s"] >= 86400:
                continue  # ignora serviço "do dia seguinte" (>24h) nesta versão
            rows.append((trip_id, line, mode_name, a["stop_id"], a["dep_s"], b["stop_id"], b["arr_s"]))

    con = pd.DataFrame(rows, columns=["trip", "line", "mode", "dep_stop", "dep_s", "arr_stop", "arr_s"])

    stops = stops_t.copy()
    stops["stop_key"] = stops["stop_id"]
    stops = stops.rename(columns={"stop_id": "stop", "stop_name": "name"})
    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)
    return con, stops[["stop", "stop_key", "name", "stop_lat", "stop_lon"]]


def load_reliability(path):
    """CSV opcional: route_id,stop_id,hour,delay_p50_s,delay_p90_s,cancel_rate.
    Sem ficheiro (ainda não há agregação real), devolve None e os quantis ficam a 0."""
    if not path or not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df = df.rename(columns={"route_id": "line", "stop_id": "stop_key"})
    for q in Q:
        if q not in df.columns:
            df[q] = df.get("delay_p50_s", 0)
    if "mode" not in df.columns:
        df["mode"] = "Autocarro"
    if "n" not in df.columns:
        df["n"] = 100  # peso por omissão quando a fonte não dá contagem
    if "cancel_rate" not in df.columns:
        df["cancel_rate"] = 0.0
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gtfs")
    ap.add_argument("--dia", help="AAAAMMDD (default: próxima terça-feira)")
    ap.add_argument("--fonte", default="demo", choices=["demo", "real", "misto"])
    ap.add_argument("--fiabilidade", help="CSV com quantis de atraso por paragem+linha+hora (opcional)")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "data", "tp"))
    args = ap.parse_args()

    if args.dia:
        service_date = datetime.strptime(args.dia, "%Y%m%d").date()
    else:
        today = date.today()
        service_date = date.fromordinal(today.toordinal() + (1 - today.weekday()) % 7)

    con, stops = build_connections(args.gtfs, service_date)
    stops = stops[stops["stop"].isin(set(con.dep_stop) | set(con.arr_stop))].reset_index(drop=True)
    sid = {s: i for i, s in enumerate(stops["stop"])}
    assert len(stops) < 65536

    con["u"] = con["dep_stop"].map(sid)
    con["v"] = con["arr_stop"].map(sid)
    con["t"] = pd.factorize(con["trip"])[0]
    assert con["t"].max() < 65536

    dl = load_reliability(args.fiabilidade)
    if dl is not None and not dl.empty:
        dl[Q] = dl[Q].clip(lower=0, upper=1800)
        w = dl.assign(**{c: dl[c] * dl.n for c in Q + ["cancel_rate"]})
        line_tbl = w.groupby(["line", "mode", "hour"])[Q + ["cancel_rate", "n"]].sum()
        line_tbl[Q + ["cancel_rate"]] = line_tbl[Q + ["cancel_rate"]].div(line_tbl["n"], axis=0)

        c = con.merge(stops[["stop", "stop_key"]], left_on="arr_stop", right_on="stop", how="left")
        c["hour"] = (c["arr_s"] // 3600) % 24
        own = dl.set_index(["stop_key", "line", "hour"])[Q + ["cancel_rate"]]
        own = own[~own.index.duplicated()]
        a = c.join(own, on=["stop_key", "line", "hour"])
        b = c.join(line_tbl[Q + ["cancel_rate"]], on=["line", "mode", "hour"])
        for col in Q + ["cancel_rate"]:
            a[col] = a[col].fillna(b[col]).fillna(0)
        hw = c.groupby(["line", "arr_stop", "hour"])["trip"].transform("count")
        wait = a["cancel_rate"] * (3600 / hw).clip(upper=1800)
        buf = {q: (a[q] + wait).clip(upper=2540).to_numpy() for q in Q}
        has_reliability = True
    else:
        buf = {q: np.zeros(len(con)) for q in Q}
        has_reliability = False

    order = np.argsort(con["dep_s"].to_numpy(), kind="stable")
    con = con.iloc[order].reset_index(drop=True)
    buf = {q: v[order] for q, v in buf.items()}

    out_dir = args.out
    os.makedirs(os.path.join(out_dir, "c"), exist_ok=True)

    # data/tp/live.json — sequência de paragens+hora de cada viagem do dia de referência,
    # para a simulação dinâmica ("o que deveria estar a acontecer agora", segundo o horário
    # real): o browser interpola a posição do veículo em linha reta entre as duas paragens
    # que está a percorrer à hora simulada (não segue a curva exata da via entre paragens —
    # só a camada "Linhas" faz isso, com a geometria de percurso real quando existe).
    # Reaproveita "con" (já ordenado, com u/v/t): cada viagem é a cadeia das suas ligações.
    trip_op, trip_line, trip_mode, starts, visit_u, visit_t = [], [], [], [0], [], []
    for _t, g in con.groupby("t", sort=False):
        first = g.iloc[0]
        trip_op.append(op_of(first["trip"]))
        trip_line.append(str(first["line"]))
        trip_mode.append(str(first["mode"]))
        visit_u.append(int(first["u"])); visit_t.append(int(first["dep_s"]))
        for row in g.itertuples():
            visit_u.append(int(row.v)); visit_t.append(int(row.arr_s))
        starts.append(len(visit_u))
    live = {
        "trip_op": trip_op, "trip_line": trip_line, "trip_mode": trip_mode,
        "visit_start": b64(np.array(starts, dtype=np.uint32)),
        "visit_u": b64(np.array(visit_u, dtype=np.uint16)),
        "visit_t": b64(np.array(visit_t, dtype=np.uint32)),
        "operadoras": OPERADORAS,
        "note": "Posição simulada a partir do horário real do dia de referência (não é GTFS-RT; "
                "não há posições ao vivo). Entre paragens, a posição é interpolada em linha reta "
                "pelo tempo decorrido, não pela geometria exata da via.",
    }
    import json as _json
    _json.dump(live, open(os.path.join(out_dir, "live.json"), "w"), separators=(",", ":"))

    hours = con["dep_s"] // 3600
    for h in sorted(hours.unique()):
        m = (hours == h).to_numpy()
        part = con[m]
        chunk = {
            "u": b64(part["u"].to_numpy(np.uint16)), "v": b64(part["v"].to_numpy(np.uint16)),
            "dep": b64(np.round(part["dep_s"].to_numpy() / 10).astype(np.uint16)),
            "arr": b64(np.round(part["arr_s"].to_numpy() / 10).astype(np.uint16)),
            "trip": b64(part["t"].to_numpy(np.uint16)),
            **{q: b64(np.round(buf[q][m] / 10).astype(np.uint8)) for q in Q},
        }
        import json
        json.dump(chunk, open(os.path.join(out_dir, "c", f"{int(h):02d}.json"), "w"), separators=(",", ":"))

    rows = int(np.ceil((BOX[2] - BOX[0]) / DLAT))
    cols = int(np.ceil((BOX[3] - BOX[1]) / DLON))
    # grelha de população: zeros por agora (ver README — falta fonte INE/Censos)
    cell_pop = np.zeros(rows * cols, dtype=np.uint16)

    con["h"] = (con["arr_s"] // 3600) % 24
    mode_delay = {}
    if has_reliability:
        for lvl, q in zip(LEVELS[1:], Q):
            t = pd.DataFrame({"mode": con["mode"], "h": con["h"], "d": buf[q] / 60}).groupby(["h", "mode"])["d"].mean().round(1)
            mode_delay[lvl] = {int(h): t.loc[h].to_dict() for h in t.index.get_level_values(0).unique()}

    stop_op = stops["stop"].map(op_of)

    import json
    meta = {
        "box": list(BOX), "dlat": DLAT, "dlon": DLON, "rows": rows, "cols": cols,
        "day": service_date.strftime("%A %d %b %Y"), "city": "Póvoa de Varzim",
        "levels": LEVELS, "quantiles": Q, "hours": [int(h) for h in sorted(hours.unique())],
        "stop_lat": b64(stops["stop_lat"].to_numpy(np.float32)), "stop_lon": b64(stops["stop_lon"].to_numpy(np.float32)),
        "stop_name": stops["name"].tolist(), "stop_op": stop_op.tolist(), "operadoras": OPERADORAS,
        "pop": b64(cell_pop), "mode_delay": mode_delay,
        "source": args.fonte, "has_reliability": has_reliability, "has_population": False,
        "generated_at": datetime.now().astimezone().isoformat(),
        "stop_count": len(stops), "connection_count": len(con),
    }
    json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"), separators=(",", ":"))

    print(f"OK: {len(stops)} paragens, {con['t'].max() + 1} viagens, {len(con)} conexões, "
          f"dia de referência {service_date.isoformat()}, fonte={args.fonte}, fiabilidade={'sim' if has_reliability else 'não (0)'}")
    print(f"grid {rows}x{cols} (~200m), saída em {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
