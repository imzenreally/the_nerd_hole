# InfraGraph

Map your homelab infrastructure from config files to a readable graph.

InfraGraph ingests infrastructure configuration sources (Docker Compose, Nginx proxy configs, host inventories) and produces a unified graph model that answers:

- What services exist?
- What depends on what?
- What ports are exposed?
- What is public vs internal?
- What reverse proxies route to which backends?
- What breaks if one node or service goes down?

## Install

```bash
# Clone and install in development mode
git clone <repo-url>
cd infragraph
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

### Scan for config files

```bash
infragraph scan ./examples/homelab
```

```
Scanned 3 file(s):
  - examples/homelab/docker-compose.yaml
  - examples/homelab/hosts.yaml
  - examples/homelab/nginx-proxies.yaml

Graph: 33 nodes, 31 edges
```

### Generate a report

```bash
infragraph report ./examples/homelab
infragraph report ./examples/homelab --format json
infragraph report ./config -o report.md
```

Produces a Markdown report with:
- Service inventory with trust zones and ports
- Host inventory
- Reverse proxy route table
- Exposure summary (public / proxy / internal / localhost)
- Dependency chains
- Findings: broken references, missing backends, proxy bypasses, SPOFs, orphaned services

### Render a diagram

```bash
infragraph render ./examples/homelab
infragraph render ./examples/homelab -o graph.mmd
```

Outputs a Mermaid diagram with color-coded trust zones:
- Red = public internet
- Yellow = behind reverse proxy
- Green = internal LAN
- Blue = localhost only

Paste the output into any Mermaid renderer (GitHub markdown, mermaid.live, etc.).

### Export raw graph

```bash
infragraph export ./examples/homelab
infragraph export ./examples/homelab -o graph.json
```

## Supported Config Sources

### Phase 1 (implemented)

| Source | Detected Files |
|--------|---------------|
| Docker Compose | `docker-compose.yaml`, `compose.yml`, etc. |
| Nginx Proxy (YAML) | `nginx-proxies.yaml`, `proxies.yml` |
| Host Inventory | `hosts.yaml`, `hosts.json`, `inventory.yml` |

### Phase 2 (planned)

- Kubernetes / k3s manifests
- Traefik / Nginx Proxy Manager exports
- DNS records (JSON/YAML)
- TLS certificate inventory

## Config File Formats

### Docker Compose

Standard `docker-compose.yaml` — InfraGraph extracts services, ports, dependencies, networks, images, labels, and volumes.

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
```

## Analysis

InfraGraph runs these analyzers on the merged graph:

| Analyzer | Detects |
|----------|---------|
| **Exposure** | Publicly exposed services, containers bypassing reverse proxy |
| **Dependencies** | Broken references, orphaned services, routes with missing backends |
| **SPOF** | Single points of failure, single reverse proxy, single host setups |

## Project Structure

```
infragraph/
├── src/infragraph/
│   ├── cli/           # Click CLI commands
│   ├── parsers/       # One module per config source
│   ├── graph/         # Typed data model + merge engine
│   ├── analyzers/     # Exposure, dependency, SPOF checks
│   └── renderers/     # JSON, Markdown, Mermaid output
├── tests/             # 28 tests covering all modules
├── examples/homelab/  # Sample fixtures
└── docs/              # Architecture documentation
```

## Development

```bash
# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/
```

## Backlog

### Next up

- [ ] Graphviz/DOT output renderer
- [ ] Golden-file snapshot tests for report stability
- [ ] `--watch` mode for live re-scanning
- [ ] Raw nginx.conf parser (not just YAML representation)
- [ ] Docker container metadata JSON import (docker inspect output)

### Phase 2 sources

- [ ] Kubernetes manifest parser (Deployments, Services, Ingress)
- [ ] Traefik dynamic config parser
- [ ] Nginx Proxy Manager API/export parser
- [ ] DNS zone file / JSON record parser
- [ ] TLS certificate inventory parser (from files or ACME exports)

### Analysis improvements

- [ ] Network segmentation analysis (which services share networks)
- [ ] Volume mount analysis (shared data dependencies)
- [ ] Restart policy audit
- [ ] Port conflict detection
- [ ] Health check coverage report
- [ ] "What breaks if X goes down" impact query

### Output improvements

- [ ] Interactive HTML report
- [ ] Diff mode (compare two scans)
- [ ] CI-friendly exit codes (fail on critical findings)
- [ ] SARIF output for security tooling integration
- [ ] Configurable severity thresholds

### UX

- [ ] Config file for default options (`.infragraph.yaml`)
- [ ] Auto-detect project root
- [ ] Color-coded terminal output for findings
- [ ] `infragraph init` to generate sample configs

## License

MIT
