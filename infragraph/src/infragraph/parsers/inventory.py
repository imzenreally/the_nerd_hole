"""Static host inventory parser.

Expected format (hosts.yaml or hosts.json):
    hosts:
      - name: proxmox-01
        ip: 192.168.1.10
        role: hypervisor
        os: Proxmox VE 8.1
        services:
          - name: pve-web
            port: 8006
            protocol: https
      - name: nas-01
        ip: 192.168.1.20
        role: storage
        os: TrueNAS SCALE
"""

from __future__ import annotations

import json
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

_INVENTORY_FILENAMES = {"hosts.yaml", "hosts.yml", "hosts.json", "inventory.yaml", "inventory.yml"}


class InventoryParser(BaseParser):
    @property
    def source_type(self) -> str:
        return "inventory"

    def can_parse(self, path: Path) -> bool:
        return path.name in _INVENTORY_FILENAMES

    def parse(self, path: Path) -> GraphFragment:
        data = _load_file(path)
        if not isinstance(data, dict):
            return GraphFragment()

        hosts: list[dict[str, Any]] = data.get("hosts", [])
        if not hosts:
            return GraphFragment()

        fragment = GraphFragment(source=str(path))

        for host_def in hosts:
            if not isinstance(host_def, dict):
                continue

            name = host_def.get("name", "")
            if not name:
                continue

            ip = host_def.get("ip", "")
            role = host_def.get("role", "")
            os_name = host_def.get("os", "")

            host_node = Node(
                id=name,
                name=name,
                node_type=NodeType.HOST,
                trust_zone=TrustZone.INTERNAL,
                labels={"role": role} if role else {},
                metadata={"ip": ip, "os": os_name},
                source="inventory",
            )

            # Parse services running on this host
            host_services: list[dict[str, Any]] = host_def.get("services", [])
            for svc_def in host_services:
                if not isinstance(svc_def, dict):
                    continue

                svc_name = svc_def.get("name", "")
                if not svc_name:
                    continue

                svc_port = svc_def.get("port")
                svc_proto = svc_def.get("protocol", "tcp")
                proto = _parse_protocol(svc_proto)

                ports: list[Port] = []
                if svc_port:
                    ports.append(Port(host_port=int(svc_port), container_port=int(svc_port), protocol=proto))
                    host_node.ports.append(
                        Port(host_port=int(svc_port), container_port=int(svc_port), protocol=proto)
                    )

                svc_node = Node(
                    id=f"{name}:{svc_name}",
                    name=svc_name,
                    node_type=NodeType.SERVICE,
                    trust_zone=TrustZone.INTERNAL,
                    ports=ports,
                    metadata={"host": name},
                    source="inventory",
                )
                fragment.nodes.append(svc_node)
                fragment.edges.append(
                    Edge(
                        source_id=f"{name}:{svc_name}",
                        target_id=name,
                        edge_type=EdgeType.RUNS_ON,
                    )
                )

            fragment.nodes.append(host_node)

        return fragment


def _load_file(path: Path) -> Any:
    text = path.read_text()
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _parse_protocol(proto: str) -> Protocol:
    mapping = {
        "tcp": Protocol.TCP,
        "udp": Protocol.UDP,
        "http": Protocol.HTTP,
        "https": Protocol.HTTPS,
    }
    return mapping.get(proto.lower(), Protocol.TCP)
