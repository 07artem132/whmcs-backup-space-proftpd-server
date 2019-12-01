#!/usr/bin/env python
from enum import Enum
import peewee
from flask import Flask, jsonify, abort, request, make_response, url_for
from flask_httpauth import HTTPBasicAuth
import json
import socket
from peewee import *
import shutil

config_file_name = "config.json"

app = Flask(__name__, static_url_path="")
auth = HTTPBasicAuth()
with open(config_file_name) as config_file:
    config = json.loads(config_file.read())
    mysql_db = MySQLDatabase(config.get('mysql_database'),
                             user=config.get('mysql_login'),
                             password=config.get('mysql_password'),
                             host=config.get('mysql_ip'),
                             port=config.get('mysql_port'),
                             )


@auth.get_password
def get_password(username):
    if username == 'token':
        return config.get('api_token')
    return None


@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 403)
    # return 403 instead of 401 to prevent browsers from displaying the default auth dialog


@app.errorhandler(400)
def not_found(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.errorhandler(405)
def method_not_allowed(error):
    return make_response(jsonify({'error': 'Method is not allowed'}), 405)


@app.errorhandler(500)
def method_not_allowed(error):
    return make_response(jsonify({'error': 'internal server error'}), 500)


class BaseModel(Model):
    class Meta:
        database = mysql_db


class Users(BaseModel):
    username = CharField()
    password = CharField()
    uid = IntegerField()
    gid = IntegerField()
    homedir = CharField()
    shell = CharField()


class QuotaTallies(BaseModel):
    name = CharField()
    quota_type = CharField()

    class QuotaType(Enum):
        USER = "user"
        GROUP = "group"
        CLASS = "class"
        ALL = "all"

    bytes_in_used = FloatField()
    bytes_out_used = FloatField()
    bytes_xfer_used = FloatField()
    files_in_used = IntegerField()
    files_out_used = IntegerField()
    files_xfer_used = IntegerField()


class QuotaLimits(BaseModel):
    name = CharField()
    quota_type = CharField()
    per_session = CharField()
    limit_type = CharField()

    class QuotaType(Enum):
        USER = "user"
        GROUP = "group"
        CLASS = "class"
        ALL = "all"

    class PerSession(Enum):
        FALSE = "false"
        TRUE = "true"

    class LimitType(Enum):
        SOFT = "soft"
        HARD = "hard"

    bytes_in_avail = FloatField()
    bytes_out_avail = FloatField()
    bytes_xfer_avail = FloatField()
    files_in_avail = IntegerField()
    files_out_avail = IntegerField()
    files_xfer_avail = IntegerField()


def db_hashed_password(password):
    cursor = mysql_db.execute_sql('select ENCRYPT("' + password + '");')
    return cursor.fetchone()[0].decode("utf-8")


def generate_user_path(login):
    if config.get('user_path')[:1] != '/':
        return config.get('user_path') + "/" + login
    else:
        return config.get('user_path') + login


@app.route('/api/node/oversell', methods=['PUT'])
@auth.login_required
def set_oversell():
    if not request.form:
        abort(400)
    if 'oversell' not in request.form:
        abort(400)

    config['oversell'] = request.form.get('oversell')

    with open(config_file_name, 'w') as f:
        json.dump(config, f, indent=4)

    return jsonify({'status': 'success'})


@app.route('/api/node/status', methods=['GET'])
@auth.login_required
def get_status():
    use_without_quota = QuotaTallies.select(fn.SUM(QuotaTallies.bytes_in_used)).scalar()
    use_quota = QuotaLimits.select(fn.SUM(QuotaLimits.bytes_in_avail)).scalar()
    if use_quota is None:
        use_quota = 0
    if use_without_quota is None:
        use_without_quota = 0

    return jsonify({
        'disk_space': config.get('disk_space'),
        'oversell': config.get('oversell'),
        'allow_protocol': config.get('allow_protocol'),
        'hostname': socket.getfqdn(),
        'disk_free': '%.2f' % (config.get('disk_space') - use_quota),  # свободно c учетом квоты
        'disk_free_without_quota': '%.2f' % (config.get('disk_space') - use_without_quota),  # свободно без учета квот
        'disk_use': '%.2f' % use_quota,  # занято c учетом квоты
        'disk_use_without_quota': '%.2f' % use_without_quota,  # занято без учета квот
    })


@app.route('/api/<string:login>', methods=['DELETE'])
@auth.login_required
def user_delete(login):
    try:
        with mysql_db.atomic() as transaction:
            QuotaTallies.delete().where(QuotaTallies.name == login).execute()
            QuotaLimits.delete().where(QuotaLimits.name == login).execute()
            Users.delete().where(Users.username == login).execute()
    except peewee.PeeweeException:
        transaction.rollback()
        abort(500)
    try:
        shutil.rmtree(generate_user_path(login))
    except BaseException as e:
        print(e)
    return jsonify({'status': 'success'})


@app.route('/api/<string:login>/password', methods=['PUT'])
@auth.login_required
def user_edit_password(login):
    if not request.form:
        abort(400)
    if 'password' not in request.form:
        abort(400)

    try:
        Users.update({Users.password: db_hashed_password(request.form.get('password'))}) \
            .where(Users.username == login).execute()
    except peewee.PeeweeException:
        abort(500)

    return jsonify({'status': 'success'})


@app.route('/api/<string:login>/quota', methods=['PUT'])
@auth.login_required
def user_edit_quota(login):
    if not request.form:
        abort(400)
    if 'quota' not in request.form:
        abort(400)

    try:
        QuotaLimits.update({QuotaLimits.bytes_in_avail: float(request.form.get('quota'))}) \
            .where(QuotaLimits.name == login).execute()
    except peewee.PeeweeException:
        abort(500)

    return jsonify({'status': 'success'})


@app.route('/api/<string:login>', methods=['GET'])
@auth.login_required
def user_get(login):
    try:
        result_query = QuotaLimits.select(QuotaLimits.name, QuotaLimits.bytes_in_avail, QuotaTallies.bytes_in_used) \
            .where(QuotaLimits.name == login) \
            .join(QuotaTallies, on=(QuotaLimits.name == QuotaTallies.name)).first()

        if result_query is None:
            abort(400)

        return jsonify({
            'status': 'success',
            'disk_space': '%.2f' % result_query.bytes_in_avail,
            'disk_use': '%.2f' % result_query.quotatallies.bytes_in_used
        })
    except peewee.PeeweeException:
        abort(500)


@app.route('/api/user/all', methods=['GET'])
@auth.login_required
def user_list():
    try:
        result_query = QuotaLimits.select(QuotaLimits.name, QuotaLimits.bytes_in_avail, QuotaTallies.bytes_in_used) \
            .join(QuotaTallies, on=(QuotaLimits.name == QuotaTallies.name)).execute()

        if result_query is None or result_query is None:
            abort(400)

        result = {}
        for item in result_query:
            result[item.name] = {
                'disk_space': '%.2f' % item.bytes_in_avail,
                'disk_use': '%.2f' % item.quotatallies.bytes_in_used
            }

        return jsonify({
            'status': 'success',
            'users': result,
        })
    except peewee.PeeweeException:
        abort(500)


@app.route('/api/user', methods=['POST'])
@auth.login_required
def user_add():
    if not request.form:
        abort(400)
    if 'login' not in request.form or 'password' not in request.form or 'quota' not in request.form:
        abort(400)

    login = request.form.get('login')
    password = request.form.get('password')

    try:
        with mysql_db.atomic() as transaction:
            insert_user(login, password)
            insert_quota_limits(login, float(request.form.get('quota')))
            insert_quota_stats(login)
    except peewee.PeeweeException:
        transaction.rollback()
        abort(500)

    return jsonify({'status': 'success'})


def insert_quota_stats(login):
    QuotaTallies.create(
        name=login,
        quota_type=QuotaTallies.QuotaType.USER.value,
        bytes_in_used=0,
        bytes_out_used=0,
        bytes_xfer_used=0,
        files_in_used=0,
        files_out_used=0,
        files_xfer_used=0,
    )


def insert_quota_limits(login, limit):
    QuotaLimits.create(
        name=login,
        quota_type=QuotaLimits.QuotaType.USER.value,
        per_session=QuotaLimits.PerSession.FALSE.value,
        limit_type=QuotaLimits.LimitType.HARD.value,
        bytes_in_avail=limit,
        bytes_out_avail=0,
        bytes_xfer_avail=0,
        files_in_avail=0,
        files_out_avail=0,
        files_xfer_avail=0,
    )


def insert_user(login, password):
    Users.create(
        username=login,
        password=db_hashed_password(password),
        uid=config.get('user_uid'),
        gid=config.get('user_gid'),
        homedir=generate_user_path(login),
        shell=config.get('user_shell')
    )


if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=55000)
