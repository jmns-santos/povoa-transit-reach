#!/usr/bin/env python3
"""
Gera o grafo routável (carro + a pé) a partir da rede viária municipal REAL
(shapefile com geometria de cada troço e campos: classe funcional da via,
sumo_class — lista de classes de veículo autorizadas por troço, à boleia do
SUMO/traffic simulation —, sentido, oneway).

Substitui build_road_demo.py (grelha sintética) sempre que este ficheiro
estiver disponível: aqui a GEOMETRIA e a CLASSIFICAÇÃO de cada troço (que via
é só pedonal/ciclável, que via é motorway, sentido único, etc.) são reais.

O que NÃO é real (e fica documentado): os campos de velocidade/tempo do
próprio ficheiro vêm todos preenchidos com o mesmo valor genérico (50 km/h,
incluindo em troços pedonais) — claramente um valor de teste, não calibrado.
Por isso as velocidades usadas aqui vêm de uma tabela por classe funcional da
via (suposição documentada, não medição), da mesma forma que o resto do
projeto assume velocidades quando não há dados reais calibrados — mas agora
sobre a geometria e a topologia REAIS da rede, não sobre uma grelha inventada.

Uso:
    python3 build_road_real.py <rede_viaria.shp>

Formato de saída: igual ao de build_road_demo.py (data/road/graph.json) —
não exige nenhuma mudança no index.html.
"""
import argparse
import base64
import math
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree


def clean_str(v):
    """None/NaN -> "" ; qualquer outro valor -> str(v)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v)

from build_explore_povoa import BOX, DLAT, DLON  # mesma caixa e grid fino do modo TP

HERE = os.path.dirname(os.path.abspath(__file__))
WALK_KMH = 5.0  # velocidade de marcha uniforme assumida (não medida)

# velocidade assumida por classe funcional da via (km/h) — suposição
# documentada, não medição (ver nota acima); "default" cobre classes não
# listadas ou em branco.
SPEED_BY_CLASSE = {
    "A": 120, "A (fora limite PV)": 120,
    "EN": 80, "EN (fora limite PV)": 80, "Ramal EN13": 80,
    "ER": 70, "ER (fora limite PV)": 70,
    "EM": 60,
    "CM": 50,
    "ARR": 40,
    "OUT": 30,
    "Outras Vias (fora limite PV)": 50,
    "PED": 5, "CIC": 15,  # não usadas para carro (ver allowed_car), só de reserva
}
DEFAULT_SPEED = 30

# classes funcionais que NÃO são seguras/legais para andar a pé (auto-estrada)
CLASSES_SEM_PEAO = {"A", "A (fora limite PV)"}


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shapefile", help="Shapefile (.shp) da rede viária municipal, com os campos classe/sumo_class/sentido/oneway/comprim")
    ap.add_argument("--precisao-no", type=float, default=0.2, help="tolerância (m) para fundir extremos de troços no mesmo nó (default 0.2m)")
    args = ap.parse_args()

    gdf = gpd.read_file(args.shapefile)
    print(f"{len(gdf)} troços lidos.")

    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf = gdf[gdf["situacao"] == "Ativa"].copy()  # só rede existente, não "Proposta"/"Em execução"
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)  # separa MultiLineString em LineString
    gdf = gdf[gdf.geometry.length > 0.5].copy()  # tira troços de comprimento ~zero (erros de digitalização)
    print(f"{len(gdf)} troços após filtrar ativos, com geometria e comprimento > 0.5m.")

    if gdf.crs is None:
        sys.exit("Erro: shapefile sem CRS definido.")
    crs_m = gdf.crs  # já está num CRS métrico (ETRS89/TM06-Portugal)

    # nós = extremos dos troços, fundidos por proximidade (precisao_no)
    prec = args.precisao_no
    node_of = {}
    node_xy = []

    def get_node(x, y):
        key = (round(x / prec), round(y / prec))
        if key not in node_of:
            node_of[key] = len(node_xy)
            node_xy.append((x, y))
        return node_of[key]

    edges_u, edges_v = [], []
    edge_len_m, edge_classe, edge_sumo, edge_oneway = [], [], [], []

    for row in gdf.itertuples():
        coords = list(row.geometry.coords)
        x0, y0 = coords[0]
        x1, y1 = coords[-1]
        u, v = get_node(x0, y0), get_node(x1, y1)
        if u == v:
            continue
        edges_u.append(u); edges_v.append(v)
        edge_len_m.append(row.geometry.length)
        edge_classe.append(clean_str(getattr(row, "classe", None)))
        edge_sumo.append(clean_str(getattr(row, "sumo_class", None)))
        oneway_v = clean_str(getattr(row, "oneway", None))
        edge_oneway.append(oneway_v or "B")

    n_nodes = len(node_xy)
    print(f"{n_nodes} nós, {len(edges_u)} troços válidos (após fundir extremos a {prec} m).")

    node_xy = np.array(node_xy)
    # reprojeta nós para WGS84 (lat/lon) para o formato de saída e para casar com o grid fino
    nodes_gdf = gpd.GeoSeries(gpd.points_from_xy(node_xy[:, 0], node_xy[:, 1]), crs=crs_m).to_crs(epsg=4326)
    node_lon = nodes_gdf.x.values.astype(np.float32)
    node_lat = nodes_gdf.y.values.astype(np.float32)

    edges_u = np.array(edges_u, dtype=np.uint32)
    edges_v = np.array(edges_v, dtype=np.uint32)
    edge_len_m = np.array(edge_len_m, dtype=np.float64)

    HUGE = 1e9  # peso "proibido" (muito maior do que qualquer corte de tempo usado no painel)
    car_mps = np.array([SPEED_BY_CLASSE.get(c, DEFAULT_SPEED) * 1000 / 3600 for c in edge_classe])
    allowed_car = np.array(["passenger" in s for s in edge_sumo])
    allowed_ped = np.array([c not in CLASSES_SEM_PEAO for c in edge_classe])
    walk_mps = WALK_KMH * 1000 / 3600

    car_seconds_fwd = np.where(allowed_car, edge_len_m / car_mps, HUGE)
    ped_seconds = np.where(allowed_ped, edge_len_m / walk_mps, HUGE)

    # sentido: FT = só u->v permitido a carro; TF = só v->u; tudo o resto (B/N/vazio) = os dois.
    oneway_fwd_only = np.array([o == "FT" for o in edge_oneway])
    oneway_rev_only = np.array([o == "TF" for o in edge_oneway])

    car_seconds_rev = car_seconds_fwd.copy()
    car_seconds_fwd = np.where(oneway_rev_only, HUGE, car_seconds_fwd)
    car_seconds_rev = np.where(oneway_fwd_only, HUGE, car_seconds_rev)
    # a pé ignora sentido de trânsito automóvel (anda-se nos dois sentidos de uma rua de sentido único)

    # cada troço vira dois arcos dirigidos (u->v e v->u)
    all_u = np.concatenate([edges_u, edges_v])
    all_v = np.concatenate([edges_v, edges_u])
    all_w_car = np.concatenate([car_seconds_fwd, car_seconds_rev])
    all_w_walk = np.concatenate([ped_seconds, ped_seconds])

    print(f"arcos a carro utilizáveis: {(all_w_car < HUGE).sum()} / {len(all_w_car)}")
    print(f"arcos a pé utilizáveis: {(all_w_walk < HUGE).sum()} / {len(all_w_walk)}")

    # nó do grafo mais próximo de cada célula do grid FINO (o mesmo do modo TP),
    # com correção de compressão da longitude nesta latitude
    S, W, N, E = BOX
    lat0 = (S + N) / 2
    coslat = math.cos(math.radians(lat0))
    tree = cKDTree(np.column_stack([node_lat, node_lon * coslat]))

    fine_rows = int(np.ceil((N - S) / DLAT))
    fine_cols = int(np.ceil((E - W) / DLON))
    cell_lat = S + (np.arange(fine_rows) + 0.5) * DLAT
    cell_lon = W + (np.arange(fine_cols) + 0.5) * DLON
    grid_lat, grid_lon = np.meshgrid(cell_lat, cell_lon, indexing="ij")
    _, nearest = tree.query(np.column_stack([grid_lat.ravel(), grid_lon.ravel() * coslat]))
    cell_node = nearest.astype(np.uint32)

    graph = {
        "box": list(BOX), "n_nodes": n_nodes,
        "fine_rows": fine_rows, "fine_cols": fine_cols,
        "node_lat": b64(node_lat), "node_lon": b64(node_lon),
        "edge_u": b64(all_u.astype(np.uint32)),
        "edge_v": b64(all_v.astype(np.uint32)),
        "edge_w": b64(all_w_car.astype(np.float32)),
        "edge_w_walk": b64(all_w_walk.astype(np.float32)),
        "cell_node": b64(cell_node),
        "walk_kmh": WALK_KMH,
        "source": "real",
        "note": "Rede viária municipal real (geometria e classificação por tipo de via e sentido reais; "
                "motorways excluídas do modo a pé). As velocidades por tipo de via são uma suposição documentada "
                "(os campos de velocidade do próprio ficheiro estavam todos preenchidos com o mesmo valor genérico, "
                "não calibrado) — mas aplicadas sobre a topologia real da rede, não sobre uma grelha inventada. "
                "O modo \"A pé\" já pode usar troços só pedonais/cicláveis que o carro não pode.",
    }

    out_dir = os.path.join(HERE, "..", "data", "road")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "graph.json"), "w", encoding="utf-8") as f:
        import json
        json.dump(graph, f, separators=(",", ":"))

    print(f"OK: {n_nodes} nós, {len(all_u)} arestas dirigidas")
    print(f"saída em {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
