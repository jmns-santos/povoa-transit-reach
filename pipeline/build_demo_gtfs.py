#!/usr/bin/env python3
"""
Gera um GTFS SINTÉTICO (não é dados reais da UNIR) só para testar e demonstrar
o motor de isócronas antes de termos acesso ao GTFS real da UNIR/TMP.

Paragens e linhas são inventadas, mas usam coordenadas aproximadas de locais
reais da Póvoa de Varzim e Vila do Conde, para o mapa parecer plausível.

Uso:
    python build_demo_gtfs.py [pasta_saida]

Gera um GTFS "normal" (stops.txt, routes.txt, trips.txt, stop_times.txt,
calendar.txt) que o build_data.py depois lê exatamente como leria um GTFS
real exportado da UNIR.
"""
import csv
import os
import sys
from datetime import timedelta

# --- Paragens (id, nome, lat, lon) — coordenadas aproximadas, só para demo ---
STOPS = [
    ("est01", "Estela",                       41.4460, -8.7840),
    ("avm01", "A Ver-o-Mar",                   41.3650, -8.7600),
    ("pov01", "Póvoa de Varzim - Câmara",      41.3793, -8.7649),
    ("pov02", "Póvoa de Varzim - Estação",     41.3815, -8.7600),
    ("pov03", "Póvoa de Varzim - Hospital",    41.3850, -8.7550),
    ("ter01", "Terroso",                       41.3950, -8.7500),
    ("bei01", "Beiriz",                        41.3900, -8.7300),
    ("vdc01", "Vila do Conde - Centro",        41.3523, -8.7438),
    ("vdc02", "Vila do Conde - Estação",       41.3480, -8.7400),
]

# --- Linhas (id, nome, lista de paragens em ordem, cor) ---
ROUTES = [
    ("L1", "Estela - Póvoa - Vila do Conde",
     ["est01", "avm01", "pov01", "pov02", "vdc01", "vdc02"], "1E88E5"),
    ("L2", "Póvoa - Terroso - Beiriz",
     ["pov01", "ter01", "bei01"], "43A047"),
    ("L3", "Circular urbana Póvoa",
     ["pov01", "pov03", "pov02", "avm01", "pov01"], "F4511E"),
]

# tempo de viagem entre paragens consecutivas de cada linha, em minutos
SEGMENT_MINUTES = {
    "L1": [8, 6, 4, 10, 5],
    "L2": [9, 7],
    "L3": [6, 5, 9, 7],
}

SERVICE_ID = "DIA_UTIL"
START_H, END_H = 6, 22      # serviço das 06:00 às 22:00
HEADWAY_MIN = {"L1": 30, "L2": 40, "L3": 25}


def hms(total_minutes):
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}:00"


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../data_src/gtfs_demo"
    out_dir = os.path.join(os.path.dirname(__file__), out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # stops.txt
    with open(os.path.join(out_dir, "stops.txt"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon"])
        for sid, name, lat, lon in STOPS:
            w.writerow([sid, name, lat, lon])

    # routes.txt
    with open(os.path.join(out_dir, "routes.txt"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["route_id", "route_short_name", "route_long_name", "route_type", "route_color"])
        for rid, name, _, color in ROUTES:
            w.writerow([rid, rid, name, 3, color])

    # calendar.txt — um único serviço, dias úteis
    with open(os.path.join(out_dir, "calendar.txt"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
                    "saturday", "sunday", "start_date", "end_date"])
        w.writerow([SERVICE_ID, 1, 1, 1, 1, 1, 0, 0, "20260101", "20271231"])

    trips_rows = []
    stop_times_rows = []
    trip_seq = 0

    for rid, name, stops, color in ROUTES:
        headway = HEADWAY_MIN[rid]
        segs = SEGMENT_MINUTES[rid]
        # gera partidas a cada `headway` minutos, das START_H às END_H, nos dois sentidos
        for direction, seq_stops, seq_segs in (
            (0, stops, segs),
            (1, list(reversed(stops)), list(reversed(segs))),
        ):
            t = START_H * 60
            while t <= END_H * 60:
                trip_seq += 1
                trip_id = f"{rid}_{direction}_{trip_seq}"
                trips_rows.append([rid, SERVICE_ID, trip_id, f"{name} ({'ida' if direction == 0 else 'volta'})", direction])
                cursor = t
                for i, sid in enumerate(seq_stops):
                    stop_times_rows.append([trip_id, hms(cursor), hms(cursor), sid, i])
                    if i < len(seq_segs):
                        cursor += seq_segs[i]
                t += headway

    with open(os.path.join(out_dir, "trips.txt"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["route_id", "service_id", "trip_id", "trip_headsign", "direction_id"])
        w.writerows(trips_rows)

    with open(os.path.join(out_dir, "stop_times.txt"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
        w.writerows(stop_times_rows)

    print(f"GTFS sintético gerado em: {out_dir}")
    print(f"  {len(STOPS)} paragens, {len(ROUTES)} linhas, {len(trips_rows)} viagens, {len(stop_times_rows)} passagens")


if __name__ == "__main__":
    main()
