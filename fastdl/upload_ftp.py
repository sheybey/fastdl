from enum import Enum
from ftplib import FTP, FTP_TLS
from io import BufferedReader
from os import fstat, path
from queue import Empty, Queue
from ssl import CERT_NONE, create_default_context
from threading import Thread
from weakref import WeakValueDictionary

from . import app, db
from .background import subscribers
from .models import Map, Server


BLOCK_SIZE = 16 * 1024
SESSION_TIMEOUT = 60
EMPTY_LIST = []


class FTPAction(Enum):
    Upload = 1
    Delete = 2


ActionQueue = Queue[tuple[FTPAction, str, int]]
ftp_sessions: WeakValueDictionary[int, ActionQueue] = WeakValueDictionary()


class ProgressCallback:
    def __init__(self, id: int, type: str, fp: BufferedReader):
        self.id = id
        self.type = type
        self.size = fstat(fp.fileno()).st_size
        self.consumed = 0

    def __call__(self, data: bytes):
        self.consumed += len(data)
        for subscriber in subscribers.get(self.id, EMPTY_LIST):
            subscriber(self.id, self.type, self.consumed / self.size)


def open_ftp_session(server: Server):
    if server.ftp_tls:
        ctx = None
        if not server.ftp_tls_verify:
            ctx = create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = CERT_NONE
        ftp = FTP_TLS(context=ctx)
    else:
        ftp = FTP()

    ftp.connect(
        host=server.ftp_host,
        port=server.ftp_port,
        timeout=SESSION_TIMEOUT
    )
    ftp.login(server.ftp_user, server.ftp_pass)
    ftp.cwd(server.ftp_dir)

    return ftp


def ftp_session_thread(server_id: int, queue: ActionQueue):
    ftp: FTP
    task_name: str
    map_dir: str
    with app.app_context():
        map_dir = app.config['UPLOAD_DIR']
        server = db.session.get(Server, server_id)
        if not server or not server.ftp_enabled:
            return
        task_name = 'Uploading to ' + server.description
        ftp = open_ftp_session(server)
        del server

    try:
        while True:
            [action, map_name, map_id] = queue.get(timeout=SESSION_TIMEOUT)
            if action == FTPAction.Upload:
                with open(path.join(map_dir, map_name), 'rb') as map_file:
                    progress = ProgressCallback(map_id, task_name, map_file)
                    ftp.storbinary(
                        'STOR ' + map_name,
                        map_file,
                        callback=progress
                    )
            elif action == FTPAction.Delete:
                ftp.delete(map_name)

    except Empty:
        ftp.close()


def get_or_create_ftp_queue(server_id: int) -> ActionQueue:
    queue = ftp_sessions.get(server_id)
    if queue is None:
        queue = Queue()
        ftp_sessions[server_id] = queue
        thread = Thread(
            target=ftp_session_thread,
            args=[server_id, queue]
        )
        thread.start()

    return queue


def schedule_ftp_action(action: FTPAction, map: Map):
    for server in db.session.scalars(
        db.select(Server).where(Server.ftp_enabled == True)  # noqa
    ):
        queue = get_or_create_ftp_queue(server.id)
        queue.put((action, map.name, map.id))
