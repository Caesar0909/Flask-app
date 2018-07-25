"""
Holds all API methods for posting and getting data points

Endpoints to add:
  1) Latest
  2) csv download
"""
from ..models import *
from flask import request, abort, url_for, current_app, jsonify
from flask import app, make_response
from flask_login import login_required, current_user
from .. import db, sentry
from . import api_1_0
from .authentication import requires_credentials, requires_write_access
from .authentication import requires_viewing_privileges, requires_research_privileges
from .decorators import json, collection, _collection, _filter_query
from ..helpers import calculate_days
import datetime
import dateutil.parser

@api_1_0.route('/data/webhook/', methods=['POST'])
@requires_write_access
@json
def webhook_post():
    """POST a new datapoint from through a Particle webhook"""
    coreid = request.form['coreid']
    data = request.form['data']
    dev = Instrument.query.filter_by(particle_id=coreid).first_or_404()

    # In order to use this, I need to rewrite the from_json methods of MIT and EBAM
    model = dev._get_data_model()

    # If the device has a model attached, try to evaluate and add the so2 to the dictionary
    # So, evaluate() should return a new data object and should intake data in webhook format (or not)
    data = model.from_webhook(data, dev.sn)

    # Evaluate the model; returns new dict
    data = dev.evaluate(data=data)

    # old, working version
    new_pt = model.create(data)

    if new_pt.timestamp.year > datetime.datetime.utcnow().year:
        sentry.captureMessage("Invalid timestamp /data/webhook")
        abort(400)

    # Load in the ML model and set the
    dev.update()

    db.session.add(new_pt)
    db.session.commit()

    return {"Webhook Post": "All good!"}, 201

@api_1_0.route('/data/webhook/meta/', methods=['POST'])
@requires_write_access
@json
def webhook_post_meta():
    """POST meta information like restarts to the logs.
    """
    coreid  = request.form['coreid']

    # Return 200 for non actual coreid calls
    if coreid == 'api':
        return {'Webhook Post': 'NA'}, 200

    dev = Instrument.query.filter_by(particle_id=coreid).first_or_404()

    # data contains the message, name contains the webhook endpoint
    name = request.form['name']
    data = request.form['data']

    # use name to dictate the message
    if name == 'spark/device/last_reset':
        message = 'Device Reset: {}'.format(data)
    elif name == 'spark/flash/status':
        message = "Firmware Flash: {}".format(data)
    else:
        message = "Particle Event: {}".format(data)

    try:
        dev.log_event(message=message, level='INFO')
    except Exception:
        sentry.captureException()

    return {"Webhook Post": "All good!"}, 201

@api_1_0.route('/data/', methods=['POST'])
@requires_write_access
@json
def data_post():
    """POST a new datapoint"""
    data = request.json
    sn = data['instr_sn']

    i = Instrument.query.filter_by(sn=sn).first_or_404()

    # Fix datetime
    data['timestamp'] = dateutil.parser.parse(data['timestamp'])

    # Get the data model
    model = i._get_data_model()

    new = model.create(data)

    if new.timestamp.year > datetime.datetime.utcnow().year:
        abort(400)

    db.session.add(new)
    db.session.commit()

    new.update_parent()

    return new, 201

@api_1_0.route('/device/<string:sn>/data/', methods=['GET'])
@requires_viewing_privileges
@json
def get_data_by_dev(sn):
    """_filter and _sort first! Oh, and get the model name..."""
    dev = Instrument.query.filter_by(sn=sn).first_or_404()

    # Choose model
    model = dev._get_data_model()
    data = _collection(model, model.query.filter_by(instr_sn=dev.sn),
                    name='data', sn=dev.sn, researcher=False)

    return data, 200

@api_1_0.route('/researcher/device/<string:sn>/data/', methods=['GET'])
@requires_credentials
@requires_research_privileges
@json
def get_research_data_by_dev(sn):
    """Return the research data by device
    """
    dev = Instrument.query.filter_by(sn=sn).first_or_404()

    # Choose model
    model = dev._get_data_model()
    data = _collection(model, model.query.filter_by(instr_sn=dev.sn),
                    name='data', sn=dev.sn, researcher=True)

    return data, 200

@api_1_0.route('/device/<string:sn>/data/<int:id>', methods=['GET'])
@requires_credentials
@requires_viewing_privileges
@json
def get_datapoint_by_dev(sn, id):
    """GET individual data point by device SN."""
    dev = Instrument.query.filter_by(sn=sn).first_or_404()
    model = dev._get_data_model()

    # Query the individual data point
    data = model.query.get_or_404(id)

    return data, 200

@api_1_0.route('/device/<string:sn>/latest', methods=['GET'])
@requires_credentials
@requires_viewing_privileges
@json
def get_most_recent_datapoint(sn):
    """GET the most recent data point for instrument with sn=sn"""
    dev = Instrument.query.filter_by(sn=sn).first_or_404()

    m = dev._get_data_model()

    # query to get the most recent data point
    data = m.query.order_by(m.timestamp.desc()).first()

    if data is None:
        data = {}

    return data, 200

@api_1_0.route('/device/<string:sn>/data/<int:id>', methods=['PUT'])
@requires_credentials
@requires_viewing_privileges
@json
def put_datapoint(sn, id):
    """The only attribute we can change is the flag!
    """
    dev = Instrument.query.filter_by(sn=sn).first_or_404()
    mod = dev._get_data_model()

    pt = mod.query.get_or_404(id)

    # Update the model
    pt.from_dict(request.get_json(), partial_update=True)

    # Commit the changes
    db.session.add(pt)
    db.session.commit()

    return {"Update": "all good"}, 204

@api_1_0.route('/data/csv/<string:sn>/<string:start>/<string:end>/')
def download_csv(sn, start, end):
    """Download data and return as a csv
    If current_user has the permissions, give all the data!
    """
    dev = Instrument.query.filter_by(sn=sn).first_or_404()

    # Get the data model
    model = dev._get_data_model()

    # Get the data query
    dq = model.query.filter_by(instr_sn=dev.sn)

    # Filter on timestamp
    dq = dq.filter(model.timestamp >= start, model.timestamp <= end)

    # Get the columns to add to the file (based on the users permissions)
    cols_to_keep = dev.private_cols if current_user.can_view_research_data else dev.public_cols

    # Get the dataframe
    df = dev.df_from_query(dq, cols_to_keep=cols_to_keep)

    # Create a filename
    filename = "{}-{}-{}.csv".format(sn, ''.join(start.split('-')),
                        ''.join(end.split('-')))

    # Make the response
    resp = make_response(df.to_csv(date_format='%Y-%m-%dT%H:%M:%SZ'))

    resp.headers['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    resp.headers['Content-Type'] = 'text/csv'

    return resp
