from ipaddress import IPv4Address

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from steam.enums.common import EType
from steam.steamid import SteamID
from werkzeug.utils import secure_filename
from wtforms.validators import InputRequired, NumberRange, ValidationError
from wtforms.fields import (
    Field, BooleanField, HiddenField, IntegerField, PasswordField, StringField
)
from wtforms.widgets import TextInput, HiddenInput

from . import app, db
from .models import Map, User
from .util import string_to_steamid


class MagicNumber:
    def __init__(self, magic_numbers, message='Invalid file.'):
        self.magic_numbers = magic_numbers
        self.length = max(map(len, magic_numbers))
        self.message = message

    def __call__(self, form, field):
        number = field.data.read(self.length)
        field.data.seek(0)
        for expected in self.magic_numbers:
            if number.startswith(expected):
                return True
        raise ValidationError(self.message)


class FileExtension:
    def __init__(self, extensions, message='{} is not an allowed extension'):
        self.extensions = extensions
        self.message = message

    def __call__(self, form, field):
        extension = field.data.filename.split('.')[-1].lower()
        if extension not in self.extensions:
            raise ValidationError(self.message.format(extension))
        return True


class SteamIDField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data.as_steam3
        else:
            return ''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = string_to_steamid(valuelist[0])

        else:
            self.data = SteamID()


class UserIDField(Field):
    widget = HiddenInput()

    def _value(self):
        if self.data:
            if isinstance(self.data, User):
                return str(self.data.steamid64)
            else:
                return str(self.data)
        else:
            return ''

    def process_formdata(self, valuelist):
        if valuelist:
            obj = valuelist[0]
            if isinstance(obj, User):
                self.data = obj
            else:
                try:
                    self.data = db.session.get(User, int(valuelist[0]))
                except ValueError:
                    self.data = None
        else:
            self.data = None


def unique_map_name(form, field):
    name = secure_filename(field.data.filename or '')
    if not name:
        raise ValidationError('Invalid map name.')

    if (
        not app.config['OVERWRITE_BUILTIN'] and
        name in app.config['BUILTIN']
    ):
        raise ValidationError('This map is built-in to the game.')

    map = db.session.scalar(db.select(Map).where(Map.name == name))
    if map is not None:
        raise ValidationError(
            map.name + ' already exists. To replace it, delete it first.')

    field.data.filename = name
    return True


def valid_and_individual_id(form, field):
    if not field.data.is_valid():
        raise ValidationError('Invalid Steam ID')
    if field.data.type != EType.Individual:
        raise ValidationError('Non-individual Steam ID')
    return True


class UploadForm(FlaskForm):
    map = FileField('Map', validators=[
        FileRequired(),
        FileExtension(
            extensions=['bsp'],
            message='This does not look like a valid BSP file.'
        ),
        unique_map_name,
        MagicNumber(
            magic_numbers=[b'VBSP'],
            message='This does not look like a valid BSP file.'
        ),
    ])


class NewUserForm(FlaskForm):
    steamid = SteamIDField('Steam ID', validators=[
        InputRequired('Missing Steam ID'),
        valid_and_individual_id
    ])
    admin = BooleanField('Admin')


valid_port = NumberRange(min=1, max=65535, message='Invalid port')


class NewServerForm(FlaskForm):
    ip = StringField('IP Address')
    port = IntegerField('Port', validators=[valid_port], default=27015)
    description = StringField(
        'Description',
        validators=[InputRequired('Missing description')]
    )

    def validate_ip(self, field):
        try:
            field.data = IPv4Address(field.data)
        except ValueError:
            raise ValidationError('Invalid IP address')

        if not field.data.is_global:
            raise ValidationError('Non-global IP address')


class IDForm(FlaskForm):
    id = HiddenField()

    def __init__(self, *args, model, pk='id', **kwargs):
        self.model = model
        self.pk = pk
        if 'obj' in kwargs:
            attr = getattr(kwargs['obj'], pk)
            if attr is not None:
                kwargs['pk'] = attr
        super().__init__(*args, **kwargs)

    def validate_id(self, field):
        try:
            instance = db.session.get(self.model, int(field.data))
            if instance is None:
                raise ValueError
        except ValueError:
            raise ValidationError('No such object.')

        self.instance = instance


class RequiredIf:
    def __init__(self, field_name: str):
        self.field_name = field_name

    def __call__(self, form: FlaskForm, field: Field):
        prereq: Field = getattr(form, self.field_name)
        if prereq.data and not field.data:
            raise ValidationError('Missing ' + field.label.text)


required_if_enabled = RequiredIf('ftp_enabled')


class EditServerForm(NewServerForm):
    ftp_enabled = BooleanField('Enable upload via FTP')
    ftp_host = StringField('FTP Hostname', validators=[required_if_enabled])
    ftp_port = IntegerField(
        'FTP Port',
        validators=[required_if_enabled, valid_port],
        default=21
    )
    ftp_tls = BooleanField('Use TLS for FTP')
    ftp_tls_verify = BooleanField('Verify FTP server TLS certificate')
    ftp_user = StringField('FTP Username', validators=[required_if_enabled])
    ftp_pass = PasswordField('FTP Password')
    ftp_dir = StringField(
        'FTP Maps Directory',
        validators=[required_if_enabled],
        default='/maps'
    )
