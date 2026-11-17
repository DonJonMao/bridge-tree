import ipaddress
import json
import os
import socket
import sys
from datetime import datetime, timezone

def _audit(event, args):
    if event != 'socket.connect':
        return
    sock, address = args
    if sock.family == socket.AF_UNIX:
        return
    host = address[0] if isinstance(address, tuple) and address else None
    try:
        allowed = host == 'localhost' or ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        allowed = False
    if allowed:
        return
    path = os.environ.get('WEBWALKER_VALIDATION_NETWORK_LOG')
    if path:
        with open(path, 'a') as handle:
            handle.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                'event': event, 'host': host, 'port': address[1] if isinstance(address, tuple) and len(address) > 1 else None}) + '\n')
    raise RuntimeError('Offline validation blocks non-loopback socket connection')

sys.addaudithook(_audit)
