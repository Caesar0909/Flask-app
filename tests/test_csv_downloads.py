import unittest
from app.models import *
from app import create_app, db
from app.exceptions import EmptyDataFrameException
import sqlite3
import datetime
import random
from helpers import prepare_db
import pandas as pd
from io import StringIO
from sqlalchemy.exc import IntegrityError
import boto3
from flask_login import login_user, logout_user, current_user
from app import assets


class CredentialsModelTestCase(unittest.TestCase):
    def setUp(self):
        assets._named_bundles = {}
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.client = self.app.test_client(use_cookies=True)

        try:
            prepare_db()
        except Exception as e:
            pass

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_user(self, user):
        resp = self.client.post(url_for('auth.login'), data={
            'email': user.email,
            'password': 'password'
        }, follow_redirects=True)

        return True if resp.status_code == 200 else False

    def test_admin_ebam(self):
        r = Role.query.filter_by(name='Administrator').first()
        u = User.query.filter_by(role=r).first()

        # Login the user
        resp = self.login_user(u)

        # Download a file
        # 1) Get a Device that can be seen by the user
        d = EBAM.query.first()

        # Make sure the user can see the device
        self.assertTrue(u.canview(d))
        self.assertTrue(u.can_view_research_data)

        # 2) Make an API Call to download data for this device
        rv = self.client.get(
                url_for("api_1_0.download_csv",
                        sn=d.sn, start="2017-01-01",
                        end="2018-12-01"))

        # 3) Convert the unicode to a dataframe for easier manipulation
        body = pd.read_csv(StringIO(rv.get_data(as_text=True)), sep=',')

        # 4) Retrieve the columns
        cols = body.columns

        # Make sure we have the correct columns for an Administrator (all of them)
        self.assertTrue('timestamp' in cols)
        self.assertTrue('timestamp_local' in cols)

        # Check to ensure the additional columns are present for the EBAM instrument
        for key in d.private_cols:
            self.assertTrue(key in cols)

    def test_admin_orphan(self):
        r = Role.query.filter_by(name='Administrator').first()
        u = User.query.filter_by(role=r).first()

        # Login the user
        resp = self.login_user(u)

        # Download a file
        # 1) Get a Device that can be seen by the user
        d = Orphan.query.first()

        # Make sure the user can see the device
        self.assertTrue(u.canview(d))
        self.assertTrue(u.can_view_research_data)

        # 2) Make an API Call to download data for this device
        rv = self.client.get(
                url_for("api_1_0.download_csv",
                        sn=d.sn, start="2017-01-01",
                        end="2018-12-01"))

        # 3) Convert the unicode to a dataframe for easier manipulation
        body = pd.read_csv(StringIO(rv.get_data(as_text=True)), sep=',')

        # 4) Retrieve the columns
        cols = body.columns

        # Make sure we have the correct columns for an Administrator (all of them)
        self.assertTrue('timestamp' in cols)
        self.assertTrue('timestamp_local' in cols)

        # Check to ensure the additional columns are present for the EBAM instrument
        for key in d.private_cols:
            self.assertTrue(key in cols)

    def test_admin_trex(self):
        admin = Role.query.filter_by(name='Administrator').first()
        u = User.query.filter_by(role=admin).first()

        # Download a file
        # 1) Get a Device that can be seen by the user
        d = TREX.query.first()

        # Login the user
        resp = self.login_user(u)

        # Make sure the user can see the device
        self.assertTrue(u.canview(d))
        self.assertTrue(u.can_view_research_data)

        # 2) Make an API Call to download data for this device
        rv = self.client.get(
                url_for("api_1_0.download_csv",
                        sn=d.sn, start="2017-01-01",
                        end="2018-12-01"))

        # 3) Convert the unicode to a dataframe for easier manipulation
        body = pd.read_csv(StringIO(rv.get_data(as_text=True)), sep=',')

        # 4) Retrieve the columns
        cols = body.columns

        # Make sure we have the correct columns for an Administrator (all of them)
        self.assertTrue('timestamp' in cols)
        self.assertTrue('timestamp_local' in cols)

        # Check to ensure the additional columns are present for the EBAM instrument
        for key in d.private_cols:
            self.assertTrue(key in cols)

    def test_admin_mit(self):
        admin = Role.query.filter_by(name='Administrator').first()
        u = User.query.filter_by(role=admin).first()

        # Login the user
        resp = self.login_user(u)

        # Download a file
        # 1) Get a Device that can be seen by the user
        d = MIT.query.first()

        # Make sure the user can see the device
        self.assertTrue(u.canview(d))
        self.assertTrue(u.can_view_research_data)

        # 2) Make an API Call to download data for this device
        rv = self.client.get(
                url_for("api_1_0.download_csv",
                        sn=d.sn, start="2017-01-01",
                        end="2017-12-01"))

        # 3) Convert the unicode to a dataframe for easier manipulation
        body = pd.read_csv(StringIO(rv.get_data(as_text=True)), sep=',')

        # 4) Retrieve the columns
        cols = body.columns

        # Make sure we have the correct columns for an Administrator (all of them)
        self.assertTrue('timestamp' in cols)
        self.assertTrue('timestamp_local' in cols)

        # Check to ensure the additional columns are present for the EBAM instrument
        for key in d.private_cols:
            self.assertTrue(key in cols)

    def test_user(self):
        r = Role.query.filter_by(name='User').first()
        u = User.query.filter_by(role=r).first()

        # Login the user
        resp = self.login_user(u)

        # Download a file
        # 1) Get a Device that can be seen by the user
        d = u.devices.first()

        self.assertTrue(u.canview(d))
        self.assertFalse(u.can_view_research_data)

        # 2) Make an API Call to download data for this device
        rv = self.client.get(
                url_for("api_1_0.download_csv",
                        sn=d.sn, start="2017-01-01",
                        end="2018-12-01"))

        # 3) Convert the unicode to a dataframe for easier manipulation
        body = pd.read_csv(StringIO(rv.get_data(as_text=True)), sep=',')

        # 4) Retrieve the columns
        cols = list(body.columns)

        # Make sure we have the correct columns for an Administrator (all of them)
        self.assertTrue('timestamp' in cols)
        self.assertTrue('timestamp_local' in cols)

        for key in d.public_cols:
            self.assertTrue(key in cols)

        # Make sure there are none of the extras
        diff = list(set(d.private_cols) - set(d.public_cols))

        for key in diff:
            self.assertFalse(key in cols)

    def test_all_users_in_group(self):
        g = Group.query.filter_by(name='MIT').first()
        d = MIT.query.first()

        for m in g.members.all():
            # login the user
            resp = self.login_user(m)

            # Make sure the user can see the data
            self.assertTrue(m.canview(d))

            # Download the file
            rv = self.client.get(
                    url_for("api_1_0.download_csv",
                            sn=d.sn, start="2017-01-01",
                            end="2017-12-01"))

            # 3) Convert the unicode to a dataframe for easier manipulation
            body = pd.read_csv(StringIO(rv.get_data(as_text=True)), sep=',')

            # 4) Retrieve the columns
            cols = list(body.columns)

            # Make sure we have the correct columns for an Administrator (all of them)
            self.assertTrue('timestamp' in cols)
            self.assertTrue('timestamp_local' in cols)

            for key in d.public_cols:
                self.assertTrue(key in cols)
