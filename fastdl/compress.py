from bz2 import BZ2Compressor
from errno import EXDEV
from os import fstat, link, unlink
from shutil import copyfile
from sys import stderr
from tempfile import NamedTemporaryFile
from threading import Thread
from traceback import print_exception

from . import app, db
from .background import subscribers
from .models import Map


BLOCK_SIZE = 16 * 1024


def send_progress(id: int, progress: float):
    for subscriber in subscribers.get(id, []):
        subscriber(id, 'Compressing to bz2', progress)


def compress_file(map: Map):
    with NamedTemporaryFile(delete_on_close=False) as tempfile:
        compressor = BZ2Compressor()
        with open(map.filename, 'rb') as mapfile:
            size = fstat(mapfile.fileno()).st_size
            compressed = 0
            while True:
                data = mapfile.read(BLOCK_SIZE)
                if not data:
                    break
                tempfile.write(compressor.compress(data))
                compressed += len(data)
                send_progress(map.id, compressed / size)
        tempfile.write(compressor.flush())
        tempfile.close()
        try:
            link(tempfile.name, map.filename_compressed)
        except OSError as err:
            if err.errno == EXDEV:
                copyfile(tempfile.name, map.filename_compressed)
            else:
                raise

    send_progress(map.id, 1.0)


def compression_thread(map_id: int):
    with app.app_context():
        map = db.session.get(Map, map_id)
        if map is not None:
            try:
                compress_file(map)
            except Exception as ex:
                print(f'failed to compress map {map.name}:', file=stderr)
                print_exception(ex, file=stderr)
                try:
                    unlink(map.filename_compressed)
                except FileNotFoundError:
                    pass
                return
            map.compressed = True
            db.session.add(map)
            db.session.commit()


def schedule_compress(map: Map):
    thread = Thread(
        target=compression_thread,
        args=[map.id],
        name=f'compress-{map.id}'
    )
    thread.start()
