from datetime import datetime, timezone
from ipaddress import IPv4Address
from os import path, stat, unlink
from flask_login import AnonymousUserMixin
from sqlalchemy import types
from steam.steamid import SteamID
from . import app, db, login_manager


class UTCDateTime(types.TypeDecorator):
    impl = types.DateTime

    def process_bind_param(self, value, engine):
        if value is not None:
            return value.astimezone(timezone.utc)

    def process_result_value(self, value, engine):
        if value is not None:
            return self.to_utc(value)

    @staticmethod
    def to_utc(value):
        return datetime(
            value.year, value.month, value.day,
            value.hour, value.minute, value.second, value.microsecond,
            tzinfo=timezone.utc
        )

    @classmethod
    def utcnow(cls):
        return cls.to_utc(datetime.utcnow())


class AnonymousUser(AnonymousUserMixin):
    steamid64 = None
    name = 'Anonymous'
    admin = False


login_manager.anonymous_user = AnonymousUser


class User(db.Model):
    steamid64 = db.Column(db.BigInteger, primary_key=True)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    name = db.Column(db.String(128), nullable=False)

    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return str(self.steamid64)

    @property
    def steamid(self):
        return SteamID(self.steamid64)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class IPMixin:
    @property
    def ip(self):
        return IPv4Address(self._ip)

    @ip.setter
    def ip(self, address):
        if not isinstance(address, IPv4Address):
            address = IPv4Address(address)
        self._ip = address.packed


class Server(IPMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    _ip = db.Column('ip', db.BINARY(4), nullable=False)
    port = db.Column(db.Integer)

    description = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return '<{} {}:{}>'.format(
            self.__class__.__name__,
            self.ip.exploded,
            self.port
        )

    @property
    def maps_served(self):
        return Access.query.filter_by(server=self).count()

    @classmethod
    def get_by_address(cls, address, port):
        if not isinstance(address, IPv4Address, port):
            address = IPv4Address(address)
        return cls.query.filter_by(_ip=address.packed, port=port).first()

    @property
    def bandwidth(self):
        sizes = {}
        total = 0
        for access in self.accesses:
            if access.map.id not in sizes:
                sizes[access.map.id] = access.map.size
            total += sizes[access.map.id]

        return total

    @property
    def display(self):
        return self.ip.exploded + ':' + str(self.port)

    __table_args__ = (
        db.UniqueConstraint(_ip, port),
        {}
    )


class Map(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    uploaded = db.Column(db.Boolean, nullable=False)

    @property
    def filename(self):
        return path.join(app.config['UPLOAD_DIR'], self.name)

    @property    
    def url(self):
        return url_for('download_map', name=self.name)

    @property
    def size(self):
        try:
            return stat(self.filename).st_size
        except IOError:
            return 0

    @property
    def bandwidth(self):
        return self.size * self.times_served

    @property
    def times_served(self):
        return Access.query.filter_by(map=self).count()

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)

    def delete(self):
        unlink(self.filename)


class Access(IPMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    _ip = db.Column(db.BINARY(4), nullable=False)

    server_id = db.Column(
        db.Integer,
        db.ForeignKey(Server.id),
        nullable=False
    )
    server = db.relationship(
        Server,
        backref=db.backref('accesses', lazy=True, cascade="all,delete")
    )

    map_id = db.Column(
        db.Integer,
        db.ForeignKey(Map.id),
        nullable=False
    )
    map = db.relationship(
        Map,
        backref=db.backref('accesses', lazy=True, cascade='all,delete')
    )

    access_time = db.Column(
        UTCDateTime,
        nullable=False,
        default=UTCDateTime.utcnow
    )
