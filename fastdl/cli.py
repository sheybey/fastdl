from os import path, mkdir
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
    sheybey = User(
        steamid64=76561198013023668,
        admin=True,
        name="sheybey | TF2.GG"
    )

    bball = Map(name='bball_tf_v2.bsp', uploaded=True)
    antiquity = Map(name='cp_antiquity_rc1.bsp', uploaded=True)
    glassworks = Map(name='cp_glassworks_rc6.bsp', uploaded=True)
    
    tf_heybey_org_1 = Server(
        ip='45.79.167.195', port=27015, description="tf.heybey.org server 1")
    tf_heybey_org_2 = Server(
        ip='45.79.167.195', port=27016, description="tf.heybey.org server 2")

    access_1 = Access(
        map=bball, server=tf_heybey_org_1, ip='127.0.0.1')
    access_2 = Access(
        map=antiquity, server=tf_heybey_org_1, ip='127.0.0.1')
    access_3 = Access(
        map=glassworks, server=tf_heybey_org_1, ip='127.0.0.1')
    access_4 = Access(
        map=bball, server=tf_heybey_org_2, ip='127.0.0.1')
    access_5 = Access(
        map=antiquity, server=tf_heybey_org_2, ip='127.0.0.1')
    access_6 = Access(
        map=glassworks, server=tf_heybey_org_2, ip='127.0.0.1')

    db.session.add_all(locals().values())
    db.session.commit()


@app.cli.group()
def uploads():
    """Configure the upload directory"""
    pass

@uploads.command('path')
def get_upload_path():
    """Get the configured upload path"""
    upload_path = path.abspath(app.config['UPLOAD_DIR'])
    echo(upload_path)
    echo('Exists' if path.isdir(upload_path) else 'Does not exist')


@uploads.command('create')
def create_uploads():
    """Create the upload directory"""
    try:
        mkdir(app.config['UPLOAD_DIR'])
    except IOError as e:
        echo('Could not create directory: ' + str(e))
