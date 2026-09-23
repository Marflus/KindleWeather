"""A fallback for host name lookups, asked straight to DNS servers.

Python packages built apart from the Kindle can fail to resolve names through
the system ("Temporary failure in name resolution") even with Wi-Fi up. When
the system lookup fails, the name is sent to the DNS servers of
/etc/resolv.conf, then to public ones.
"""

from __future__ import annotations

import random
import socket
import struct
from pathlib import Path

PUBLIC_SERVERS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")
TIMEOUT = 3
_TYPE_A, _CLASS_IN = 1, 1

_system_getaddrinfo = socket.getaddrinfo


def install() -> None:
    """Fall back on direct DNS queries when the system cannot resolve a name."""
    socket.getaddrinfo = _getaddrinfo


def _getaddrinfo(host, port, *args, **kwargs):
    try:
        return _system_getaddrinfo(host, port, *args, **kwargs)
    except socket.gaierror:
        addresses = resolve(host) if isinstance(host, str) else []
        if not addresses:
            raise
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))
            for address in addresses
        ]


def resolve(host: str) -> list[str]:
    """IPv4 addresses of host, from the first DNS server that answers."""
    servers = [*nameservers(), *PUBLIC_SERVERS]
    for server in dict.fromkeys(servers):
        query_id = random.randrange(1 << 16)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
                connection.settimeout(TIMEOUT)
                connection.sendto(query(host, query_id), (server, 53))
                reply = connection.recv(4096)
        except OSError:
            continue
        addresses = parse_reply(reply, query_id)
        if addresses:
            return addresses
    return []


def nameservers(resolv_conf: Path = Path("/etc/resolv.conf")) -> list[str]:
    try:
        lines = resolv_conf.read_text().splitlines()
    except OSError:
        return []
    return [
        line.split()[1]
        for line in lines
        if line.startswith("nameserver") and len(line.split()) > 1 and "." in line.split()[1]
    ]


def query(host: str, query_id: int) -> bytes:
    """A recursive DNS query for the A records of host."""
    header = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    name = b"".join(bytes([len(label)]) + label.encode() for label in host.split(".") if label)
    return header + name + b"\0" + struct.pack(">HH", _TYPE_A, _CLASS_IN)


def parse_reply(reply: bytes, query_id: int) -> list[str]:
    """IPv4 addresses among the answers of a DNS reply to query_id."""
    try:
        reply_id, flags, questions, answers = struct.unpack_from(">HHHH", reply)
        if reply_id != query_id or flags & 0x000F:
            return []
        offset = 12
        for _ in range(questions):
            offset = _skip_name(reply, offset) + 4
        addresses = []
        for _ in range(answers):
            offset = _skip_name(reply, offset)
            kind, klass, _, length = struct.unpack_from(">HHIH", reply, offset)
            offset += 10
            if kind == _TYPE_A and klass == _CLASS_IN and length == 4:
                addresses.append(socket.inet_ntoa(reply[offset : offset + 4]))
            offset += length
        return addresses
    except (struct.error, IndexError):
        return []


def _skip_name(reply: bytes, offset: int) -> int:
    while True:
        length = reply[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:  # Compressed: a pointer ends the name.
            return offset + 2
        offset += length + 1
