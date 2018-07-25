'''
    Contains helper functions
'''
import re
import datetime
import os
from flask import current_app
import pytz

def clean_round(val, places = 3):
    if isinstance(val, float):
        return round(val, places)

    return None

def calculate_days(val):
    '''
    '''
    days = None
    b, m, p = re.split('(\d+)', val)
    if p == 'd':
        days = int(m) * 1
    elif p == 'w':
        days = int(m) * 7
    elif p == 'm':
        days = int(m) * 30
    else:
        days = int(m) * 365

    return days

def calculate_minutes(val):
    """Calculate the number of minutes

    ex. '1h' -> 60 minutes
    """
    minutes = None
    b, m, p = re.split('(\d+)', val)

    if p == 'min':
        minutes = int(m) * 1                    # minutes
    elif p == 'h':
        minutes = int(m) * 60                   # hours
    elif p == 'd':
        minutes = int(m) * 60 * 24              # days
    elif p == 'w':
        minutes = int(m) * 60 * 24 * 7          # weeks
    else:
        minutes = int(m) * 60 * 24 * 7 * 30     # months

    return minutes

def calculate_start_timestamp(span):
    """Return the current time - span
    """
    return datetime.datetime.utcnow() - datetime.timedelta(minutes=calculate_minutes(span))

def model_type(model):
    """Returns the Model Type from the model name
    """
    model = model.upper()

    if model in ['CO-A4', 'SO2-A4', 'NO-A4', 'NOX-A4', 'OX-A4']:
        ans = 'toxic'
    elif model in ['HIH6130', 'PT1000']:
        ans = 'met'
    elif model in ['OPC-N2']:
        ans = 'particle'
    elif model in ['PID-AH', 'PID-A1']:
        ans = 'pid'
    elif model in ['MIT', 'X1', 'X2']:
        ans = 'mit'
    elif model in ['E-BAM', 'EBAM']:
        ans = 'ebam'
    elif model in ['MITv2', 'mit_v2', 'MIT_v2']:
        ans = 'mit_v2'
    elif model.lower() in ['trex', 'trex2017']:
        ans = 'trex'
    else:
        ans = 'other'

    return ans

def parse_csv(value, typ = 'float'):
    """
    """
    resp = None
    if typ == 'float':
        try:
            resp = float(value)
        except:
            resp = None
    elif typ == 'int':
        try:
            resp = int(value)
        except:
            resp = None
    else:
        resp = None

    return resp


def allowed_file(filename):
    ext = os.path.splitext(filename.lower())[1][1:]
    return True if ext in current_app.config['ALLOWED_EXTENSIONS'] else False

def to_timezone(timestamp, tzone, isoformat=True, replace=False):
    """
    """
    res = None
    if tzone is not None:
        local   = pytz.timezone(tzone)
        res     = timestamp.replace(tzinfo=pytz.UTC).astimezone(local)

        if replace:
            res = res.replace(tzinfo=None)

        if isoformat:
            res = res.isoformat()

    return res
