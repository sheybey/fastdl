from os import path, mkdir, listdir
from click import echo, argument, option
from steam.enums.common import EType
from . import app, db
from .models import Map, Server, Access, User
from .util import string_to_steamid


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


@app.cli.group()
def maps():
    """Map-related utilites"""
    pass


@maps.command('path')
def get_upload_path():
    """Get the effective configured upload path"""
    echo(app.config['UPLOAD_DIR'])


@maps.command('create')
def create_uploads():
    """Create the upload directory"""
    try:
        if not path.isdir(app.config['UPLOAD_DIR']):
            mkdir(app.config['UPLOAD_DIR'])
    except IOError as e:
        echo('Could not create directory: ' + str(e))


@maps.command()
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


@maps.command()
def prune():
    """Remove maps that do not exist on the filesystem"""
    for map in Map.query.all():
        if not path.isfile(map.filename):
            db.session.delete(map)
            echo('pruned ' + map.name)

    db.session.commit()


@app.cli.group()
def user():
    """Manage users"""
    pass


@user.command('create')
@argument('steamid')
@option('--admin/--not-admin', default=False)
def create_user(steamid, admin):
    """Create a user"""
    steamid = string_to_steamid(steamid)
    if not steamid.is_valid() or not steamid.type == EType.Individual:
        echo('Invalid steam ID')
        return 1

    user = User(steamid64=steamid.as_64, admin=admin)
    user.refresh_name()
    if user.name is not None:
        db.session.add(user)
        db.session.commit()
        echo('added ' + user.name)
    else:
        echo('No such steam user')
        return 1


@user.command('delete')
@argument('steamid64', type=int)
def delete_user(steamid64):
    """Delete a user"""
    user = User.query.get(steamid64)
    if user is None:
        echo('No such user')
        return 1
    db.session.delete(user)
    db.session.commit()
    echo('deleted ' + user.name)


@user.command('list')
def list_users():
    """List all users"""
    echo('Steam ID'.ljust(17, ' ') + '  Name')
    echo('-' * 79)
    for user in User.query.all():
        echo(str(user.steamid64) + '  ' + user.name)
