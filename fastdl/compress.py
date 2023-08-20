from bz2 import BZ2Compressor
from os import link
from tempfile import NamedTemporaryFile

from . import app, db
from .models import Map


BLOCK_SIZE = 16 * 1024


def compress_file(map: Map):
    with NamedTemporaryFile() as tempfile:
        compressor = BZ2Compressor()
        with open(map.filename, 'rb') as mapfile:
            while True:
                data = mapfile.read(BLOCK_SIZE)
                if not data:
                    break
                tempfile.write(compressor.compress(data))
        compressor.flush()
        link(tempfile.name, map.filename_compressed)


def thread_entry(map_id: int):
    with app.app_context():
        map = db.session.get(Map, map_id)
        if map is not None:
            compress_file(map)
            map.compressed = True
            db.session.add(map)
            db.session.commit()
