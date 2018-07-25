from flask import session, request, make_response
from flask_socketio import emit
from flask_login import current_user
from .. import socketio
from ..models import *
from .. import db
import pandas as pd

@socketio.on('more data', namespace='/device')
def more_data(message):
    """Grab more data and return"""
    sn      = str(message['sn'])
    lot     = str(message['lot'])
    secret  = str(message['secret'])

    # Get the data
    instr = Instrument.query.filter_by(sn=sn).first()

    data = []

    try:
        data = instr._plotly(span=lot, researcher=secret)
    except Exception as e:
        print ("Error with more data emit: {}".format(e))

    emit('update data', {'results': data})


# Error handler for the device namespace
@socketio.on_error('/device')
def error_handler_device(e):
    print ("/device namespace error: ")
    print (request.event['message'])
    print (request.event['args'])
