import re
from functools import wraps
from ipaddress import IPv4Address
from steam.steamid import SteamID
from flask import (
    render_template, redirect, url_for, flash, request, abort, send_file,
    jsonify
)
from flask_login import current_user, login_user, logout_user, login_required
from jinja2 import Markup
from . import app, openid, db, steam_api
from .models import User, Server, Map, Access
from .forms import UploadForm, NewUserForm, NewServerForm, IDForm


def admin_required(view):
    @wraps(view)
    @login_required
    def check_admin(*args, **kwargs):
        if not current_user.admin:
            flash('You are not authorized to view this page.', 'danger')
            return redirect(url_for('index'))
        return view(*args, **kwargs)


@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template(
            'index.html',
            accesses=Access.query.order_by(
                db.desc(Access.access_time)).limit(10).all()
        )
    else:
        return redirect(url_for('login'))


@app.route('/login')
@openid.loginhandler
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    error = openid.fetch_error()
    if error:
        flash(error, 'danger')

    return openid.try_login('https://steamcommunity.com/openid')


@openid.after_login
def after_login(response):
    id = response.identity_url.split('/')[-1]
    user = User.query.get(id)
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
        servers=Server.query.all(),
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
            server = Server(
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
        maps=Map.query.all(),
        form=IDForm(model=Map)
    )


@app.route('/maps/<name>')
def download_map(name):
    map = Map.query.filter_by(name=name).first_or_404()
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

            access = Access(ip=request.remote_addr, map=map, server=server)
            db.session.add(access)
            db.session.commit()

        except (KeyError, ValueError):
            abort(404)

    return send_file(
        map.filename,
        mimetype='application/octet-stream',
        as_attachment=True,
        attachment_filename=map.name,
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
        request.headers.get('Accept', '') == 'application/json'
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

            if should_return_json:
                return jsonify({
                    'success': True,
                    'map_name': map.name
                })

        elif should_return_json:
            return jsonify({
                'success': False,
                'error': form.errors[next(iter(form.errors.keys()))][0]
            })

    return render_template('upload.html', form=form)


@admin_required
@app.route('/users')
def users():
    return render_template(
        'users.html',
        users=User.query.all(),
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
        user = User.query.filter_by(steamid64=id64).first()
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
