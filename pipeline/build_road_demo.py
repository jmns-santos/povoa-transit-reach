#!/usr/bin/env python3
"""
Gera uma rede viária SINTÉTICA routável (grid + alguns eixos mais rápidos a
imitar estradas principais) para o modo "Rede Viária" (carro), só para
demonstração — não é a rede viária real da CMPV nem dados do OSM.

Porquê sintética: não foi possível obter o extrato OSM real (Overpass/osm.pbf)
nem a rede viária municipal oficial, por restrições de acesso de rede deste
ambiente de desenvolvimento (ver README). Quando um desses ficheiros estiver
disponível, substituir este script por um que leia o grafo viário real e gere
o mesmo formato de saída (data/road/graph.json).

Formato de saída (consumido pelo index.html, calculado no browser com
Dijkstra): nós (lat/lon) e arestas (from, to, segundos), tudo em base64.
"""
import base64
import json
import math
import os

import numpy as np

from build_explore_povoa import BOX, DLAT, DLON  # mesma caixa e grid fino do modo TP

HERE = os.path.dirname(os.path.abspath(__file__))
SPACING_M = 300                          # malha base de ruas locais (nós do grafo)
LOCAL_KMH = 22                           # inclui cruzamentos/sinais; a malha é só 4 direções e sobre-estima atalhos
MAIN_KMH = 65
WALK_KMH = 4.8                           # velocidade a pé (mesma do acesso/transferência no modo TP), uniforme em toda a rede

# pontos-chave da área (mesmos do GTFS de demonstração), para os eixos rápidos
KEY_POINTS = {
    "Estela": (41.4460, -8.7840),
    "A Ver-o-Mar": (41.3650, -8.7600),
    "Póvoa Centro": (41.3793, -8.7649),
    "Póvoa Estação": (41.3815, -8.7600),
    "Póvoa Hospital": (41.3850, -8.7550),
    "Terroso": (41.3950, -8.7500),
    "Beiriz": (41.3900, -8.7300),
    "Vila do Conde Centro": (41.3523, -8.7438),
    "Vila do Conde Estação": (41.3480, -8.7400),
}
MAIN_AXES = [
    ("Estela", "A Ver-o-Mar"), ("A Ver-o-Mar", "Póvoa Centro"),
    ("Póvoa Centro", "Póvoa Estação"), ("Póvoa Estação", "Vila do Conde Centro"),
    ("Vila do Conde Centro", "Vila do Conde Estação"),
    ("Póvoa Centro", "Terroso"), ("Terroso", "Beiriz"),
    ("Póvoa Centro", "Póvoa Hospital"),
]


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def main():
    S, W, N, E = BOX
    lat0 = (S + N) / 2
    kx = math.cos(math.radians(lat0)) * 111320
    ky = 110574
    dlat = SPACING_M / ky
    dlon = SPACING_M / kx

    rows = int((N - S) / dlat) + 1
    cols = int((E - W) / dlon) + 1

    lats = S + np.arange(rows) * dlat
    lons = W + np.arange(cols) * dlon

    def node_id(r, c):
        return r * cols + c

    n_nodes = rows * cols
    node_lat = np.repeat(lats, cols).astype(np.float32)
    node_lon = np.tile(lons, rows).astype(np.float32)

    edges_u, edges_v, edges_w, edges_d = [], [], [], []
    local_mps = LOCAL_KMH * 1000 / 3600

    # malha 4-direções (ruas locais)
    for r in range(rows):
        for c in range(cols):
            i = node_id(r, c)
            if c + 1 < cols:
                j = node_id(r, c + 1)
                d = SPACING_M
                w = d / local_mps
                edges_u += [i, j]; edges_v += [j, i]; edges_w += [w, w]; edges_d += [d, d]
            if r + 1 < rows:
                j = node_id(r + 1, c)
                d = SPACING_M
                w = d / local_mps
                edges_u += [i, j]; edges_v += [j, i]; edges_w += [w, w]; edges_d += [d, d]

    # eixos rápidos entre pontos-chave: encontra o caminho de nós mais perto
    # da linha reta (aprox.) e reduz o tempo de viagem nesses troços para
    # simular uma via principal (MAIN_KMH em vez de LOCAL_KMH)
    def nearest_node(lat, lon):
        r = round((lat - S) / dlat)
        c = round((lon - W) / dlon)
        r = min(max(r, 0), rows - 1)
        c = min(max(c, 0), cols - 1)
        return r, c

    main_mps = MAIN_KMH * 1000 / 3600
    speedup = local_mps / main_mps  # fator multiplicativo do tempo (<1)
    edge_index = {}
    for idx, (u, v) in enumerate(zip(edges_u, edges_v)):
        edge_index.setdefault((u, v), idx)

    for a_name, b_name in MAIN_AXES:
        (lat_a, lon_a), (lat_b, lon_b) = KEY_POINTS[a_name], KEY_POINTS[b_name]
        r0, c0 = nearest_node(lat_a, lon_a)
        r1, c1 = nearest_node(lat_b, lon_b)
        steps = max(abs(r1 - r0), abs(c1 - c0), 1)
        prev = (r0, c0)
        for s in range(1, steps + 1):
            r = round(r0 + (r1 - r0) * s / steps)
            c = round(c0 + (c1 - c0) * s / steps)
            # anda em L (primeiro linha, depois coluna) para garantir nós existentes na malha
            step_r = (r, prev[1])
            for (pr, pc), (nr, nc) in ((prev, step_r), (step_r, (r, c))):
                if (pr, pc) == (nr, nc):
                    continue
                if 0 <= nr < rows and 0 <= nc < cols:
                    u, v = node_id(pr, pc), node_id(nr, nc)
                    for key in ((u, v), (v, u)):
                        if key in edge_index:
                            edges_w[edge_index[key]] *= speedup
            prev = (r, c)

    # nó do grafo mais próximo de cada célula do grid FINO (o mesmo do modo TP),
    # para o browser rasterizar o resultado do Dijkstra sem procurar vizinhos
    fine_rows = int(np.ceil((BOX[2] - BOX[0]) / DLAT))
    fine_cols = int(np.ceil((BOX[3] - BOX[1]) / DLON))
    cell_node = np.zeros(fine_rows * fine_cols, dtype=np.uint32)
    for r in range(fine_rows):
        clat = BOX[0] + (r + 0.5) * DLAT
        nr = min(max(round((clat - S) / dlat), 0), rows - 1)
        for c in range(fine_cols):
            clon = BOX[1] + (c + 0.5) * DLON
            nc = min(max(round((clon - W) / dlon), 0), cols - 1)
            cell_node[r * fine_cols + c] = node_id(nr, nc)

    walk_mps = WALK_KMH * 1000 / 3600
    edges_w_walk = [d / walk_mps for d in edges_d]  # tempo a pé pela MESMA topologia de vias, sem o speedup dos eixos rápidos

    graph = {
        "box": list(BOX), "rows": rows, "cols": cols, "n_nodes": n_nodes,
        "fine_rows": fine_rows, "fine_cols": fine_cols,
        "node_lat": b64(node_lat), "node_lon": b64(node_lon),
        "edge_u": b64(np.array(edges_u, dtype=np.uint32)),
        "edge_v": b64(np.array(edges_v, dtype=np.uint32)),
        "edge_w": b64(np.array(edges_w, dtype=np.float32)),
        "edge_w_walk": b64(np.array(edges_w_walk, dtype=np.float32)),
        "cell_node": b64(cell_node),
        "local_kmh": LOCAL_KMH, "main_kmh": MAIN_KMH, "walk_kmh": WALK_KMH,
        "source": "demo",
        "note": "Rede viária sintética (grid + eixos rápidos entre pontos-chave) — não é OSM nem a rede municipal real. "
                "O modo \"A pé\" usa a mesma topologia de vias, à velocidade de marcha (sem o atalho dos eixos rápidos); "
                "não representa passeios, atravessamentos nem atalhos pedonais reais (praças, parques, acessos só para pessoas).",
    }

    out_dir = os.path.join(HERE, "..", "data", "road")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "graph.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, separators=(",", ":"))

    print(f"OK: {n_nodes} nós, {len(edges_u)} arestas dirigidas, grid {rows}x{cols} (~{SPACING_M}m)")
    print(f"saída em {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
