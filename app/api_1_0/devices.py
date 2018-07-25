"""Handles all API calls for posting, putting, and getting instruments (all types)"""
from ..models import *
from flask  import request, abort, url_for, current_app
from .. import db
from . import api_1_0
from .authentication import requires_credentials, requires_write_access, requires_drop_access
from .authentication import filter_on_instrument_permissions, requires_viewing_privileges
from .decorators import json, collection, cache_control
from ..helpers import calculate_days, model_type
from .errors import bad_request
import datetime

@api_1_0.route('/device/', methods=['POST'])
@requires_write_access
@json
def post_device():
    """POST a new device (Requires discriminator and sn)"""
    data    = request.json
    model   = data.get('discriminator', None)

    if model is None or 'sn' not in data.keys():
        abort(400)

    if model == 'mit':
        new = MIT.create(data)
    elif model == 'ebam':
        new = EBAM.create(data)
    elif model == 'trex':
        new = TREX.create(data)
    else:
        new = Orphan.create(data)

    db.session.add(new)
    db.session.commit()

    # Set the credentials for the instrument
    new.set_credentials()

    return new, 201

@api_1_0.route('/device/<string:sn>', methods=['PUT'])
@requires_write_access
@requires_viewing_privileges
@json
def put_device(sn):
    """PUT a device"""
    data = request.json
    i = Instrument.query.filter_by(sn=sn).first()

    if i is None:
        abort(400)

    # Don't update the sn
    if 'sn' in data.keys():
        data.pop('sn')

    # Update the device
    i.from_dict(data, partial_update=True)

    db.session.add(i)
    db.session.commit()

    return {'Updated': 'all good'}, 204

@api_1_0.route('/device/<string:sn>', methods=['GET'])
@requires_credentials
@requires_viewing_privileges
@json
def get_device(sn):
    """Return a device by id"""
    dev = Instrument.query.filter_by(sn=sn).first_or_404()

    return dev, 200

@api_1_0.route('/device/', methods=['GET'])
@requires_credentials
@json
@collection(Instrument, 'data')
@filter_on_instrument_permissions(Instrument)
def get_devices():
    """Return a paginated list of all devices"""
    return Instrument.query

@api_1_0.route('/device/<string:sn>', methods=['DELETE'])
@requires_drop_access
@json
def delete_device(sn):
    """DELETE a device."""
    dev = Instrument.query.filter_by(sn=sn).first_or_404()

    # Drop from server
    dev.drop()

    return {'result': "deleted device '{}'".format(dev.sn)}, 202
