"""Visitor source provenance is separate from authentication and voice proxy trust."""
import asyncio
from functools import lru_cache
from ipaddress import ip_address, ip_network
import os
from pathlib import Path
import socket

from ip2region import searcher, util

from backend.services.proxy_discovery import ProxyDiscovery


async def _resolve_public_edge():
    rows = await asyncio.get_running_loop().getaddrinfo(
        "lxm-entry-mobile-gateway", 8081, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    return {row[4][0] for row in rows}


public_edge = ProxyDiscovery(resolver=_resolve_public_edge)
PRIVATE = tuple(map(ip_network, ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")))


def verified_address(value, *, internal_clients=(), intermediaries=()):
    try:
        address = ip_address(value)
    except ValueError:
        return None
    address = getattr(address, "ipv4_mapped", None) or address
    if str(address) in intermediaries or address.is_multicast or address.is_unspecified:
        return None
    if address.is_global:
        return address
    # Container bridges, host NAT and preview proxies also present as private peers.
    # Confirm a private client only when the operator has verified its direct edge path.
    if str(address) in internal_clients and any(address in subnet for subnet in PRIVATE):
        return address
    return None


async def source_for_request(request):
    proxy = request.scope.get("voice_proxy") or {}
    peer = proxy.get("peer")
    if not peer:
        return None, None
    if proxy.get("trusted"):
        edge = "main"
    else:
        public = await public_edge.refresh(peer=peer)
        edge = "public" if peer in public["trusted_addresses"] else None
    if not edge:
        return None, None
    # Only the matching edge location sets this header, replacing any client input.
    if request.headers.get("x-lxm-visitor-edge") != edge:
        return None, None
    internal = os.getenv("VISITOR_VERIFIED_LAN_CLIENTS", "").split(",")
    excluded = os.getenv("VISITOR_INTERMEDIARIES", "").split(",")
    address = verified_address(request.headers.get("x-lxm-visitor-source"), internal_clients={v.strip() for v in internal},
                               intermediaries={peer, *(v.strip() for v in excluded)})
    return edge, address


@lru_cache(maxsize=2)
def _database(path, version):
    util.verify_from_file(str(path))
    return util.load_content_from_file(str(path))


def lookup_region(address):
    directory = Path(os.getenv("VISITOR_GEO_DIR", "var/visitor-geo"))
    version = util.IPv4 if address.version == 4 else util.IPv6
    path = directory / f"ip2region_v{address.version}.xdb"
    reader = searcher.new_with_buffer(version, _database(path, address.version))
    return reader.search(str(address))


def network_snapshot(address, lookup=lookup_region):
    if address is None:
        return {"ip": None, "region": "来源未知"}
    if any(address in subnet for subnet in PRIVATE):
        return {"ip": str(address), "region": "内网"}
    region = "归属地未知"
    try:
        fields = lookup(address).split("|")
        if len(fields) >= 3 and fields[1] not in ("", "0"):
            province = fields[1].removesuffix("省").removesuffix("市")
            city = fields[2].removesuffix("市")
            region = "·".join([province, city]) if city not in ("", "0", province) else province
    except Exception:
        # The pinned xdb binding also raises plain Exception for invalid database headers.
        pass
    return {"ip": str(address), "region": region}
