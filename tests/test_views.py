import unittest
from app.models import *
from app import create_app, db
import sqlite3
import datetime
import random
import re
from helpers import prepare_db
from flask_login import login_user, logout_user, current_user
from app import assets

class CredentialsModelTestCase(unittest.TestCase):
    def setUp(self):
        assets._named_bundles = {}
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        Role.insert_roles()

        self.client = self.app.test_client(use_cookies=True)

        try:
            prepare_db()
        except Exception as e:
            print ("Error setting up test database: {}".format(e))

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_register_and_login(self):
        # Test the blank registration page
        response = self.client.get(url_for('auth.register'))
        data = response.get_data(as_text=True)

        self.assertTrue('REGISTER' in data)

        # Test blank login page
        response = self.client.get(url_for('auth.login'))
        data = response.get_data(as_text=True)

        self.assertTrue('LOG IN' in data)


        # Go through the registration and login process
        response = self.client.post(url_for('auth.register'), data={
            'email': 'test@testing123.com',
            'username': 'testing123',
            'password': 'cat12345',
            'password2': 'cat12345'
        })

        self.assertTrue(response.status_code == 302)

        # At this point, we should be registered and logged in.
        # Try going to the registration page again (should be redirected)
        response = self.client.get(url_for('auth.register'))
        data = response.get_data(as_text=True)
        self.assertTrue('redirected' in data)

        # Next, let's logout the user
        response = self.client.get(url_for('auth.logout'), follow_redirects=True)
        data = response.get_data(as_text=True)

        self.assertTrue('TATA CENTER' in data) #main landing page

        # Next, login with new credentials (should go to unconfirmed)
        response = self.client.post(url_for('auth.login'), data={
            'email': 'test@testing123.com',
            'password': 'cat1234'},
            follow_redirects=True)

        response = self.client.post(url_for('auth.login'), data={
            'email': 'test@testing123.com',
            'password': 'cat12345'},
            follow_redirects=True)

        data = response.get_data(as_text=True)
        self.assertTrue('you have not confirmed' in data)

        # Test the confirmation landing page
        response = self.client.get(url_for('main.unconfirmed'))
        data = response.get_data(as_text=True)
        self.assertTrue('not confirmed' in data)

        # Next, confirm the new user
        user = User.query.filter_by(username='testing123').first()
        token = user.generate_confirmation_token()

        response = self.client.get(url_for('auth.confirm', token=token),
                    follow_redirects=True)

        data = response.get_data(as_text=True)
        self.assertTrue('Thank you for confirming' in data)

        # Test the unconfirmed landing page
        response = self.client.get(url_for('main.unconfirmed'))
        data = response.get_data(as_text=True)
        self.assertTrue('redirect' in data)

        # Try hitting the login page again to make sure it redirects
        response = self.client.get(url_for('auth.confirm', token=token))
        data = response.get_data(as_text=True)
        self.assertTrue('redirect' in data)

        # Send a confirmation email
        response = self.client.get(url_for('auth.resend_confirmation'))
        data = response.get_data(as_text=True)
        #self.assertTrue()

    def test_reset_password(self):
        user = User.query.first()

        # Test the blank password reset form
        response = self.client.get(url_for('auth.forgot_password'))
        data = response.get_data(as_text=True)
        self.assertTrue('RESET PASSWORD' in data)

        # Now, make a POST request to that url to initiate the password reset process
        response = self.client.post(url_for('auth.forgot_password'),
            data=dict(email=user.email))
        data = response.get_data(as_text=True)
        self.assertTrue('redirect' in data)

        # Generate a token for the user
        token = user.generate_confirmation_token()

        # Visit the blank reset form
        response = self.client.get(url_for('auth.confirm_reset', token=token,
                    username=user.username))
        data = response.get_data(as_text=True)
        self.assertTrue('RESET PASSWORD' in data)

        response = self.client.post(url_for('auth.confirm_reset', token=token,
                    username=user.username), data=dict(password='a12345', password2='a12345'))
        data = response.get_data(as_text=True)
        self.assertTrue('redirect' in data)

    def test_landing_page(self):
        response = self.client.get(url_for('main.index'))

        data = response.get_data(as_text=True)

        self.assertTrue('TATA CENTER AIR QUALITY' in data)
        self.assertTrue('LOGIN' in data)
        self.assertTrue('SIGN UP' in data)

    def test_views_admin(self):
        pass

    def test_views_manager(self):
        pass

    def test_views_user_main_index_page(self):
        # User: User(email='user@test.com', username='test_user', password='test_user')

        # Log In
        response = self.client.post(url_for('auth.login'), data={
            'email': 'user@test.com',
            'password': 'password'},
            follow_redirects=True)

        response = self.client.get(url_for('main.index'))
        data = response.get_data(as_text=True)

        self.assertTrue('API' in data)
        self.assertTrue('DEVICES' in data)
        self.assertTrue('ADMIN' not in data)

    def test_views_user_api_tokens_page(self):
        # User: User(email='user@test.com', username='test_user', password='test_user')
        user = User.query.filter_by(username='test_user').first()

        response = self.client.post(url_for('auth.login'), data={
            'email': 'user@test.com',
            'password': 'password'},
            follow_redirects=True)

        # Get the tokens page
        response = self.client.get(url_for('main.user_api'))
        data = response.get_data(as_text=True)

        # Make sure the button is there
        self.assertTrue('Generate New Token' in data)
        self.assertTrue('Name' in data)

        # Test token form
        response = self.client.post(url_for('main.user_api'), data={
            'name': 'test_token',
            'user_id': user.id},
            follow_redirects=True)

        data = response.get_data(as_text=True)
        self.assertTrue('test_token' in data)
        self.assertTrue('WRITE' not in data)

    def test_views_user_devices_page(self):
        # User: User(email='user@test.com', username='test_user', password='test_user')
        user = User.query.filter_by(username='test_user').first()

        # Make sure the user has devices, or add all public devices
        i = Instrument.query.first()

        response = self.client.post(url_for('auth.login'), data={
            'email': 'user@test.com',
            'password': 'password'},
            follow_redirects=True)

        # Get the tokens page
        response = self.client.get(url_for('main.user_portal'))
        data = response.get_data(as_text=True)

        #print (data)
        self.assertTrue('Model' in data)

    def test_views_user_device_page(self):
        # User: User(email='user@test.com', username='test_user', password='test_user')
        user = User.query.filter_by(username='test_user').first()

        response = self.client.post(url_for('auth.login'), data={
            'email': 'user@test.com',
            'password': 'password'},
            follow_redirects=True)

        # Make sure the user can see the device
        # Get a device the user can see
        i = user.devices.first()

        self.assertTrue(user.canview(i))

        # Get the tokens page
        response = self.client.get(url_for('main.view_public_device', sn=i.sn))
        data = response.get_data(as_text=True)

        self.assertTrue('Plot' in data)
        self.assertTrue('About' in data)
        self.assertTrue('Downloads' in data)
        self.assertTrue('API' in data)
        self.assertFalse('Logs' in data)
