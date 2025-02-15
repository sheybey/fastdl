from functools import wraps
from ipaddress import IPv4Address
import re

from flask import (
    render_template, redirect, url_for, flash, request, abort, send_file,
    jsonify
)
from flask_login import current_user  # type: ignore
from flask_login import login_required, login_user, logout_user
from steam_openid import SteamOpenID


from . import app, db
from .compress import schedule_compress
from .forms import (
    EditServerForm, IDForm, NewServerForm, NewUserForm, UploadForm
)
from .models import AnonymousUser, User, Server, Map, Access
from .upload_ftp import FTPAction, schedule_ftp_action


current_user: User | AnonymousUser


def create_openid():
    return SteamOpenID(
        realm=url_for('login', _external=True),
        return_to=url_for('login_callback', _external=True)
    )


def admin_required(view):
    @wraps(view)
    @login_required
    def check_admin(*args, **kwargs):
        if not current_user.admin:
            flash('You are not authorized to view this page.', 'danger')
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return check_admin


@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template(
            'index.html',
            accesses=db.session.scalars(
                db.select(Access).order_by(Access.access_time.desc()).limit(10)
            )
        )
    else:
        return redirect(url_for('login'))


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    return redirect(create_openid().get_redirect_url())


@app.route('/login/callback')
def login_callback():
    openid = create_openid()

    steam_id = None
    errors: list[str] = []
    try:
        steam_id = openid.validate_results(request.args)
    except openid.SteamIDExtractionError:
        errors.append('No user ID returned from Steam')

    if steam_id is None:
        if request.args.get('openid.mode') == 'error':
            errors.extend(request.args.getlist('openid.error'))
        if len(errors) == 0:
            errors.append('Unknown error')

        return render_template('login_failed.html', errors=errors)

    user = db.session.get(User, steam_id)
    if user:
        login_user(user)
        return redirect(url_for('index'))

    return render_template('unauthorized.html')


@app.route('/logout')
def logout():
    logout_user()
    return render_template('logged_out.html')


@login_required
@app.route('/servers')
def servers():
    return render_template(
        'servers.html',
        servers=db.session.scalars(db.select(Server)),
        form=NewServerForm(),
        delete_form=IDForm(model=Server)
    )


@login_required
@app.route('/server/create', methods=['POST'])
def create_server():
    form = NewServerForm()
    if form.validate():
        server = Server.get_by_address(form.ip.data, form.port.data)
        if server:
            flash(server.display + ' already added.', 'danger')
        else:
            server = Server(  # type: ignore
                ip=form.ip.data,
                port=form.port.data,
                description=form.description.data
            )
            db.session.add(server)
            db.session.commit()
            flash(server.display + ' added.', 'success')

    else:
        flash(next(iter(next(iter(form.errors.values())))), 'danger')

    return redirect(url_for('servers'))


def update_server(server: Server, form: EditServerForm):
    if form.validate():
        server.ip = form.ip.data
        server.description = form.description.data

        server.ftp_enabled = form.ftp_enabled.data
        if form.ftp_enabled.data:
            server.ftp_host = form.ftp_host.data
            server.ftp_port = form.ftp_port.data or 21
            server.ftp_tls = form.ftp_tls.data
            server.ftp_tls_verify = form.ftp_tls_verify.data
            server.ftp_dir = form.ftp_dir.data
            server.ftp_user = form.ftp_user.data
            if form.ftp_pass.data:
                server.ftp_pass = form.ftp_pass.data
            elif not server.ftp_pass:
                flash('Missing FTP password', 'danger')
                return False
        else:
            server.ftp_host = ''
            server.ftp_port = 0
            server.ftp_tls = True
            server.ftp_tls_verify = True
            server.ftp_dir = '/'
            server.ftp_user = ''
            server.ftp_pass = ''

        return True

    else:
        for error_list in form.errors.values():
            for error in error_list:
                flash(error, 'danger')
        return False


@login_required
@app.route('/server/edit/<int:id>', methods=['GET', 'POST'])
def edit_server(id):
    server = db.get_or_404(Server, id)
    form = EditServerForm(obj=server)
    if request.method == 'POST':
        if update_server(server, form):
            db.session.add(server)
            db.session.commit()
            flash('Server details updated.', 'success')
            return redirect(url_for('servers'))
    return render_template('edit_server.html', form=form, server=server)


@login_required
@app.route('/server/delete', methods=['POST'])
def delete_server():
    form = IDForm(model=Server)
    if form.validate():
        display = form.instance.display
        db.session.delete(form.instance)
        db.session.commit()
        flash(display + ' deleted.', 'success')
    else:
        flash('Invalid server.', 'danger')

    return redirect(url_for('servers'))


@login_required
@app.route('/maps')
def maps():
    return render_template(
        'maps.html',
        maps=db.session.scalars(db.select(Map)),
        form=IDForm(model=Map)
    )


@app.route('/maps/<name>')
def download_map(name):
    map: Map = db.first_or_404(db.select(Map).where(Map.name == name))
    if not map.uploaded:
        abort(404)

    if not current_user.is_authenticated:
        try:
            if request.headers['User-Agent'] != 'Half-Life 2':
                abort(404)

            match = re.match(
                r'hl2://([0-9.]+):([0-9]+)',
                request.headers['Referer']
            )
            if not match:
                abort(404)

            addr = IPv4Address(match.group(1))
            port = int(match.group(2))
            server = Server.get_by_address(addr, port)
            if server is None:
                abort(404)

            access = Access(  # type: ignore
                ip=request.remote_addr,
                map=map,
                server=server
            )
            db.session.add(access)
            db.session.commit()

        except (KeyError, ValueError):
            abort(404)

    if map.compressed:
        filename = map.filename_compressed
        mimetype = 'application/x-bzip2'
    else:
        filename = map.filename
        mimetype = 'application/octet-stream'
    return send_file(
        filename,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
        conditional=True
    )


@login_required
@app.route('/map/delete', methods=['POST'])
def delete_map():
    form = IDForm(model=Map)
    if form.validate():
        map = form.instance
        if not map.uploaded:
            flash(
                'Wait for the map to finish uploading before deleting it.',
                'danger'
            )
        else:
            try:
                schedule_ftp_action(FTPAction.Delete, map)
                map.delete()
                flash('Deleted ' + map.name, 'success')
                db.session.delete(map)
                db.session.commit()
            except FileNotFoundError:
                flash(map.name + ' did not exist on filesystem.', 'warning')
                db.session.delete(map)
                db.session.commit()
            except IOError as err:
                flash(str(err), 'danger')
    else:
        flash('Invalid map.', 'danger')

    return redirect(url_for('maps'))


@login_required
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    is_post = request.method == 'POST'
    should_return_json = (
        is_post and
        request.headers.get('Accept') == 'application/json'
    )
    form = UploadForm()
    if is_post:
        if form.validate():
            map = Map(name=form.map.data.filename, uploaded=False)
            db.session.add(map)
            db.session.commit()

            form.map.data.save(map.filename)
            map.uploaded = True
            db.session.add(map)
            db.session.commit()

            schedule_compress(map)
            schedule_ftp_action(FTPAction.Upload, map)

            if should_return_json:
                return jsonify({
                    'success': True,
                    'name': map.name,
                    'id': map.id
                })
            else:
                flash('Uploaded ' + map.name, 'success')

        else:
            error = form.errors[next(iter(form.errors.keys()))][0]
            if should_return_json:
                return jsonify({'success': False, 'error': error})
            else:
                flash(error, 'danger')

    return render_template('upload.html', form=form)


@admin_required
@app.route('/users')
def users():
    return render_template(
        'users.html',
        users=db.session.scalars(db.select(User)),
        form=NewUserForm(),
        admin_form=IDForm(model=User, pk='steamid64')
    )


@admin_required
@app.route('/user/promote', methods=['POST'])
def promote_user():
    form = IDForm(model=User, pk='steamid64')
    if form.validate():
        if form.instance == current_user:
            flash('You cannot promote yourself.', 'danger')
        else:
            form.instance.admin = True
            db.session.add(form.instance)
            db.session.commit()
            flash(form.instance.name + ' promoted.', 'success')
    else:
        flash('No such user.', 'danger')

    return redirect(url_for('users'))


@admin_required
@app.route('/user/demote', methods=['POST'])
def demote_user():
    form = IDForm(model=User, pk='steamid64')
    if form.validate():
        if form.instance == current_user:
            flash('You cannot demote yourself.', 'danger')
        else:
            form.instance.admin = False
            db.session.add(form.instance)
            db.session.commit()
            flash(form.instance.name + ' demoted.', 'success')
    else:
        flash('No such user.', 'danger')

    return redirect(url_for('users'))


@admin_required
@app.route('/user/delete', methods=['POST'])
def delete_user():
    form = IDForm(model=User, pk='steamid64')
    if form.validate():
        if form.instance == current_user:
            flash('You cannot delete yourself.', 'danger')
        else:
            name = form.instance.name
            db.session.delete(form.instance)
            db.session.commit()
            flash(name + ' deleted.', 'success')
    else:
        flash('No such user.', 'danger')

    return redirect(url_for('users'))


@admin_required
@app.route('/user/create', methods=['POST'])
def create_user():
    form = NewUserForm()
    if form.validate():
        id64 = form.steamid.data.as_64
        user = db.session.scalar(db.select(User).where(User.steamid64 == id64))
        if user:
            flash(user.name + ' already added.', 'danger')
        else:
            user = User(
                steamid64=id64,
                admin=form.admin.data
            )
            user.refresh_name()
            if user.name is not None:
                db.session.add(user)
                db.session.commit()
                flash(user.name + ' added.', 'success')
            else:
                flash('No such steam user.', 'danger')

    else:
        flash(next(iter(form.errors['steamid64'])), 'danger')

    return redirect(url_for('users'))
