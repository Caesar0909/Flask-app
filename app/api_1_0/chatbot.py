"""Handles all API calls for the facebook messenger bot"""

from ..models import *
from flask  import request, abort, url_for, current_app
from .. import db
from . import api_1_0
from datetime import datetime
import requests
from sqlalchemy import func
import json
from textblob import TextBlob

STATUS_KEYWORDS = ('status', 'doing', 'alive')

def check_for_status(sentence): #pragma: no cover
    #Check to see if the user wants to get the status of a sensor
    for word in sentence.words:
        if word.lower() in STATUS_KEYWORDS:
            return True

    return False

def check_for_valid_device(sentence): #pragma: no cover
    #Check for a valid SN
    VALID_DEVICES = [x.sn.lower() for x in Instrument.query.all()]

    dev = None

    for word in sentence.words:
        if word.lower() in VALID_DEVICES:
            dev = Instrument.query.filter(func.lower(Instrument.sn) == word.lower()).first()

    return dev

def time_since_update(timestamp): #pragma: no cover
    #Return a message with the time since last update.
    dt = datetime.utcnow() - timestamp

    days = dt.days
    seconds = dt.seconds

    if days > 0:
        msg_suffix = "{:.0f} days ago.".format(dt.days)
    else:
        if seconds < 60:
            msg_suffix = "{:.0f} seconds ago.".format(seconds)
        elif seconds < 60*60:
            msg_suffix = "{:.0f} minutes ago.".format(seconds / 60.)
        elif seconds < 24*60*60:
            msg_suffix = "{:.1f} hours ago.".format(seconds / 60. / 24.)
        else:
            msg_suffix = "a while ago...?"

    return msg_suffix

@api_1_0.route('/webhook/chat', methods=['GET']) #pragma: no cover
def bot_verify():
    #Verification check that FBOOK requires.
    if request.args.get('hub.mode') == "subscribe" and request.args.get('hub.challenge'):
        if not request.args.get('hub.verify_token') == current_app.config['FBOOK_CONFIG_TOKEN']:
            return "verification token mismatch", 403
        return request.args['hub.challenge'], 200

    return "Hello, world!", 200

@api_1_0.route('/webhook/chat', methods=['POST']) #pragma: no cover
def bot_chat():
    data = request.get_json()

    if data['object'] == 'page':
        for entry in data['entry']: # returns a dict (messaging)
            for messaging_event in entry['messaging']:
                if messaging_event.get('message'):  # someone sent us a message
                    sender_id       = messaging_event['sender']['id']
                    recipient_id    = messaging_event['recipient']['id']
                    message_txt     = messaging_event['message']['text']

                    print ("{}: {}".format(sender_id, message_txt))

                    message_blob = TextBlob(message_txt)

                    # Let's try to figure out what the user wants!
                    if check_for_status(message_blob) == True:
                        # Try to get the status of the sensor
                        dev = check_for_valid_device(message_blob)
                        if dev is not None:
                            msg = "Hi! {} was last updated {}".format(dev.sn, time_since_update(dev.last_updated))
                        else:
                            msg = "Oops. It looks like you have an invalid serial number."
                    else:
                        msg = "Oops. I don't understand your request...I'm not very intelligent...yet ;)"

                    send_message(sender_id, msg)

    return "ok", 200

def send_message(recipient_id, msg): #pragma: no cover
    params = {"access_token": current_app.config['FBOOK_PAGE_ACCESS_TOKEN']}
    headers = {'Content-Type': 'application/json'}

    data = json.dumps(
                {
                    'recipient': {
                        "id": recipient_id
                        },
                    'message': {
                        "text": msg
                        }
                    }
                )

    uri = "https://graph.facebook.com/v2.6/me/messages"
    r = requests.post(uri, params=params, headers=headers, data=data)

    if r.status_code != 200:
        print (r.status_code, r.json())

    return
