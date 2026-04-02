"""Nginx reverse proxy config parser.

This parser handles a simplified YAML representation of nginx proxy configs,
not raw nginx.conf syntax. This makes it easier to integrate with tools that
export proxy configs as structured data (e.g., Nginx Proxy Manager exports).

Expected format (nginx-proxies.yaml):
    proxies:
      - server_name: app.example.com
        listen: 443
        ssl: true
        locations:
          - path: /
            proxy_pass: http://app:8080
          - path: /api
            proxy_pass: http://api:3000
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from infragraph.graph.model import (
    Edge,
    EdgeType,
    GraphFragment,
    Node,
    NodeType,
    Port,
    Protocol,
    TrustZone,
)
from infragraph.parsers.base import BaseParser

_NGINX_FILENAMES = {"nginx-proxies.yaml", "nginx-proxies.yml", "proxies.yaml", "proxies.yml"}


class NginxParser(BaseParser):
    @property
    def source_type(self) -> str:
        return "nginx"

    def can_parse(self, path: Path) -> bool:
        return path.name in _NGINX_FILENAMES

    def parse(self, path: Path) -> GraphFragment:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return GraphFragment()

        proxies: list[dict[str, Any]] = data.get("proxies", [])
        if not proxies:
            return GraphFragment()

        fragment = GraphFragment(source=str(path))

        # Create the nginx proxy node itself
        nginx_node = Node(
            id="nginx",
            name="nginx",
            node_type=NodeType.SERVICE,
            trust_zone=TrustZone.PROXY,
            labels={"role": "reverse-proxy"},
            source="nginx",
        )

        for proxy in proxies:
            if not isinstance(proxy, dict):
                continue

            server_name = proxy.get("server_name", "")
            listen_port = proxy.get("listen", 80)
            uses_ssl = proxy.get("ssl", False)

            # Add listen port to nginx node
            nginx_node.ports.append(
                Port(
                    host_port=int(listen_port),
                    container_port=int(listen_port),
                    protocol=Protocol.HTTPS if uses_ssl else Protocol.HTTP,
                )
            )

            # Create a DNS name node for the server_name
            if server_name:
                dns_node = Node(
                    id=f"dns:{server_name}",
                    name=server_name,
                    node_type=NodeType.DNS_NAME,
                    trust_zone=TrustZone.PUBLIC,
                    metadata={"ssl": uses_ssl},
                    source="nginx",
                )
                fragment.nodes.append(dns_node)
                fragment.edges.append(
                    Edge(
                        source_id=f"dns:{server_name}",
                        target_id="nginx",
                        edge_type=EdgeType.RESOLVES_TO,
                    )
                )

            # Create route nodes for each location
            locations: list[dict[str, Any]] = proxy.get("locations", [])
            for loc in locations:
                if not isinstance(loc, dict):
                    continue

                loc_path = loc.get("path", "/")
                proxy_pass = loc.get("proxy_pass", "")
                if not proxy_pass:
                    continue

                backend = _parse_proxy_pass(proxy_pass)
                if not backend:
                    continue

                route_id = f"route:{server_name}{loc_path}"
                route_node = Node(
                    id=route_id,
                    name=f"{server_name}{loc_path}",
                    node_type=NodeType.ROUTE,
                    trust_zone=TrustZone.PROXY,
                    metadata={
                        "server_name": server_name,
                        "path": loc_path,
                        "proxy_pass": proxy_pass,
                        "backend_host": backend["host"],
                        "backend_port": backend["port"],
                    },
                    source="nginx",
                )
                fragment.nodes.append(route_node)

                # nginx -> route
                fragment.edges.append(
                    Edge(
                        source_id="nginx",
                        target_id=route_id,
                        edge_type=EdgeType.ROUTES_TO,
                    )
                )

                # route -> backend service
                fragment.edges.append(
                    Edge(
                        source_id=route_id,
                        target_id=backend["host"],
                        edge_type=EdgeType.ROUTES_TO,
                        metadata={"port": backend["port"]},
                    )
                )

        fragment.nodes.append(nginx_node)
        return fragment


def _parse_proxy_pass(proxy_pass: str) -> dict[str, Any] | None:
    """Extract host and port from a proxy_pass value like http://app:8080."""
    url = proxy_pass.strip()
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break

    url = url.rstrip("/")

    if ":" in url:
        host, port_str = url.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return None
        return {"host": host, "port": port}

    return {"host": url, "port": 80}
