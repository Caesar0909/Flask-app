from flask import Blueprint
from .decorators import etag

api_1_0 = Blueprint('api_1_0', __name__)

from . import errors, authentication, auth, data, devices, logs, chatbot

@api_1_0.after_request
@etag
def after_request(rv):
    ''' Generate an etag header '''
    return rv
