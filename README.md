# Transit Reach — Póvoa de Varzim

Até onde se chega, a partir de um ponto e hora escolhidos, em transporte público ou de carro, na Póvoa de Varzim e Vila do Conde — e como compara um com o outro. Inspirado em [munich-transit-reach](https://github.com/ilyas-ku/munich-transit-reach) e [rhein-main-transit-reach](https://github.com/ilyas-ku/rhein-main-transit-reach), de `ilyas-ku`; `index.html` reaproveita o motor desses projetos (Connection Scan no browser + contornos d3), adaptado e traduzido para português de Portugal, com um segundo modo ("De carro") acrescentado.

Protótipo da Câmara Municipal da Póvoa de Varzim.

## Estado atual (2026-11-09)

| Camada | Estado | Fonte |
|---|---|---|
| Metro do Porto | **Real** | GTFS oficial da Metro do Porto |
| Autocarros (UNIR) | **Real**, filtrado à zona | GTFS estático oficial da UNIR — cobre toda a Área Metropolitana do Porto (12 067 paragens); filtrado às viagens que tocam a Póvoa/Vila do Conde e zona próxima antes de entrar no pipeline (ver nota abaixo) |
| Fiabilidade (atrasos/cancelamentos) | **Não incluída** (todos os níveis = horário) | a UNIR tem GTFS-RT em produção (posições de veículos), mas falta a agregação por paragem+linha+hora |
| Rede viária (carro e a pé) | **Real** (geometria e classificação), velocidades por tipo de via assumidas | ver nota sobre a rede viária municipal abaixo |
| População em grelha | **Real** | BGRI 2021 (Censos), por subsecção estatística — ver nota abaixo |

A área de estudo cobre agora todo o concelho da Póvoa de Varzim (as 7 freguesias, incluindo Balazar e Rates) mais Vila do Conde.

**Tudo é ficheiro estático** — `data/tp/*.json` e `data/road/graph.json` são gerados pelo pipeline e servidos tal e qual pelo GitHub Pages. A página nunca acede a nenhuma base de dados ao vivo, por segurança: só lê estes JSON.

**Nota sobre o filtro da UNIR.** O GTFS da UNIR cobre toda a AMP; a filtragem por nome de paragem (`grep "póvoa"`) dá falsos positivos — várias zonas da AMP têm localidades chamadas "Póvoa" sem ser a de Varzim. Por isso `filter_gtfs_bbox.py` filtra por **coordenadas** (viagens que tocam pelo menos uma paragem dentro de uma caixa alargada à volta da Póvoa/Vila do Conde), mantendo cada viagem completa — algumas linhas seguem para fora da caixa visível no mapa (ex. Barcelos, Esposende); isso é esperado e não é um erro.

**Nota sobre a rede viária municipal.** `pipeline/build_road_real.py` lê um shapefile da rede viária municipal (geometria de cada troço + classificação por tipo de via, sentido, e lista de modos de transporte autorizados por troço) e gera o grafo routável. A geometria, a topologia (que ruas se cruzam) e a classificação (que troços são só pedonais/cicláveis, que sentidos são permitidos, que vias são auto-estrada) são reais. O que **não** é real: os campos de velocidade/tempo do próprio ficheiro vinham todos com o mesmo valor genérico (50 km/h, incluindo em troços pedonais) — claramente um valor de teste, nunca calibrado — por isso as velocidades usadas vêm de uma tabela por tipo de via (suposição documentada no próprio script), aplicada sobre a topologia real. `pipeline/build_road_demo.py` (grelha sintética) fica como alternativa de reserva, caso não haja shapefile disponível.

**Nota sobre o Google Maps Platform.** Há uma chave de API do Google Maps Platform disponível, criada para testar a Air Quality API — não para routing. O crédito experimental de 300 $/90 dias já deve ter expirado; resta o limite gratuito mensal permanente por API. As APIs de rotas/distâncias (Directions, Distance Matrix) podiam, em teoria, calibrar ou validar pontualmente as velocidades assumidas por tipo de via — mas essa chamada teria de correr a partir de uma máquina com rede sem restrições (não é alcançável a partir deste pipeline de desenvolvimento), e sempre sem exceder o limite gratuito mensal nem fazer upgrade da conta.

**Nota sobre o INE/Censos 2021.** `pipeline/importar_censos2021.py` lê um ficheiro BGRI 2021 (GeoPackage/Shapefile, por subsecção estatística), filtra ao concelho da Póvoa de Varzim, soma a população residente à grelha fina do projeto e atualiza `data/tp/meta.json`. A fonte pode ser o download público do INE (http://mapas.ine.pt/download/index2021.phtml — a 2026-11-09 esse portal estava temporariamente em manutenção) ou qualquer outro extrato do mesmo BGRI 2021 com geometria e um campo de população residente; o script detecta automaticamente os nomes de coluna mais comuns (ver "Preencher a população" abaixo).

## Como usar

Abrir `index.html` (ou a página publicada). Quatro modos no painel à esquerda:
- **Transporte público** — Connection Scan sobre o horário combinado (Metro + UNIR, ambos reais), com o controlo de fiabilidade (ainda sem efeito real, ver tabela acima).
- **De carro** — Dijkstra sobre a rede viária municipal real, só nas vias com acesso automóvel, a velocidades assumidas por tipo de via.
- **A pé** — Dijkstra sobre a mesma rede real, incluindo passeios, ciclovias e atalhos só pedonais que o carro não pode usar; exclui auto-estradas.
- **Comparar** — transporte público e carro sobrepostos no mesmo mapa (TP a verde-água, carro a laranja).

Clicar no mapa ou arrastar o marcador branco muda o ponto de partida; a pesquisa usa o Nominatim (OpenStreetMap), limitado à caixa da Póvoa/Vila do Conde.

## Estrutura

```
index.html                      página única (mapa Leaflet, motor CSA + Dijkstra, tudo em JS puro)
data/
  tp/meta.json, tp/c/HH.json    dados de transporte público (por hora)
  road/graph.json               grafo da rede viária (nós + arestas, carro e a pé)
pipeline/
  build_demo_gtfs.py            gera um GTFS sintético de reserva (só se não houver um GTFS real)
  filter_gtfs_bbox.py           filtra um GTFS grande (ex. UNIR, toda a AMP) às viagens perto da área de estudo
  combine_gtfs.py                junta vários GTFS (ex. Metro + UNIR, ambos reais) num só, com prefixos
  build_explore_povoa.py        lê o GTFS combinado → data/tp/*
  build_road_real.py            lê a rede viária municipal real (shapefile) → data/road/graph.json
  build_road_demo.py            alternativa de reserva: grelha sintética (carro + a pé), só se não houver shapefile
  importar_censos2021.py        lê um ficheiro BGRI 2021 do INE e preenche a população em data/tp/meta.json
data_src/                       GTFS brutos usados para gerar data/ (não precisam de ir para o site publicado)
```

## Recriar os dados

```bash
cd pipeline
# 1. filtrar o GTFS da UNIR (toda a AMP) à zona de estudo, por coordenadas (não por nome)
python3 filter_gtfs_bbox.py <pasta ou .zip do GTFS da UNIR> ../data_src/gtfs_unir_filtrado \
    --box 41.18 -8.94 41.59 -8.53

# 2. combinar com o Metro real
python3 combine_gtfs.py --out ../data_src/gtfs_combined \
    unir=../data_src/gtfs_unir_filtrado metro=<pasta ou .zip do GTFS real do Metro>

# 3. gerar os dados de transporte público e a rede viária
python3 build_explore_povoa.py ../data_src/gtfs_combined --dia 20261020 --fonte real
python3 build_road_real.py <shapefile .shp da rede viária municipal>
# (ou, só se não houver shapefile disponível: python3 build_road_demo.py)
```

### Preencher a população (Censos 2021)

```powershell
pip install geopandas pyogrio
python importar_censos2021.py "C:\caminho\para\BGRI2021_Porto.gpkg"
```

Descarregar primeiro o ficheiro do distrito do Porto em http://mapas.ine.pt/download/index2021.phtml (ver nota acima se o portal estiver em manutenção). O script filtra ao concelho da Póvoa de Varzim automaticamente e atualiza `data/tp/meta.json` — é o único ficheiro que precisa de ser publicado de novo depois.

`--dia` tem de estar dentro do período coberto pelo `calendar.txt` de **todos** os GTFS combinados — por exemplo, o GTFS do Metro descarregado em 2026-09 só é válido até 2026-10-25, enquanto o da UNIR vai até 2027-08-31; ao atualizar qualquer um dos ficheiros, verificar o novo período de validade e ajustar `--dia` (uma terça-feira normal, dentro da interseção dos dois calendários).

## O que falta para ficar mais completo

1. **Fiabilidade real**: construir, a partir do histórico de GTFS-RT já em produção, uma agregação por paragem+linha+hora (mediana, p80/p90/p95, taxa de cancelamento) e passá-la a `build_explore_povoa.py --fiabilidade ficheiro.csv` (colunas: `route_id,stop_id,hour,delay_p50_s,delay_p90_s,cancel_rate` — ver a função `load_reliability` para o formato exato esperado).
2. ~~**Rede viária real**~~ — feito: geometria e classificação reais (`build_road_real.py`). Falta: velocidades por troço calibradas (hoje são uma suposição por tipo de via, ver nota acima), capacidade por troço.
3. ~~**População em grelha**~~ — feito: BGRI 2021 já importado (64 255 habitantes no concelho, por 793 subsecções estatísticas).
4. **Calibração pontual com o Google Maps Platform**: usar a Directions/Distance Matrix API para validar as velocidades sintéticas contra algumas rotas reais — a correr a partir de uma máquina com acesso de rede normal, e sem exceder o limite gratuito mensal.

Nada disto exige mudar o front-end: `index.html` já lê o formato final; só os pipelines em `pipeline/` precisam de outra fonte.

## Publicar

Site estático — qualquer alojamento serve. Para GitHub Pages: criar o repositório, `git push`, ativar Pages a servir a raiz do `main`. Uma página estática no GitHub Pages não define `X-Frame-Options`/`frame-ancestors`, por isso **pode ser embebida num iframe** (ex. um widget doutra aplicação municipal), ao contrário do planeador do Metro do Porto (bloqueado por CSP).

## Fontes e licenças

- Metro do Porto: GTFS oficial (`agency.txt`: Metro do Porto, https://www.metrodoporto.pt).
- UNIR Mobilidade da Área Metropolitana do Porto: GTFS oficial (https://unirmobilidade.pt), filtrado à zona de estudo.
- Mapa base: Esri (World Dark Gray Canvas + Reference), © Esri, HERE, Garmin, © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Geocodificação: Nominatim.
- Motor de mapa: [Leaflet](https://leafletjs.com/). Motor de isócronas inspirado em [munich-transit-reach](https://github.com/ilyas-ku/munich-transit-reach) / [rhein-main-transit-reach](https://github.com/ilyas-ku/rhein-main-transit-reach) (ilyas-ku).
