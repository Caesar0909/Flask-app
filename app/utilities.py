"""Utility functions."""
import math
import sendgrid
import boto3
import os
from flask import current_app
from datetime import datetime, date, timedelta
from . import db
from app import models
from sqlalchemy.orm.exc import ObjectDeletedError

key_mapper = dict()

key_mapper['so2'] = dict()

def prev_month_start(dt):
    """Get the first day of the previous month."""
    _y, _m, _d = dt.year, dt.month, dt.day

    if _m == 1:
        _m = 12
        _y -= 1
    else:
        _m -= 1

    _d = 1

    return date(_y, _m, _d)

def safe_cast(value, multiplier=1, func=float):
    """Cast a value to a float safely."""
    res = None
    try:
        res = func(value)
    except:
        pass

    if res is not None and math.isnan(res):
        res = None

    if res is not None:
        res = res * multiplier

    return res

def send_email(email_subject, recipient, message, config = None):
    """Send an email using SendGrid."""
    try:
        config = current_app.config
    except:
        config = config

    sender  = sendgrid.SendGridClient(config['SENDGRID_API_KEY'])

    email   = sendgrid.Mail()

    email.set_subject(email_subject)
    email.add_to(recipient)
    email.set_from(config['FROM_EMAIL'])
    email.set_from_name(config['FROM_NAME'])
    email.set_replyto(config['FROM_NAME'])
    email.set_html(message)

    status, msg = sender.send(email)

    return status, msg

def backup_data_to_s3(config, prev_month=False, **kwargs):
    """Backup data to AmazonAWS S3."""
    today   = date.today()
    added   = ""
    failed  = ""

    if not prev_month:
        print ("Beginning daily data backup: {}".format(datetime.now()))
    else:
        print ("Beginning monthly data backup: {}".format(datetime.now()))

    print ("Uploading data to {}".format(config['AWS_BUCKET']))

    if not prev_month:
        tf = today
        t0 = tf - timedelta(days=1)
    else:
        tf = today.replace(day=1)
        t0 = prev_month_start(today)

    dt = (tf-t0).days
    s3 = boto3.resource(
                's3',
                aws_access_key_id=config['BOTO3_ACCESS_KEY'],
                aws_secret_access_key=config['BOTO3_SECRET_KEY']
                )

    bucket_name = config['AWS_BUCKET']
    updated = 0
    msg = ""

    if prev_month:
        msg += "<h1>Monthly Data Backup Summary</h1>"
    else:
        msg += "<h1>Daily Data Backup Summary</h1>"

    msg += "<ul>"
    msg += "<li><strong>Executed at</strong>: {}</li>".format(datetime.now())
    msg += "<li>WD: {}</li>".format(os.getcwd())
    msg += "<li><strong>Start</strong>: {}</li>".format(t0)
    msg += "<li><strong>End</strong>: {}</li>".format(tf)
    msg += "<li><strong>Num. Days</strong>: {}</li>".format(dt)
    msg += "<li><strong>S3 Bucket</strong>: {}</li>".format(bucket_name)

    # Iterate over each Instrument and generate csvs
    for each in models.Instrument.query.all():
        try:
            if not prev_month:
                key = each.csv_to_aws(s3, bucket_name, t0, tf, developer=True)
                key = each.csv_to_aws(s3, bucket_name, t0, tf, developer=False)
            else:
                key = each.csv_to_aws(s3, bucket_name, t0, tf, developer=True)
                key = each.csv_to_aws(s3, bucket_name, t0, tf, developer=False)

            added += "<li>{}</li>".format(key.key)
            updated += 1
        except Exception as e:
            print (e)

    msg += "<li><strong>Files Added/Updated</strong>: {}</li>".format(updated)
    msg += "</ul><br />"

    msg += "<h4>New Uploads</h4><ul>{}</ul>".format(added)
    msg += "<h4>Failures</h4><ul>{}</ul>".format(failed)

    # Send an email with the summary
    status, msg = send_email(
                        "S3 Data Backup",
                        recipient=config['ADMINS'],
                        message=msg,
                        config=config)

    return

def daily_backup_data_to_s3(config):
    """"""
    return backup_data_to_s3(config, prev_month=False)

def monthly_backup_data_to_s3(config):
    """"""
    return backup_data_to_s3(config, prev_month=True)
