# InfraGraph Architecture

## Overview

InfraGraph is a CLI tool that ingests infrastructure configuration sources and
produces a unified graph model of your homelab or service stack. It answers
questions about service dependencies, exposed ports, trust boundaries, and
single points of failure.

## Data Flow

```
Config Sources          Parsers           Graph Engine         Analyzers          Renderers
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ docker-compose│──►│ compose.py   │──►│              │    │ exposure     │    │ json_export  │
│ nginx.conf   │──►│ nginx.py     │──►│  InfraGraph  │──►│ dependencies │──►│ markdown     │
│ hosts.yaml   │──►│ inventory.py │──►│              │    │ spof         │    │ mermaid      │
└──────────────┘    └──────────────┘    └──────────────┘    │ orphans      │    └──────────────┘
                                                             └──────────────┘
```

## Core Model

The internal graph uses these node types:

| Type        | Represents                                    |
|-------------|-----------------------------------------------|
| Host        | A physical or virtual machine                 |
| Service     | A logical service (e.g., "postgres", "nginx") |
| Container   | A running container instance                  |
| Route       | A reverse proxy route (domain -> backend)     |
| Port        | An exposed port binding                       |
| DNSName     | A DNS record pointing to a host/service       |
| Certificate | A TLS certificate covering DNS names          |

### Edges (Dependencies)

Edges represent relationships:
- `depends_on` — service A requires service B
- `routes_to` — proxy route forwards to a backend service
- `runs_on` — container runs on a host
- `exposes` — service exposes a port
- `resolves_to` — DNS name resolves to a host/service
- `secures` — certificate secures a DNS name

### Trust Boundaries

Every node is tagged with a trust zone:
- `public` — reachable from the internet
- `proxy` — behind a reverse proxy
- `internal` — LAN-only
- `localhost` — loopback only

## Module Layout

```
src/infragraph/
├── cli/           # Click CLI commands
│   └── main.py
├── parsers/       # One module per config source
│   ├── base.py    # Abstract parser interface
│   ├── compose.py # Docker Compose
│   ├── nginx.py   # Nginx configs
│   └── inventory.py # Host inventory
├── graph/
│   ├── model.py   # Typed dataclasses for the graph
│   └── engine.py  # Graph construction, merge, dedup
├── analyzers/
│   ├── base.py    # Analyzer interface
│   ├── exposure.py
│   ├── dependencies.py
│   └── spof.py
└── renderers/
    ├── base.py    # Renderer interface
    ├── json_export.py
    ├── markdown.py
    └── mermaid.py
```

## Design Principles

1. **Parsers are pure** — they take file content, return graph fragments. No side effects.
2. **Graph engine merges** — deduplication happens by matching on (type, name, host).
3. **Analyzers are read-only** — they query the graph and return findings.
4. **Renderers are stateless** — they take a graph + findings and produce output.
5. **CLI orchestrates** — it wires parsers, engine, analyzers, and renderers together.

## Extension Points

Adding a new config source:
1. Create `parsers/new_source.py` implementing `BaseParser`
2. Register it in the CLI's source auto-detection
3. Add fixture files and golden tests

Adding a new analyzer:
1. Create `analyzers/new_check.py` implementing `BaseAnalyzer`
2. Return structured findings
3. Renderers pick up findings automatically
