"""Dependency-free network I/O: OSC over UDP and Art-Net DMX."""
import collections
import socket
import struct
import threading
import time


# -- OSC encoding ---------------------------------------------------------
def _pad(b):
    return b + b"\x00" * (4 - len(b) % 4)


def osc_message(address, *args):
    tags = ","
    payload = b""
    for a in args:
        if isinstance(a, bool):
            tags += "T" if a else "F"
        elif isinstance(a, int):
            tags += "i"
            payload += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            payload += struct.pack(">f", a)
        elif isinstance(a, bytes):
            tags += "b"
            payload += struct.pack(">i", len(a)) + a + b"\x00" * (-len(a) % 4)
        else:
            tags += "s"
            payload += _pad(str(a).encode("utf-8"))
    return _pad(address.encode("utf-8")) + _pad(tags.encode("ascii")) + payload


def _read_str(data, pos):
    end = data.index(b"\x00", pos)
    s = data[pos:end].decode("utf-8", "replace")
    return s, (end + 4) & ~3


def osc_parse(data):
    """Decode a packet into a list of (address, [args]); bundles are flattened."""
    out = []
    try:
        if data.startswith(b"#bundle\x00"):
            pos = 16
            while pos + 4 <= len(data):
                (size,) = struct.unpack_from(">i", data, pos)
                pos += 4
                out.extend(osc_parse(data[pos:pos + size]))
                pos += size
            return out
        address, pos = _read_str(data, 0)
        if pos >= len(data) or data[pos:pos + 1] != b",":
            return [(address, [])]
        tags, pos = _read_str(data, pos)
        args = []
        for t in tags[1:]:
            if t == "i":
                args.append(struct.unpack_from(">i", data, pos)[0]); pos += 4
            elif t == "f":
                args.append(struct.unpack_from(">f", data, pos)[0]); pos += 4
            elif t == "d":
                args.append(struct.unpack_from(">d", data, pos)[0]); pos += 8
            elif t == "h":
                args.append(struct.unpack_from(">q", data, pos)[0]); pos += 8
            elif t in "sS":
                s, pos = _read_str(data, pos)
                args.append(s)
            elif t == "b":
                (n,) = struct.unpack_from(">i", data, pos)
                args.append(bytes(data[pos + 4:pos + 4 + n]))
                pos = (pos + 4 + n + 3) & ~3
            elif t == "T":
                args.append(True)
            elif t == "F":
                args.append(False)
            elif t in "NI":
                args.append(None)
            elif t in "tcrm":
                pos += 8 if t == "t" else 4
        out.append((address, args))
    except (ValueError, struct.error, IndexError):
        pass  # malformed packet: ignore
    return out


# -- UDP ------------------------------------------------------------------
class UdpServer:
    """Listens on a UDP port in a thread and hands packets to `on_packet`."""

    def __init__(self, port, on_packet, host="0.0.0.0"):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.settimeout(0.2)
        self.on_packet = on_packet
        self.alive = True
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"LiveNodes-UDP-{port}")
        self.thread.start()

    def _run(self):
        while self.alive:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self.on_packet(data, addr)
            except Exception as exc:
                print(f"[LiveNodes] UDP handler error: {exc}")

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass
        self.thread.join(timeout=1.0)


class OscServer:
    """Keeps the latest arguments per OSC address plus a short message log."""

    def __init__(self, port):
        self.lock = threading.Lock()
        self.values = {}
        self.log = collections.deque(maxlen=64)
        self.count = 0
        self.udp = UdpServer(port, self._packet)

    def _packet(self, data, addr):
        msgs = osc_parse(data)
        with self.lock:
            for address, args in msgs:
                self.values[address] = args
                self.log.append((time.time(), address, args))
                self.count += 1

    def snapshot(self):
        with self.lock:
            return dict(self.values), list(self.log), self.count

    def close(self):
        self.udp.close()


class UdpSender:
    def __init__(self, broadcast=False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send(self, data, host, port):
        self.sock.sendto(data, (host, port))

    def close(self):
        self.sock.close()


class LineServer:
    """UDP text receiver: keeps the most recent lines."""

    def __init__(self, port):
        self.lines = collections.deque(maxlen=256)
        self.count = 0
        self.udp = UdpServer(port, self._packet)

    def _packet(self, data, addr):
        for line in data.decode("utf-8", "replace").splitlines():
            self.lines.append(line)
            self.count += 1

    def close(self):
        self.udp.close()


# -- Art-Net --------------------------------------------------------------
def artnet_dmx(universe, values, sequence=0):
    """ArtDmx packet for up to 512 byte values."""
    data = bytes(values[:512])
    if len(data) % 2:
        data += b"\x00"
    return (b"Art-Net\x00" + struct.pack("<H", 0x5000) + struct.pack(">H", 14)
            + bytes((sequence & 0xFF, 0)) + struct.pack("<H", universe & 0x7FFF)
            + struct.pack(">H", len(data)) + data)


def artnet_parse(packet):
    """Returns (universe, bytes) for an ArtDmx packet, else None."""
    if len(packet) < 18 or not packet.startswith(b"Art-Net\x00"):
        return None
    if struct.unpack_from("<H", packet, 8)[0] != 0x5000:
        return None
    universe = struct.unpack_from("<H", packet, 14)[0]
    length = struct.unpack_from(">H", packet, 16)[0]
    return universe, packet[18:18 + length]
