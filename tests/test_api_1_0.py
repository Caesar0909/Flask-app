import unittest
from app.models import *
from app import assets
from app import create_app, db
from base64 import b64encode
import json
import datetime
from flask import url_for
import time
import datetime
import random
from helpers import prepare_db
import pandas as pd

class CredentialsModelTestCase(unittest.TestCase):

    def setUp(self):
        assets._named_bundles = {}

        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.drop_all()
        db.create_all()

        Role.insert_roles()

        self.client = self.app.test_client(use_cookies=True)

        try:
            prepare_db()
        except Exception as e:
            print ("Error setting up test database: {}".format(e))

        self.role_admin = Role.query.filter_by(name='Administrator').first()
        self.role_node = Role.query.filter_by(name='Node').first()
        self.role_user = Role.query.filter_by(name='User').first()

        self.admin_api_key = User.query.filter_by(role=self.role_admin).first().api_token

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _get_headers(self, token=None, form=False):
        if token is None:
            _i = Instrument.query.first()

            token = str(_i.api_token)

        if token == 'na':
            token = ''

        user_pass = b64encode(bytes(token + ":", 'utf-8')).decode('ascii')

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + user_pass
        }

        if form:
            headers['Content-Type'] = "application/x-www-form-urlencoded"

        return headers



    def get(self, url, token=None, **kwargs):
        rv = self.client.get(url, headers=self._get_headers(token))

        db.session.remove()

        body = rv.get_data(as_text=True)

        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass

        return body, rv.status_code, rv.headers

    def post(self, url, data=None, token=None, form=False, **kwargs):
        d = data if data is None else json.dumps(data)

        if form == False:
            rv = self.client.post(url, data=d, headers=self._get_headers(token))
        else:
            rv = self.client.post(url, data=d, headers=self._get_headers(token, form=True),
                    content_type='application/x-www-form-urlencoded')

        db.session.remove()

        body = rv.get_data(as_text=True)

        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass

        return body, rv.status_code, rv.headers

    def put(self, url, data=None, token=None, **kwargs):
        d = data if data is None else json.dumps(data)

        rv = self.client.put(url, data=d, headers=self._get_headers(token))

        db.session.remove()

        body = rv.get_data(as_text=True)

        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass

        return body, rv.status_code, rv.headers

    def delete(self, url, token=None, **kwargs):
        rv = self.client.delete(url, headers=self._get_headers(token))

        db.session.remove()

        body = rv.get_data(as_text=True)

        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass

        return body, rv.status_code, rv.headers

    def test_authentication_protocols(self):
        # Get someone with role `User`
        r = Role.query.filter_by(name='User').first()
        u = User.query.filter_by(role=r).first()

        r, s, h = self.get(url_for('api_1_0.check_auth'), token=u.api_token)

        self.assertEqual(s, 200)

        # Test bad auth
        r, s, h = self.get(url_for('api_1_0.check_auth'), token='a123')

        self.assertEqual(s, 401)

    def test_no_auth_key(self):
        r, s, v = self.get(url_for('api_1_0.check_auth'), token='na')

        self.assertEqual(s, 401)

    def test_no_write_access(self):
        # raise a 401 error
        u = User.query.filter_by(role=self.role_user).first()

        self.assertFalse(u.can(Permission.API_WRITE))

        r, s, v = self.post(url_for('api_1_0.post_device'), token=u.api_token,
                    data={'sn': 'a1234'})

        self.assertEqual(s, 401)

        # Set the users credentials and make sure they still can't write
        u.set_credentials()
        u = User.query.filter_by(role=self.role_user).first()

        self.assertIsNotNone(u.api_token)

        r, s, v = self.post(url_for('api_1_0.post_device'), token=u.api_token,
                    data={'sn': 'a1234'})

        self.assertEqual(s, 401)

    def check_write_status_for_admin(self):
        u = User.query.filter_by(role=self.role_admin).first()

        self.assertTrue(u.can(Permission.API_WRITE))

        r, s, v = self.post(url_for('api_1_0.post_device'), token=u.api_token,
                    data={'sn': 'a1234'})

        self.assertEqual(s, 201)

    def test_post_device(self):
        # Orphan
        data = dict(sn='ORPHAN1', country='IN', city='Delhi', discriminator='orphan')

        r, s, v = self.post(url_for('api_1_0.post_device'), data=data)

        self.assertEqual(s, 201)
        self.assertEqual(r['sn'], data['sn'])

        i = Instrument.query.filter_by(sn=data['sn']).first()

        self.assertIsInstance(i, Orphan)

        # TREX
        data = dict(sn='TREXTEST1', country='IN', city='Delhi', discriminator='trex')

        r, s, v = self.post(url_for('api_1_0.post_device'), data=data)

        self.assertEqual(s, 201)
        self.assertEqual(r['sn'], data['sn'])

        i = Instrument.query.filter_by(sn=data['sn']).first()

        self.assertIsInstance(i, TREX)

        # MIT
        data = dict(sn='MITTEST1', country='IN', city='Delhi', discriminator='mit')

        r, s, v = self.post(url_for('api_1_0.post_device'), data=data)

        self.assertEqual(s, 201)
        self.assertEqual(r['sn'], data['sn'])

        i = Instrument.query.filter_by(sn=data['sn']).first()

        self.assertIsInstance(i, MIT)

        # EBAM
        data = dict(sn='EBAMTEST1', country='IN', city='Delhi', discriminator='ebam')

        r, s, v = self.post(url_for('api_1_0.post_device'), data=data)

        self.assertEqual(s, 201)
        self.assertEqual(r['sn'], data['sn'])

        i = Instrument.query.filter_by(sn=data['sn']).first()

        self.assertIsInstance(i, EBAM)

        # NO MODEL
        data = dict(sn='ORPHAN1', country='IN', city='Delhi')

        r, s, v = self.post(url_for('api_1_0.post_device'), data=data)

        self.assertEqual(s, 400)

        # NO SN
        data = dict(country='IN', city='Delhi', discriminator='other')

        r, s, v = self.post(url_for('api_1_0.post_device'), data=data)

        self.assertEqual(s, 400)

    def test_put_device(self):
        # Get a device
        i = Instrument.query.first()
        sn = i.sn

        u = User.query.first()

        data = dict(country='IN', timezone='Asia/Kolkota')

        r, s, v = self.put(url_for('api_1_0.put_device', sn=sn), data=data, token=u.api_token)

        self.assertEqual(s, 204)

        # Bad request
        r, s, v = self.put(url_for('api_1_0.put_device', sn='a123'), data=data, token=u.api_token)

        self.assertEqual(s, 400)

        i = Instrument.query.first()

        # Make sure that if we send a sn as a keyword, it gets dropped
        r, s, v = self.put(url_for('api_1_0.put_device', sn=sn),
                data=dict(sn='a1234', city='Napa'), token=i.owner.api_token)

        self.assertEqual(s, 204)

    def test_get_device(self):
        i = Instrument.query.first()

        # Make sure a random person can't view the sensor
        r, s, v = self.get(url_for('api_1_0.get_device', sn=i.sn))

        self.assertEqual(s, 400)

        # Get the owner of the sensor
        i = Instrument.query.first()
        u = i.owner

        self.assertTrue(u.canview(i))

        # Test with owner of device
        r, s, v = self.get(url_for('api_1_0.get_device', sn=i.sn), token=u.api_token)

        self.assertEqual(r['sn'], i.sn)
        self.assertEqual(s, 200)

    def test_delete_device(self):
        i = Instrument.query.first()

        u = User.query.first()

        self.assertTrue(u.can(Permission.DELETE))

        r, s, v = self.delete(url_for('api_1_0.delete_device', sn=i.sn), token=u.api_token)

        self.assertEqual(s, 202)

        # Force a 404
        u = User.query.first()
        self.assertTrue(u.can(Permission.DELETE))

        r, s, v = self.delete(url_for('api_1_0.delete_device', sn=i.sn), token=u.api_token)

        self.assertEqual(s, 404)

    def test_webhook_post(self):
        # Orphan
        t = Orphan.query.first()

        data = {
              "name": "RAW",
              "data": "2017-08-11T04:44:30Z,108.72,o3,ppb,0",
              "ttl": 60,
              "published_at": "2017-08-04T14:38:45.937Z",
              "coreid": t.particle_id,
              "userid": "58f6311b15e8976467db8c09",
              "version": 3,
              "public": False,
              "productID": 4964
            }

        resp = self.client.post(url_for('api_1_0.webhook_post'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        # TREX
        t = TREX.query.first()

        data = {
              "name": "RAW",
              "data": "2017-08-05T14:00:35Z,12287.8,12287.8,100.0,125.0",
              "ttl": 60,
              "published_at": "2017-08-04T14:38:45.937Z",
              "coreid": t.particle_id,
              "userid": "58f6311b15e8976467db8c09",
              "version": 1,
              "public": False,
              "productID": 4964
            }

        resp = self.client.post(url_for('api_1_0.webhook_post'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        # MIT
        t = MIT.query.first()

        data = {
              "name": "RAW",
              "data": "2017-08-21T04:37:00Z,10,1,98.9,72.8,793.3,558.3,569.2,618.2,648.7,598.4,833.3,794.0,74.0,8.6,4.0,1.4,0.4,1.0,0.2,0.2,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,35.69,42.03,44.43,3.47,6.7,6.7,5.0,2.5,3.65,10",
              "ttl": 60,
              "published_at": "2017-08-04T14:38:45.937Z",
              "coreid": t.particle_id,
              "userid": "58f6311b15e8976467db8c09",
              "version": 1,
              "public": False,
              "productID": 4964
            }

        resp = self.client.post(url_for('api_1_0.webhook_post'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        # Get that data point and make sure shit wrote correctly
        pt = t.results.all()[-1]

        self.assertTrue(pt.pm1 > 3.5)
        self.assertTrue(pt.pm1 < 5.)
        self.assertEqual(pt.rh_i, 98.9)
        self.assertEqual(pt.temp_i, 72.8)

    def test_webhook_post_meta(self):
        t = Orphan.query.first()

        # Flash Update
        data = {
            "data": "success ",
            "name": "spark/flash/status",
            "ttl": 60,
            "published_at": "2017-08-04T14:38:45.937Z",
            "coreid": t.particle_id,
            "userid": "58f6311b15e8976467db8c09",
            "version": 3,
            "public": False,
            "productID": 4964
        }

        resp = self.client.post(url_for('api_1_0.webhook_post_meta'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        # Flash Update for an MIT node
        t2 = MIT.query.first()

        data = {
            "data": "success ",
            "name": "spark/flash/status",
            "ttl": 60,
            "published_at": "2017-08-04T14:38:45.937Z",
            "coreid": t2.particle_id,
            "userid": "58f6311b15e8976467db8c09",
            "version": 3,
            "public": False,
            "productID": 4964
        }

        resp = self.client.post(url_for('api_1_0.webhook_post_meta'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        # Test soft fail (200)
        data = {
            "data": "success",
            "name": "spark/flash/status",
            "ttl": 60,
            "published_at": "2017-08-04T14:38:45.937Z",
            "coreid": t.particle_id,
            "userid": "58f6311b15e8976467db8c09",
            "version": 3,
            "public": False,
            "productID": 4964
        }

        resp = self.client.post(url_for('api_1_0.webhook_post_meta'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        # Test reset
        data = {
            "data": "success",
            "name": "spark/device/last_reset",
            "ttl": 60,
            "published_at": "2017-08-04T14:38:45.937Z",
            "coreid": t.particle_id,
            "userid": "58f6311b15e8976467db8c09",
            "version": 3,
            "public": False,
            "productID": 4964
        }

        resp = self.client.post(url_for('api_1_0.webhook_post_meta'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 201)

        data = {
            "data": "success",
            "name": "spark/flash/status",
            "ttl": 60,
            "published_at": "2017-08-04T14:38:45.937Z",
            "coreid": 'api',
            "userid": "58f6311b15e8976467db8c09",
            "version": 3,
            "public": False,
            "productID": 4964
        }

        resp = self.client.post(url_for('api_1_0.webhook_post_meta'),
                    headers=self._get_headers(form=True),
                    content_type='application/x-www-form-urlencoded',
                    data=data)

        self.assertEqual(resp.status_code, 200)

    def test_post_data(self):
        i = EBAM.query.first()

        data = {
            'timestamp': "2017-01-01 12:01:32",
            'instr_sn': i.sn,
            'conc_rt': 1.,
            'conc_hr': 23.,
            'flow': 12.,
            'ws': 12,
            'wd': 54,
            'at': 12,
            'rhx': 51,
            'rhi': 12.3,
            'bv_c': 12,
            'ft_c': 12,
            'alarm': 2
        }

        r, s, v = self.post(url_for('api_1_0.data_post'), data=data)

        self.assertEqual(s, 201)

    def test_get_paginated_data(self):
        i = Orphan.query.first()

        r, s, v = self.get(url_for('api_1_0.get_data_by_dev', sn=i.sn), token=self.admin_api_key)

        self.assertEqual(s, 200)
        self.assertIsNotNone(r['meta']['first_url'])

    def test_get_data_user(self):
        u = User.query.get(2)
        i = u.devices.first()

        # Retrieve the data for a public user (non-researcher)
        r, s, v = self.get(url_for('api_1_0.get_data_by_dev', sn=i.sn), token=u.api_token)

        # Make sure the request was a success
        self.assertEqual(s, 200)


        meta = r['meta']
        data = r['data']

        self.assertTrue('timestamp' in data[0].keys())
        self.assertTrue('co' in data[0].keys())
        self.assertTrue('pm1' in data[0].keys())
        self.assertTrue('rh' in data[0].keys())
        self.assertTrue('temp' in data[0].keys())

        self.assertFalse('so2_we' in data[0].keys())

    def test_get_data_researcher(self):
        u = User.query.get(5)
        i = u.following.first()

        self.assertTrue(u.can_view_research_data)

        # Retrieve the data for a public user (non-researcher)
        r, s, v = self.get(url_for('api_1_0.get_research_data_by_dev', sn=i.sn), token=u.api_token)

        # Make sure the request was a success
        self.assertEqual(s, 200)

        meta = r['meta']
        data = r['data'][0]

        self.assertTrue('timestamp' in data.keys())
        self.assertTrue('co_we' in data.keys())
        self.assertTrue('flag' in data.keys())

    def test_get_data_admin(self):
        u = User.query.get(1)
        i = MIT.query.first()

        self.assertTrue(u.can_view_research_data)

        # Retrieve the data for a public user (non-researcher)
        r, s, v = self.get(url_for('api_1_0.get_research_data_by_dev', sn=i.sn), token=u.api_token)

        # Make sure the request was a success
        self.assertEqual(s, 200)

        meta = r['meta']
        data = r['data'][0]

        self.assertTrue('timestamp' in data.keys())
        self.assertTrue('co_we' in data.keys())
        self.assertTrue('flag' in data.keys())

    def test_get_ind_datapoint(self):
        u = User.query.first()

        pt = Data.query.first()

        r, s, v = self.get(url_for('api_1_0.get_datapoint_by_dev', sn=pt.device.sn, id=pt.id),
                            token=u.api_token)

        self.assertEqual(s, 200)

    def test_get_recent_datapoint(self):
        u = User.query.first()

        i = Instrument.query.first()

        r, s, v = self.get(url_for('api_1_0.get_most_recent_datapoint', sn=i.sn),
                            token=u.api_token)

        self.assertEqual(s, 200)

    def test_update_old_datapoint(self):
        u = User.query.first()
        pt = TrexData.query.first()

        data = dict(flag=1)

        r, s, v = self.put(url_for('api_1_0.put_datapoint', sn=pt.device.sn, id=pt.id),
                        data=data, token=u.api_token)

        self.assertEqual(s, 204)

    def test_log(self):
        i = Orphan.query.first()

        data = dict(instr_sn=i.sn, message='test log')

        r, s, v = self.post(url_for('api_1_0.post_log'), data=data)

        self.assertEqual(s, 201)

        l = Log.query.first()
        r, s, v = self.get(url_for('api_1_0.get_log', id=l.id))

        self.assertEqual(s, 200)


        # Get logs
        r, s, v = self.get(url_for('api_1_0.get_all_logs'))

        self.assertEqual(s, 200)

        # Update a log
        l = Log.query.first()
        data = dict(level='CRITICAL')

        r, s, v = self.put(url_for('api_1_0.update_log', id=l.id), data=data)
        self.assertEqual(s, 204)

        # Get logs by device
        i = Orphan.query.first()
        r, s, v = self.get(url_for('api_1_0.get_logs_by_device', sn=i.sn))

        self.assertEqual(s, 200)

    def test_get_devices_permissions(self):
        u = User.query.get(2)

        r, s, v = self.get(url_for('api_1_0.get_devices'), token=u.api_token)

        meta = r['meta']
        data = r['data']

        for each in data:
            i = Instrument.query.filter_by(sn=each['sn']).first()
            u = User.query.get(2)

            self.assertTrue(u.canview(i))

        self.assertIsNotNone(meta['first_url'])
        self.assertIsNotNone(meta['last_url'])
        self.assertIsNotNone(meta['pages'])
        self.assertEquals(meta['page'], 1)

    def test_get_devices_admin(self):
        u = User.query.get(1)

        r, s, v = self.get(url_for('api_1_0.get_devices'), token=u.api_token)

        meta = r['meta']
        data = r['data']

        for each in data:
            i = Instrument.query.filter_by(sn=each['sn']).first()
            u = User.query.get(1)

            self.assertTrue(u.canview(i))

        self.assertIsNotNone(meta['first_url'])
        self.assertIsNotNone(meta['last_url'])
        self.assertIsNotNone(meta['pages'])
        self.assertEquals(meta['page'], 1)

        self.assertEqual(len(data), Instrument.query.count())

    def test_filtering(self):
        u = User.query.get(1)
        token = u.api_token

        # test `eq`
        filterquery = "city,eq,Delhi"

        r, s, v = self.get(url_for('api_1_0.get_devices', filter=filterquery), token=token)

        meta = r['meta']
        data = r['data']

        for each in data:
            self.assertEquals(each['city'], 'Delhi')

        # test `ne`
        filterquery = 'city,ne,Delhi'

        r, s, v = self.get(url_for('api_1_0.get_devices', filter=filterquery), token=token)

        meta = r['meta']
        data = r['data']

        for each in data:
            self.assertNotEqual(each['city'], 'Delhi')

    def test_sorting(self):
        u = User.query.get(1)
        token = u.api_token

        # older dates should appear first
        q = "last_updated,asc"

        r, s, v = self.get(url_for('api_1_0.get_devices', sort=q), token=token)

        meta = r['meta']
        data = r['data']

        last_updated = None
        for each in data:
            if last_updated is None:
                pass
            else:
                lu = pd.to_datetime(data['last_updated'])
                self.assertGreaterEqual(lu, last_updated)

                last_updated = lu

        # older dates should appear first
        q = "last_updated,desc"

        r, s, v = self.get(url_for('api_1_0.get_devices', sort=q), token=token)

        meta = r['meta']
        data = r['data']

        last_updated = None
        for each in data:
            if last_updated is None:
                pass
            else:
                lu = pd.to_datetime(data['last_updated'])
                self.assertLessEqual(lu, last_updated)

                last_updated = lu
