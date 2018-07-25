'''
    Create lots of fake, but useful data for the local server

    To execute:

        from fake_data import create_fake_data
        create_fake_data()
'''

from app import models, db
from app.models import *
import datetime
import boto3
import sendgrid

SENDGRID_API_KEY = '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'

def send_email(num_csvs):
    """
    """
    sender  = sendgrid.SendGridClient(SENDGRID_API_KEY)
    email   = sendgrid.Mail()

    email.set_subject('CSV Generation')

    email.add_to('david@david.com')
    email.set_from('dhagan@mit.edu')
    email.set_from_name('CSV Generation Tool')
    email.set_replyto('dhagan@mit.edu')

    message = """
            <h3>Another CSV update has been completed!</h3>
            <p>A total of {} files (x2) were added just now.</p>
            """.format(num_csvs)

    email.set_html(message)

    status, msg = sender.send(email)

    print (status, msg)

    return

def make_csvs(current_bucket, month = False):
    s3          = boto3.resource('s3')
    bucket      = s3.Bucket(current_bucket)
    files_added = 0

    # Build for the previous 24 hour period
    t0 = datetime.date.today() - datetime.timedelta(days = 1)

    for each in Instrument.query.all():
        if month == True:
            # Get all data for the previous month and dump it
            # Change filename to be month in text (i.e. Jan-2017)
            break
        try:
            res = each.csv_to_aws(bucket, t0, '1d', dev = True)
            res = each.csv_to_aws(bucket, t0, '1d', dev = False)
        except Exception as e:
            print (e)

        if res is True:
            files_added = files_added + 1

    send_email(files_added)

    return
