"""Handles all API calls for posting, putting, and getting instruments (all types)"""
from ..models import *
from flask  import request, abort, url_for, current_app
from .. import db
from . import api_1_0
from .authentication import requires_credentials, requires_write_access
from .decorators import json, collection, cache_control
import datetime

@api_1_0.route('/log/', methods=['POST'])
@requires_write_access
@json
def post_log():
    """POST a new log for Device SN
    """
    event = Log.create(request.json)

    db.session.add(event)
    db.session.commit()

    return event, 201

@api_1_0.route('/log/<int:id>', methods=['GET'])
@requires_credentials
@json
def get_log(id):
    log = Log.query.get_or_404(id)

    return log, 200

@api_1_0.route('/log/<int:id>', methods=['PUT'])
@requires_write_access
@json
def update_log(id):
    log = Log.query.get_or_404(id)

    log.from_dict(request.json, partial_update=True)

    db.session.add(log)
    db.session.commit()

    return log, 204

@api_1_0.route('/log/', methods=['GET'])
@requires_credentials
@json
@collection(Log, 'data')
def get_all_logs():
    """Return a paginated list of all logs
    """
    return Log.query

@api_1_0.route('/log/<string:sn>/', methods=['GET'])
@requires_credentials
@json
@collection(Log, 'data')
def get_logs_by_device(sn):
    """"""
    return Log.query.filter_by(instr_sn=sn)
