import unittest
from app.models import *
from app import create_app, db
from app.exceptions import EmptyDataFrameException
import sqlite3
import datetime
import random
from helpers import prepare_db
from sqlalchemy.exc import IntegrityError
import boto3
from app import assets

class CredentialsModelTestCase(unittest.TestCase):
    def setUp(self):
        assets._named_bundles = {}
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        try:
            prepare_db()
        except Exception as e:
            pass

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_instrument(self):
        i = Orphan.query.first()

        # Make some data
        i.fakedata(n=100, direction='backward')

        # Test the url
        self.assertTrue(i.sn in i.get_url())

        # Test credentials
        c = i.api_token

        # Set new credentials
        i.set_credentials()

        self.assertNotEqual(c, i.credentials)

        # Test to_geojson_feature
        if i.latitude is not None:
            geo = i.to_geojson_feature()

            self.assertEqual(geo['properties']['sn'], i.sn)
            self.assertEqual(geo['properties']['url'], url_for('main.view_public_device', sn=i.sn))

        # Test to_json
        js = i.to_json()

        self.assertEqual(js['sn'], i.sn)
        self.assertEqual(js['url'], i.get_url())

        # test 'has'
        self.assertFalse(i.has('so2'))
        self.assertFalse(i.has('h2s'))
        self.assertFalse(i.has('o3'))
        self.assertFalse(i.has('co'))
        self.assertFalse(i.has('pm25'))
        self.assertFalse(i.has('pm10'))

        # Test csv generation (returns an AWS object)
        s3 = boto3.resource(
                    's3',
                    aws_access_key_id=self.app.config['BOTO3_ACCESS_KEY'],
                    aws_secret_access_key=self.app.config['BOTO3_SECRET_KEY']
                    )

        bucket_name = self.app.config['AWS_BUCKET']

        t0 = datetime.date.today()
        tf = t0 + datetime.timedelta(days=1)
        key = i.csv_to_aws(bucket_name=bucket_name, t0=t0, tf=tf, developer=False, s3=s3)

        self.assertIsNotNone(key)
        self.assertIsNotNone(key.bucket_name)
        self.assertIsNotNone(key.date)
        self.assertIsNotNone(key.length)
        self.assertIsNotNone(key.size_mb)

        tf = t0 + datetime.timedelta(days=3)
        key = i.csv_to_aws(bucket_name=bucket_name, t0=t0, tf=tf, developer=True, s3=s3,
                            dropna=True)

        self.assertIsNotNone(key)
        self.assertIsNotNone(key.bucket_name)
        self.assertIsNotNone(key.date)
        self.assertIsNotNone(key.length)
        self.assertIsNotNone(key.size_mb)

        # Update the old one
        key = i.csv_to_aws(bucket_name=bucket_name, t0=t0, tf=tf, developer=True, s3=s3,
                            dropna=True)

        self.assertIsNotNone(key)
        self.assertIsNotNone(key.bucket_name)
        self.assertIsNotNone(key.date)
        self.assertIsNotNone(key.length)
        self.assertIsNotNone(key.size_mb)

        # Force S3 error
        with self.assertRaises(S3Exception):
            key = i.csv_to_aws(bucket_name=i.sn, t0=t0, tf=tf, developer=True, s3=s3,
                                dropna=True)

        # Force exception
        with self.assertRaises(EmptyDataFrameException):
            t0 = datetime.date(2017,1,1)
            tf = t0 + datetime.timedelta(days=3)
            key = i.csv_to_aws(bucket_name=bucket_name, t0=t0, tf=tf, developer=True,
                                s3=s3)

    def test_instrument_orphan(self):
        data = {
            'sn': 'OZONE_1111',
            'ip': '100.1.2.4',
            'city': 'Delhi',
            'country': 'IN',
            'location': 'CP',
            'model': '2BTech 202'
        }

        new = Orphan.create(data)

        db.session.add(new)
        db.session.commit()

        # Test the class
        self.assertIsInstance(new, Orphan)
        self.assertIsInstance(new, Instrument)
        self.assertEqual(new.sn, data['sn'])
        self.assertEqual(new.ip, data['ip'])
        self.assertEqual(new.city, data['city'])
        self.assertEqual(new.country, data['country'])
        self.assertEqual(new.model, data['model'])
        self.assertEquals(new.results.count(), 0)

        # Update the country
        new.from_dict({'country': 'US'}, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.country, 'US')

        # Make some data
        new.fakedata(n=100, direction='backward')

        # Test _plotly
        pltly = new._plotly(researcher=False)

        self.assertEqual(pltly['meta']['keys'], ['value'])
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Get param
        p = new.get_param()
        self.assertEqual(p, 'o3')

        # Test _plotly
        pltly = new._plotly(researcher=True)

        self.assertEqual(pltly['meta']['keys'], ['value'])
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Test bad required key
        with self.assertRaises(KeyError):
            Orphan.create({'ip': '1.0.2.1'})

        # Test data cascading
        n_points = new.results.count()
        self.assertGreater(n_points, 0)

        # Drop one datapoint
        last = new.results.first()
        self.assertTrue(last.drop())
        self.assertLess(new.results.count(), n_points)

        # Drop the instrument and then see how many data points are left
        self.assertTrue(new.drop())
        self.assertEqual(Data.query.filter_by(instr_sn=data['sn']).count(), 0)

    def test_instrument_ebam(self):
        data = {
            'sn': 'EBAMXYZ',
            'ip': '100.1.2.4',
            'city': 'Delhi',
            'country': 'IN',
            'location': 'CP',
            'model': 'E-BAM'
        }

        new = EBAM.create(data)

        db.session.add(new)
        db.session.commit()

        # Test the class
        self.assertIsInstance(new, EBAM)
        self.assertIsInstance(new, Instrument)
        self.assertEqual(new.sn, data['sn'])
        self.assertEqual(new.ip, data['ip'])
        self.assertEqual(new.city, data['city'])
        self.assertEqual(new.country, data['country'])
        self.assertEqual(new.model, data['model'])
        self.assertEquals(new.results.count(), 0)

        # Update the country
        new.from_dict({'country': 'US'}, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.country, 'US')

        self.assertTrue(new.has('pm25'))
        self.assertFalse(new.has('h2s'))
        self.assertFalse(new.has('o3'))
        self.assertFalse(new.has('co'))
        self.assertFalse(new.has('so2'))
        self.assertFalse(new.has('pm10'))

        # Make some data
        new.fakedata(n=100, direction='backward')

        # Test _plotly
        pltly = new._plotly(researcher=False)

        self.assertIsNotNone(pltly['meta']['keys'])
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Test _plotly
        pltly = new._plotly(researcher=True)

        self.assertIsNotNone(pltly['meta']['keys'])
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Add specific checks for labels and shit

    def test_instrument_trex(self):
        data = {
            'sn': 'TREXXYZ',
            'ip': '100.1.2.4',
            'city': 'Delhi',
            'country': 'IN',
            'location': 'CP',
            'model': 'TREX'
        }

        new = TREX.create(data)

        db.session.add(new)
        db.session.commit()

        # Test the class
        self.assertIsInstance(new, TREX)
        self.assertIsInstance(new, Instrument)
        self.assertEqual(new.sn, data['sn'])
        self.assertEqual(new.ip, data['ip'])
        self.assertEqual(new.city, data['city'])
        self.assertEqual(new.country, data['country'])
        self.assertEqual(new.model, data['model'])
        self.assertEquals(new.results.count(), 0)

        # Update the country
        new.from_dict({'country': 'US'}, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.country, 'US')

        self.assertTrue(new.has('so2'))
        self.assertFalse(new.has('h2s'))
        self.assertFalse(new.has('o3'))
        self.assertFalse(new.has('co'))
        self.assertFalse(new.has('pm25'))
        self.assertFalse(new.has('pm10'))

        # Make some data
        new.fakedata(n=100, direction='backward')

        # Test _plotly
        pltly = new._plotly(private=False)

        self.assertEqual(pltly['meta']['keys'], TREX.public_keys)
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Test _plotly
        pltly = new._plotly(researcher=True)

        self.assertEqual(pltly['meta']['keys'], TREX.private_keys)
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Add specific checks for labels and shit

    def test_instrument_mit(self):
        data = {
            'sn': 'MITXYZ',
            'ip': '100.1.2.4',
            'city': 'Delhi',
            'country': 'IN',
            'location': 'CP',
            'model': 'MIT2016'
        }

        new = MIT.create(data)

        db.session.add(new)
        db.session.commit()

        # Test the class
        self.assertIsInstance(new, MIT)
        self.assertIsInstance(new, Instrument)
        self.assertEqual(new.sn, data['sn'])
        self.assertEqual(new.ip, data['ip'])
        self.assertEqual(new.city, data['city'])
        self.assertEqual(new.country, data['country'])
        self.assertEqual(new.model, data['model'])
        self.assertEquals(new.results.count(), 0)

        # Update the country
        new.from_dict({'country': 'US'}, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.country, 'US')

        self.assertTrue(new.has('so2'))
        self.assertFalse(new.has('h2s'))
        self.assertTrue(new.has('o3'))
        self.assertTrue(new.has('co'))
        self.assertTrue(new.has('pm25'))
        self.assertTrue(new.has('pm10'))

        # Make some data
        new.fakedata(n=100, direction='backward')

        # Test _plotly
        pltly = new._plotly(researcher=False)

        self.assertEqual(pltly['meta']['keys'], MIT.public_keys)
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Test _plotly
        pltly = new._plotly(researcher=True)

        self.assertEqual(pltly['meta']['keys'], MIT.private_keys)
        self.assertGreaterEqual(len(pltly['data']), 0)

        # Add specific checks for labels and shit

    def test_instrument_trexpm(self):
        data = {
            'sn': 'TREXPM1',
            'city': 'Delhi',
            'country': 'IN',
            'location': 'CP',
            'model': 'TREXPM'
        }

        new = TrexPM.create(data)

        db.session.add(new)
        db.session.commit()

        # Test the class
        self.assertIsInstance(new, TrexPM)
        self.assertIsInstance(new, Instrument)
        self.assertEqual(new.sn, data['sn'])
        self.assertEqual(new.city, data['city'])
        self.assertEqual(new.country, data['country'])
        self.assertEqual(new.model, data['model'])
        #self.assertEquals(new.results.count(), 0)

        # Update the country

        new.from_dict({'country': 'US'}, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.country, 'US')

        # Make some data
        new.fakedata(n=100, direction='backward')

        # Test _plotly
        pltly = new._plotly(researcher=False)

        self.assertGreaterEqual(len(pltly['data']), 0)

        # Test _plotly
        pltly = new._plotly(researcher=True)

        # Test data cascading
        n_points = new.results.count()
        self.assertGreater(n_points, 0)

        # Drop one datapoint
        last = new.results.first()
        self.assertTrue(last.drop())
        self.assertLess(new.results.count(), n_points)

        # Drop the instrument and then see how many data points are left
        self.assertTrue(new.drop())
        self.assertEqual(TrexPMData.query.filter_by(instr_sn=data['sn']).count(), 0)

    def test_aws_model(self):
        i = Instrument.query.first()

        # Create a new AWS entry
        new = AWS(bucket_name='TESTBUCKET', key='testing.csv', device_id=i.id)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.bucket_name, 'TESTBUCKET')
        self.assertEqual(new.downloads, 0)

        new.increment()

        self.assertEqual(new.downloads, 1)

        # Test url generation
        s3_client = boto3.client('s3')
        self.assertTrue(new.presigned_url(s3_client=s3_client))

        # Test a drop
        new3 = AWS(bucket_name='TESTBUCKET', key='testing-new.csv', device_id=i.id)

        db.session.add(new3)
        db.session.commit()

        # Test drop
        self.assertTrue(new3.drop())

        # Force unique constraint error
        with self.assertRaises(IntegrityError):
            fail = AWS(bucket_name='TESTBUCKET', key='testing.csv', device_id=i.id)
            fail2 = AWS(bucket_name='TESTBUCKET', key='testing.csv', device_id=i.id)

            db.session.add(fail)
            db.session.add(fail2)
            db.session.commit()

    def test_credentials(self):
        # get credentials of user
        role_user = Role.query.filter_by(name='User').first()
        role_admin = Role.query.filter_by(name='Administrator').first()

        u1 = User.query.filter_by(role=role_user).first()
        u2 = User.query.filter_by(role=role_admin).first()
        n = Instrument.query.first()

        # Make sure canwrite works for admin and node
        self.assertFalse(u1.credentials.first().can_write)
        self.assertTrue(u2.credentials.first().can_write)
        self.assertTrue(n.credentials.can_write)

        # Check the scopes
        self.assertTrue(u1.credentials.first().get_scope() == ['READ'])
        self.assertTrue(u2.credentials.first().get_scope() == ['READ', 'WRITE'])
        self.assertTrue(n.credentials.get_scope() == ['READ', 'WRITE'])

        # Test drop
        c = Credentials()

        db.session.add(c)
        db.session.commit()

        self.assertTrue(c.drop())

    def test_instrument_create_log(self):
        i = EBAM.query.first()

        res = i.log_event(message='EBAM Failure', level='CRITICAL')

        self.assertTrue(res)

        # Get the log
        log = i.logs.all()[-1]

        self.assertEqual(log.message, "EBAM Failure")
        self.assertEqual(log.level, 'CRITICAL')
        self.assertTrue(log.device is i)
        self.assertIsNone(log.closed)
        self.assertFalse(log.addressed)

        # Test addressing a log
        r = log.close()

        self.assertTrue(r)
        self.assertTrue(log.addressed)
        self.assertIsNotNone(log.closed)

        log.drop()

        self.assertTrue(i.logs.count() == 0)

    def test_instrument_update(self):
        i = Instrument.query.first()

        last = i.last_updated

        i.update()

        db.session.commit()

        self.assertNotEqual(last, i.last_updated)

    def test_orphan_evaluate(self):
        i = Orphan.query.first()

        # Build a model and test it
        m = Model(filename="LR_1VAR.sav", label='LinReg2x')

        db.session.add(m)
        db.session.commit()

        i.ml_model = m

        db.session.add(i)
        db.session.commit()

        # First, test with no model_id
        data = dict(timestamp=datetime.datetime.utcnow(), value=12, parameter='o3', instr_sn=i.sn)

        # Evaluate the algo
        data = i.evaluate(data)

        new = Data.create(data)

        db.session.add(new)
        db.session.commit()

        self.assertIsNotNone(new)

    def test_ebam_evaluate(self):
        i = EBAM.query.first()

        self.assertIsNone(i.ml_model)

        pt = dict(timestamp=datetime.datetime.utcnow(), conc_rt=12, conc_hr=2.1, instr_sn=i.sn)

        data = i.evaluate(pt)    # returns new dict

        new_pt = EBamData.create(data)

        db.session.add(new_pt)
        db.session.commit()

        self.assertIsNotNone(new_pt)
        self.assertEqual(pt['conc_rt'], new_pt.conc_rt)

    def test_trex_evaluate(self):
        i = TREX.query.first()

        self.assertIsNone(i.so2_model)

        m = Model(filename="trex001_hybrid_20171214202354.sav", label='trex001-hybrid-model')

        db.session.add(m)
        db.session.commit()

        i.so2_model = m

        db.session.add(i)
        db.session.commit()

        self.assertIsNotNone(m.load_from_file())

        pt = dict(
                timestamp=datetime.datetime.utcnow(),
                instr_sn=i.sn,
                so2_we=431,
                so2_ae=334,
                temp=23.1,
                rh=45.3)

        new = i.evaluate(pt)

        new_pt = TrexData.create(new)

        db.session.add(new_pt)
        db.session.commit()

        new = TrexData.query.filter_by(instr_sn=i.sn).order_by(TrexData.timestamp.desc()).first()

        self.assertIsNotNone(new_pt)
        self.assertEqual(new_pt.model_id, m.id)
        self.assertEqual(new_pt.so2_we, pt['so2_we'])
        self.assertEqual(new_pt.so2_ae, pt['so2_ae'])
        self.assertEqual(new_pt.temp, pt['temp'])
        self.assertEqual(new_pt.rh, pt['rh'])
        self.assertIsNotNone(new_pt.so2)

    def test_trexpm_evaluate(self):
        i = TrexPM.query.first()

        self.assertIsNone(i.pm_model)

        self.assertIsNone(i.evaluate(dict()))


    def test_mit_evaluate(self):
        i = MIT.query.first()

        self.assertIsNone(i.so2_model)
        self.assertIsNone(i.ox_model)
        self.assertIsNone(i.nox_model)
        self.assertIsNone(i.co_model)
        self.assertIsNone(i.pm_model)
