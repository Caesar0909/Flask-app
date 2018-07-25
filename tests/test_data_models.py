import unittest
from app.models import *
from app import create_app, db
import sqlite3
import datetime
import random
from helpers import prepare_db
from sqlalchemy.exc import IntegrityError
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

    def test_base_data_model(self):
        # create a data point
        i = Orphan.query.first()

        data = dict(timestamp=datetime.datetime.utcnow(), instr_sn=i.sn, value=1., parameter='o3')

        new = Data.create(data)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.value, 1.)
        self.assertIsNotNone(new.timestamp)

        # Update a datapoint
        additional_data = dict(flag=1, unit='ppb')
        new.from_dict(additional_data, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.flag, 1)
        self.assertEqual(new.unit, 'ppb')

        # Test to_json
        js = new.to_json()

        param = data['parameter']

        self.assertEqual(js[param]['value'], 1.)
        self.assertIsNotNone(js['instrument'])

        # Test url
        url = new.get_url()

        self.assertIsNotNone(url)

        # Test update parent
        last_updated = i.last_updated

        new.update_parent()

        self.assertNotEqual(last_updated, i.last_updated)

    def test_mitdata_model(self):
        i = MIT.query.first()

        data = dict(timestamp=datetime.datetime.utcnow(), instr_sn=i.sn,
                    co_we=1., co_ae=.3)

        new = MITData.create(data)

        db.session.add(new)
        db.session.commit()

        self.assertIsNotNone(new.timestamp)
        self.assertEqual(new.co_we, 1.)

        # Update the datapoint
        updated_data = dict(so2_we=1., so2_ae=.3)

        new.from_dict(updated_data, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertEqual(new.so2_we, 1.)

        with self.assertRaises(KeyError):
            data = dict(instr_sn=i.sn)

            new = MITData.create(data)

        # Test from_webhook
        data = "2017-08-15T13:16:00Z,10,0,45.0,37.9,0.8,39.0,8549.5,9178.8,453.6,354.6,13.9,13.1,45.6,18.3,15.4,9.3,4.2,4.1,3.0,1.3,0.4,0.2,0.0,0.0,0.0,0.0,0.0,0.0,42.75,71.50,108.74,1.99,7.9,10.1,10.6,7.7,3.13,10"

        result = MITData.from_webhook(data, sn=i.sn)

        self.assertEqual(result['instr_sn'], i.sn)

        new = MITData.create(MITData.from_webhook(data, sn=i.sn))

        db.session.add(new)
        db.session.commit()

        self.assertIsNotNone(new.id)

        # Test _plotly
        old_ts = new.to_json()['timestamp']

        i.from_dict(dict(timezone='US/Eastern'), partial_update=True)

        db.session.add(i)
        db.session.commit()

        self.assertIsNotNone(i.timezone)

        pltly = new._plotly()

        #self.assertNotEqual(old_ts, pltly['timestamp'])

        # Test get_url
        url = new.get_url()

        self.assertIsNotNone(url)

        # Test update parent
        last = i.last_updated

        new.update_parent()

        self.assertNotEqual(i.last_updated, last)

        # Drop the datapoint
        self.assertTrue(new.drop())


    def test_ebamdata_model(self):
        i = EBAM.query.first()

        # add a new datapoint
        data = dict(timestamp=datetime.datetime.utcnow(), conc_rt=1., conc_hr=2.,
                    instr_sn=i.sn)

        new = EBamData.create(data)

        db.session.add(new)
        db.session.commit()

        self.assertIsNotNone(new.timestamp)
        self.assertEqual(new.conc_hr, 2.)
        self.assertEqual(new.conc_rt, 1.)

        # Test an update
        updated = dict(rh_i=50.1, rh_interal=65.)

        new.from_dict(updated, partial_update=True)

        db.session.add(new)
        db.session.commit()

        # Test to_json
        js = new.to_json()

        self.assertIsNotNone(js['timestamp'])
        self.assertIsNotNone(new.get_url())

        # Test update parent
        old_ts = i.last_updated

        new.update_parent()

        self.assertNotEqual(old_ts, i.last_updated)

        # Test drop
        self.assertTrue(new.drop())

    def test_trexdata_model(self):
        i = TREX.query.first()

        data = dict(timestamp=datetime.datetime.utcnow(), instr_sn=i.sn,
                    so2_we=1., so2_ae=.3)

        new = TrexData.create(data)

        db.session.add(new)
        db.session.commit()

        self.assertIsNotNone(new)

        # Update the device
        updated = dict(so2=34.5, temp=21.3)

        new.from_dict(updated, partial_update=True)

        db.session.add(new)
        db.session.commit()

        self.assertIsNotNone(new.so2)

        # url
        self.assertIsNotNone(new.get_url())

        # json
        js = new.to_json()

        self.assertIsNotNone(js['timestamp'])

        # plotly
        pt = new._plotly()

        self.assertIsNotNone(pt['Temperature'])

        # drop
        self.assertTrue(new.drop())

    def test_make_group(self):
        g = Group('Trex2017')

        db.session.add(g)
        db.session.commit()

        self.assertTrue(g.name == 'Trex2017')

    def test_membership(self):
        u = User.query.first()
        g = Group.query.first()

        self.assertTrue(g.members)
        self.assertTrue(u.groups)

    def test_join_group(self):
        u = User.query.first()
        g = Group.query.first()

        u.joingroup(g)

        self.assertTrue(g in u.groups)

    def test_leave_group(self):
        u = User.query.first()
        g = Group.query.first()

        u.joingroup(g)
        u.leavegroup(g)

        self.assertTrue(g not in u.groups)

    def test_add_device_to_group(self):
        g = Group.query.first()
        d = Instrument.query.first()

        d.joingroup(g)

        self.assertTrue(d.group is g)
        self.assertTrue(d in g.devices)

        d.leavegroup(g)

        self.assertIsNone(d.group)
        self.assertFalse(d in g.devices)

    def test_create_log(self):
        i = EBAM.query.first()

        log = Log.create(dict(instr_sn=i.sn, message='EBAM Failure', level='CRITICAL'))

        db.session.add(log)
        db.session.commit()

        self.assertEqual(log.instr_sn, i.sn)
        self.assertEqual(log.message, 'EBAM Failure')
        self.assertEqual(log.level, "CRITICAL")

        # Try updating the log
        log.from_dict(dict(level='INFO'), partial_update=True)

        db.session.add(log)
        db.session.commit()

        self.assertEqual(log.level, "INFO")

        # Test addressing a log
        r = log.close()

        self.assertTrue(r)
        self.assertTrue(log.addressed)
        self.assertIsNotNone(log.closed)

        log.drop()

        self.assertTrue(i.logs.count() == 0)

        # Try creating a log with no sn
        with self.assertRaises(Exception):
            log = Log.create(dict(message='bad'))
