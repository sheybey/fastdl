from json import JSONDecodeError, dumps, loads
from typing import Callable
from weakref import ref, WeakSet

from flask_login import login_required
from flask_sock import Server
from simple_websocket import ConnectionClosed

from . import sock


subscribers: dict[int, WeakSet[Callable[[int, str, float], None]]] = {}


@login_required
@sock.route('/progress')
def progress(sock: Server):
    subscribed = set()
    weak_sock = ref(sock)

    def send_progress(map_id: int, type: str, progress: float):
        sock = weak_sock()
        if sock is not None:
            try:
                sock.send(dumps({'m': map_id, 't': type, 'p': progress}))
            except ConnectionClosed:
                pass

    try:
        while True:
            message = sock.receive()
            if message is not None:
                try:
                    id = loads(message)['m']
                    if id not in subscribed:
                        subscribed.add(id)
                        weak_set = subscribers.setdefault(id, WeakSet())
                        weak_set.add(send_progress)
                except (KeyError, JSONDecodeError):
                    pass

    except ConnectionClosed:
        sock.close()
