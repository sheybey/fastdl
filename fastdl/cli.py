from os import path, mkdir, listdir
from click import echo
from . import app, db
from .models import Map, Server, Access, User


@app.cli.group('db')
def database():
    """Database-related commands"""
    pass


@database.command()
def drop():
    """Drop database tables"""
    db.drop_all()


@database.command('create')
def create_database():
    """Create database tables"""
    db.create_all()


@database.command()
def seed():
    """Insert initial data into the database"""
    db.session.add(User(
        steamid64=76561198013023668,
        admin=True,
        name="sheybey | TF2.GG"
    ))
    db.session.commit()


@app.cli.group()
def uploads():
    """Configure the upload directory"""
    pass


@uploads.command('path')
def get_upload_path():
    """Get the effective configured upload path"""
    echo(app.config['UPLOAD_DIR'])


@uploads.command('create')
def create_uploads():
    """Create the upload directory"""
    try:
        if not path.isdir(app.config['UPLOAD_DIR']):
            mkdir(app.config['UPLOAD_DIR'])
    except IOError as e:
        echo('Could not create directory: ' + str(e))


@uploads.command()
def discover():
    """Add pre-existing maps to the database"""
    existing = list(map(lambda m: m.name, Map.query.all()))

    for name in listdir(app.config['UPLOAD_DIR']):
        if (
            name in existing or
            not path.isfile(name) or
            not name.endswith('.bsp')
        ):
            continue

        if name in app.config['BUILTIN']:
            echo('warning: ignoring builtin map ' + name)
            continue

        with open(name, 'rb') as file:
            magic_number = file.read(4)
        if magic_number == b'VBSP':
            db.session.add(Map(name=name, uploaded=True))
            echo('added ' + name)
        else:
            echo('warning: ignoring invalid BSP ' + name)
        
    db.session.commit()


@uploads.command()
def prune():
    """Remove maps that do not exist on the filesystem"""
    for map in Map.query.all():
        if not path.isfile(map.filename):
            db.session.delete(map)
            echo('pruned ' + map.name)

    db.session.commit()
