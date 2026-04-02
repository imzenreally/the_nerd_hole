# InfraGraph

Map your homelab infrastructure from config files to a readable graph.

InfraGraph ingests infrastructure configuration sources (Docker Compose, Nginx proxy configs, host inventories) and produces a unified graph model that answers:

- What services exist and where do they run?
- What depends on what?
- What ports are exposed and to whom?
- What is public vs. internal vs. localhost?
- Which reverse proxies route to which backends?
- What breaks if a node or service goes down?

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Status](https://img.shields.io/badge/status-alpha%20v0.1.0-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Install

```bash
git clone <repo-url>
cd infragraph
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Quick Start

Point InfraGraph at a directory containing your infrastructure configs:

```bash
# See what InfraGraph finds
infragraph scan ./examples/homelab

# Generate a full Markdown report
infragraph report ./examples/homelab -o report.md

# Render a Mermaid diagram
infragraph render ./examples/homelab -o graph.mmd

# Export raw graph as JSON
infragraph export ./examples/homelab -o graph.json
```

## Commands

### `infragraph scan <path>`

Recursively scans a directory for recognized config files and reports what was found.

```
$ infragraph scan ./examples/homelab

Scanned 3 file(s):
  - examples/homelab/docker-compose.yaml
  - examples/homelab/hosts.yaml
  - examples/homelab/nginx-proxies.yaml

Graph: 33 nodes, 31 edges
```

### `infragraph report <path>`

Generates a structured infrastructure analysis report.

```bash
infragraph report ./examples/homelab                  # Markdown to stdout
infragraph report ./examples/homelab --format json     # JSON format
infragraph report ./examples/homelab -o report.md      # Save to file
```

**Report sections:**

| Section | Contents |
|---------|----------|
| Summary | Node/edge counts, finding totals by severity |
| Services | Name, type, trust zone, ports, container image |
| Hosts | Name, IP, role, OS, services running on each |
| Routes | Domain, path, backend target, SSL status |
| Exposure | Services grouped by trust zone (public → localhost) |
| Dependencies | Dependency chains and broken references |
| Findings | All issues grouped by severity (critical → info) |

### `infragraph render <path>`

Renders the infrastructure graph as a diagram.

```bash
infragraph render ./examples/homelab                   # Mermaid to stdout
infragraph render ./examples/homelab -f json           # JSON format
infragraph render ./examples/homelab -o graph.mmd      # Save to file
```

Outputs a Mermaid diagram with:

- **Color-coded trust zones** as subgraphs:
  - Red = public internet
  - Yellow = behind reverse proxy
  - Green = internal LAN
  - Blue = localhost only
- **Node shapes** by type: rectangles (containers), circles (DNS), rhombus (routes), stadiums (hosts)
- **Port numbers** displayed inline (up to 3 per node)
- **Edge labels**: "depends on", "routes to", "runs on", etc.

Paste the output into any Mermaid renderer — GitHub markdown, [mermaid.live](https://mermaid.live), Obsidian, etc.

### `infragraph export <path>`

Exports the raw graph and analysis findings as JSON.

```bash
infragraph export ./examples/homelab -o graph.json
```

## Supported Config Sources

### Phase 1 (implemented)

| Source | Detected Files | What's Extracted |
|--------|---------------|------------------|
| Docker Compose | `docker-compose.yaml`, `compose.yml` | Services, ports, dependencies, networks, images, labels, volumes, restart policies |
| Nginx Proxy (YAML) | `nginx-proxies.yaml`, `proxies.yml` | Reverse proxy routes, server names, SSL/TLS, location paths, backend targets |
| Host Inventory | `hosts.yaml`, `hosts.json`, `inventory.yml` | Hosts, IPs, roles, OS, services running on each host |

### Phase 2 (planned)

- Kubernetes / k3s manifests (Deployments, Services, Ingress)
- Traefik / Nginx Proxy Manager exports
- DNS records (JSON/YAML zone files)
- TLS certificate inventory (files or ACME exports)
- Raw `nginx.conf` parser
- Docker inspect JSON import

## Config File Formats

### Docker Compose

Standard `docker-compose.yaml` — InfraGraph extracts services, ports, `depends_on` (list and dict forms), `links`, networks, images, labels, volumes, and restart policies.

```yaml
services:
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - app
      - api
    networks:
      - frontend
      - backend
```

Port parsing handles all Docker formats: `"8080:80"`, `"127.0.0.1:3000:3000"`, `"8080:80/udp"`, and bare container ports.

### Nginx Proxy Config (YAML)

A structured YAML representation of reverse proxy routes:

```yaml
proxies:
  - server_name: app.example.com
    listen: 443
    ssl: true
    locations:
      - path: /
        proxy_pass: http://app:8080
      - path: /api
        proxy_pass: http://api:3000
```

InfraGraph creates DNS name nodes, route nodes, and edges connecting domains → nginx → routes → backend services. It also flags routes pointing to backends that don't exist in the graph.

### Host Inventory

```yaml
hosts:
  - name: server-01
    ip: 192.168.1.10
    role: docker-host
    os: Ubuntu 24.04 LTS
    services:
      - name: ssh
        port: 22
        protocol: tcp
      - name: node-exporter
        port: 9100
        protocol: tcp
```

## Data Model

### Node Types

| Type | Description | Shape (Mermaid) |
|------|-------------|----------------|
| `HOST` | Physical or virtual machine | Stadium `[[ ]]` |
| `SERVICE` | Logical service (postgres, nginx) | Rounded `( )` |
| `CONTAINER` | Docker container instance | Rectangle `[ ]` |
| `ROUTE` | Reverse proxy route (domain → backend) | Rhombus `{ }` |
| `DNS_NAME` | DNS record | Circle `(( ))` |
| `CERTIFICATE` | TLS certificate (future) | Flag `> ]` |

### Trust Zones

| Zone | Meaning | Mermaid Color |
|------|---------|--------------|
| `PUBLIC` | Reachable from the internet | Red |
| `PROXY` | Behind a reverse proxy | Yellow |
| `INTERNAL` | LAN-only | Green |
| `LOCALHOST` | Loopback only (127.0.0.1) | Blue |
| `UNKNOWN` | Not yet classified | Grey |

Trust zones are assigned automatically based on port bindings (`0.0.0.0` → public, `127.0.0.1` → localhost), proxy routing, and source context.

### Edge Types

| Type | Meaning |
|------|---------|
| `DEPENDS_ON` | Service A requires service B |
| `ROUTES_TO` | Proxy route forwards to backend |
| `RUNS_ON` | Container/service runs on a host |
| `EXPOSES` | Service exposes a port |
| `RESOLVES_TO` | DNS name resolves to host/service |
| `SECURES` | Certificate secures a DNS name |
| `LINKS_TO` | Docker link between services |

## Analysis

InfraGraph runs three analyzers on the merged graph and reports findings at three severity levels:

### Exposure Analyzer

| Finding | Severity | Trigger |
|---------|----------|---------|
| Public service | INFO | Node has PUBLIC trust zone with published ports |
| Proxy bypass | WARNING | Container has published ports but no reverse proxy route |

### Dependency Analyzer

| Finding | Severity | Trigger |
|---------|----------|---------|
| Broken reference | WARNING | Edge points to a node that doesn't exist |
| Orphaned service | INFO | Service with no incoming or outgoing edges |
| Missing backend | CRITICAL | Proxy route targets a backend not in the graph |

### SPOF Analyzer

| Finding | Severity | Trigger |
|---------|----------|---------|
| Critical dependency | WARNING | Node has 2+ services depending on it |
| Single reverse proxy | WARNING | Only one nginx instance handling all routes |
| Single host | INFO | All services running on a single host |

## Architecture

```
┌──────────────────────────────────────────────────┐
│                     CLI                           │
│          scan · report · render · export          │
└──────────┬───────────────────────────┬───────────┘
           │                           │
     ┌─────▼─────┐             ┌──────▼──────┐
     │  Parsers   │             │  Analyzers  │
     │            │             │             │
     │ Compose    │             │ Exposure    │
     │ Nginx      │──fragments─▶│ Dependencies│
     │ Inventory  │             │ SPOF        │
     └─────┬──────┘             └──────┬──────┘
           │                           │
     ┌─────▼──────────────────────────▼──────┐
     │            Graph Engine                │
     │                                        │
     │  InfraGraphModel                       │
     │  ├─ nodes: dict[key, Node]            │
     │  ├─ edges: list[Edge]                 │
     │  ├─ add_node() — merge by (type, id)  │
     │  └─ find_nodes() / find_edges()       │
     └─────────────────┬─────────────────────┘
                       │
               ┌───────▼───────┐
               │   Renderers   │
               │               │
               │ Markdown      │
               │ Mermaid       │
               │ JSON          │
               └───────────────┘
```

**Design principles:**
- Parsers are pure: file content → `GraphFragment` (no side effects)
- Graph engine merges fragments with deduplication by `(type, name)` key
- Analyzers are read-only: query graph, return findings
- Renderers are stateless: graph + findings → output string
- CLI orchestrates: wires all components together

## Project Structure

```
infragraph/
├── src/infragraph/
│   ├── __init__.py
│   ├── cli/
│   │   └── main.py              # Click CLI: scan, report, render, export
│   ├── parsers/
│   │   ├── base.py              # BaseParser ABC
│   │   ├── compose.py           # Docker Compose parser
│   │   ├── nginx.py             # Nginx reverse proxy YAML parser
│   │   └── inventory.py         # Host inventory parser
│   ├── graph/
│   │   ├── model.py             # Node, Edge, GraphFragment, InfraGraphModel
│   │   └── engine.py            # GraphEngine: ingest, merge, query
│   ├── analyzers/
│   │   ├── base.py              # Finding, AnalysisReport, BaseAnalyzer ABC
│   │   ├── exposure.py          # Public exposure + proxy bypass detection
│   │   ├── dependencies.py      # Broken refs, orphans, missing backends
│   │   └── spof.py              # Single points of failure
│   └── renderers/
│       ├── base.py              # BaseRenderer ABC
│       ├── json_export.py       # JSON graph + findings export
│       ├── markdown.py          # Markdown report with tables
│       └── mermaid.py           # Mermaid diagram with trust zone subgraphs
├── tests/
│   ├── test_analyzers.py        # Exposure, dependency, SPOF analyzer tests
│   ├── test_compose_parser.py   # Port parsing, services, depends_on, networks
│   ├── test_graph_engine.py     # Ingestion, file collection, merging
│   ├── test_inventory_parser.py # Host/service nodes, trust zones
│   ├── test_nginx_parser.py     # Server names, locations, proxy_pass
│   └── test_renderers.py        # JSON, Markdown, Mermaid output
├── examples/
│   └── homelab/
│       ├── docker-compose.yaml  # 10 services, 4 networks, 6 volumes
│       ├── nginx-proxies.yaml   # 6 reverse proxy routes (1 broken)
│       └── hosts.yaml           # 3 hosts with services
├── docs/
│   └── ARCHITECTURE.md          # Architecture diagrams and design docs
└── pyproject.toml               # Project metadata, dependencies, tool config
```

## Extending InfraGraph

### Adding a new config source

1. Create `src/infragraph/parsers/my_source.py` inheriting `BaseParser`
2. Implement `can_parse(path) -> bool`, `parse(path) -> GraphFragment`, and `source_type` property
3. Register the parser in `cli/main.py` → `_build_engine()`
4. Add tests in `tests/test_my_source_parser.py`

### Adding a new analyzer

1. Create `src/infragraph/analyzers/my_check.py` inheriting `BaseAnalyzer`
2. Implement `analyze(graph) -> list[Finding]` and `name` property
3. Register in `cli/main.py` → `ANALYZERS` list
4. Renderers automatically pick up new findings

### Adding a new output format

1. Create `src/infragraph/renderers/my_format.py` inheriting `BaseRenderer`
2. Implement `render(graph, report) -> str` and `format_name` property
3. Register in `cli/main.py` → `RENDERERS` dict

## Example Output

The included homelab example (`examples/homelab/`) produces:

- **33 nodes** — 10 containers, 6 routes, 6 DNS names, 3 hosts, services, networks
- **31 edges** — dependencies, routes, host assignments
- **Findings**: missing backend (`old-app` referenced by proxy but doesn't exist), potential SPOFs, proxy bypass warnings

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=infragraph

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Format
ruff format src/ tests/
```

## Backlog

### Next up

- [ ] Graphviz/DOT output renderer
- [ ] Golden-file snapshot tests for report stability
- [ ] `--watch` mode for live re-scanning
- [ ] Raw `nginx.conf` parser (not just YAML representation)
- [ ] Docker inspect JSON import

### Analysis improvements

- [ ] Network segmentation analysis (which services share Docker networks)
- [ ] Volume mount analysis (shared data dependencies)
- [ ] Restart policy audit
- [ ] Port conflict detection
- [ ] Health check coverage report
- [ ] Impact query: "what breaks if X goes down"

### Output improvements

- [ ] Interactive HTML report
- [ ] Diff mode (compare two scans over time)
- [ ] CI-friendly exit codes (fail on critical findings)
- [ ] SARIF output for security tooling integration
- [ ] Color-coded terminal output

### UX

- [ ] Config file for defaults (`.infragraph.yaml`)
- [ ] Auto-detect project root
- [ ] `infragraph init` to scaffold sample configs

## License

MIT
