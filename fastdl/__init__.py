from importlib import import_module
from os import path, listdir
from steam.webapi import WebAPI
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_openid import OpenID


app = Flask('fastdl', instance_relative_config=True)
app.config.from_object('fastdl.config')
app.config['UPLOAD_DIR'] = path.join(app.instance_path, 'uploads')
app.config.from_pyfile('fastdl.cfg')
app.config['UPLOAD_DIR'] = path.abspath(app.config['UPLOAD_DIR'])

for key in ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI', 'STEAM_API_KEY']:
    if key not in app.config:
        raise ValueError('Missing configuration key: ' + key)

login_manager = LoginManager(app)
db = SQLAlchemy(app)
openid = OpenID(app, store_factory=lambda: None)
steam_api = WebAPI(app.config['STEAM_API_KEY'])


models = import_module('fastdl.models')
views = import_module('fastdl.views')
cli = import_module('fastdl.cli')
