import unittest
from app.models import *
from app import create_app, db
import sqlite3
import datetime
import random
import re
from helpers import prepare_db
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

    def test_create_model(self):
        fname = "/test/models/model.pkl"

        m = Model(filename=fname)

        m.rmse = 12.1
        m.mae = 7.5
        m.r2 = 0.98

        db.session.add(m)
        db.session.commit()

        self.assertIsNotNone(m.created)
        self.assertIsNotNone(m.last_updated)
        self.assertEqual(m.filename, fname)
        self.assertEqual(m.rmse, 12.1)
        self.assertEqual(m.mae, 7.5)
        self.assertEqual(m.r2, 0.98)

    def test_model_cascading(self):
        fname = "/test/models/model.pkl"

        m = Model(filename=fname)

        db.session.add(m)
        db.session.commit()

        model_id = m.id

        i = MIT.query.first()

        i.so2_model = m

        db.session.add(i)
        db.session.commit()

        self.assertEqual(i.so2_model, m)

        # Drop the Model
        m.drop()

        # Expected Behaviour: After deleting a model, there should be no reference to it
        # in the database (no linked records in Data or Instrument models)

        self.assertIsNone(Model.query.get(model_id))
        self.assertIsNone(i.so2_model)

    def test_model_history(self):
        # Make sure old models stick around since they're connected to Data Points and whatnot
        fname1 = "/test/models/model1.pkl"
        fname2 = "/test/models/model2.pkl"

        i = MIT.query.first()

        m = Model(filename=fname1, instr_id=i.id)

        db.session.add(m)
        db.session.commit()

        # Get the model's ID
        model_id = m.id

        # Assign the model to the instrument
        i.so2_model = m

        db.session.add(i)
        db.session.commit()

        self.assertEqual(i.so2_model, m)
        self.assertEqual(m.instr_id, i.id)

        # Add the second model
        m2 = Model(filename=fname2, instr_id=i.id)

        db.session.add(m2)
        db.session.commit()

        i.so2_model = m2

        db.session.add(i)
        db.session.commit()

        self.assertEqual(i.so2_model, m2)
        self.assertEqual(m.instr_id, i.id)
        self.assertEqual(m2.parent, i)

        # Get all models with the SN of i
        ms = Model.query.filter_by(instr_id=i.id)

        self.assertEqual(ms.count(), 2)

    def test_mit_model_compat(self):
        i = MIT.query.first()

        m1 = Model(filename="/test/models/model1.pkl", instr_id=i.id)
        m2 = Model(filename="/test/models/model2.pkl", instr_id=i.id)
        m3 = Model(filename="/test/models/model3.pkl", instr_id=i.id)
        m4 = Model(filename="/test/models/model4.pkl", instr_id=i.id)

        db.session.add_all([m1, m2, m3, m4])
        db.session.commit()

        # Assign the model to the instrument
        i.so2_model = m1
        i.co_model = m2
        i.ox_model = m3
        i.nox_model = m4

        db.session.add(i)
        db.session.commit()

        self.assertEqual(i.so2_model, m1)
        self.assertEqual(i.co_model, m2)
        self.assertEqual(i.ox_model, m3)
        self.assertEqual(i.nox_model, m4)

    def test_trex_model_compat(self):
        i = TREX.query.first()

        m = Model(filename='test.pkl', instr_id=i.id)

        db.session.add(m)
        db.session.commit()

        i.so2_model = m

        db.session.add(i)
        db.session.commit()

        self.assertEqual(i.so2_model, m)
        self.assertEqual(m.parent, i)

    def test_load_ml_models_joblib(self):
        from sklearn.externals import joblib
        import os
        import pickle

        basedir = os.path.join(os.getcwd(), "tests/dummy_models")

        # Test the LR models
        m = joblib.load(os.path.join(basedir, "lr36.sav"))

        self.assertTrue(hasattr(m, "predict"))

        # Test the kNN models
        #with open(os.path.join(basedir, "knn36.sav"), 'rb') as f:
        #    m = pickle.load(f)

        m = joblib.load(os.path.join(basedir, "knn36.sav"))

        self.assertTrue(hasattr(m, "predict"))

        # Test the Hybrid Model
        m = joblib.load(os.path.join(basedir, "trex001_hybrid_20171214202354.sav"))

        self.assertTrue(hasattr(m, "predict"))
        self.assertTrue(hasattr(m, "prepare"))
        self.assertTrue(hasattr(m, "fit"))

    def test_data_link(self):
        # We should be able to evaluate a data point, and then know which model
        # was used to evaluate that datapoint and potentially also which datapoints
        # were evaluated given a specific model?

        # 1) Get an Instrument
        i = Orphan.query.first()

        # 2) Make sure the instrument has a model
        if i.ml_model is None:
            fname = "/test/models/model.pkl"

            m = Model(filename=fname)

            m.rmse = 12.1
            m.mae = 7.5
            m.r2 = 0.98

            db.session.add(m)
            db.session.commit()

            i.ml_model = m

            db.session.add(i)
            db.session.commit()

        # Add the model to the instrument
        self.assertIsNotNone(i.ml_model)

        # 3) Create a datapoint for the instrument and attach a model_id to it
        m = i.ml_model

        d = Data.create(
                dict(timestamp=datetime.datetime.utcnow(), value=12.3, parameter='o3',
                        unit='ppbv', flag=1, instr_sn=i.sn, model_id=m.id))

        db.session.add(d)
        db.session.commit()

        data_id = d.id

        # 4) Make sure the datapoint.model_id returns the model
        self.assertIsNotNone(m.id)
        self.assertEqual(d.model_id, m.id)

        # 5) If we delete/update the model, make sure the datapoint doesn't get screwed up
        db.session.delete(m)
        db.session.commit()

        q = Model.query.filter_by(filename=fname).first()
        d = Data.query.get(data_id)

        self.assertIsNone(q)

    def test_trex_data_link(self):
        i = TREX.query.first()

        if i.so2_model is None:
            fname = "/test/models/model.pkl"

            m = Model(filename=fname)

            m.rmse = 12.1
            m.mae = 7.5
            m.r2 = 0.98

            db.session.add(m)
            db.session.commit()

            i.so2_model = m

            db.session.add(i)
            db.session.commit()

        # Make sure the model is there
        self.assertIsNotNone(i.so2_model)

        # Set the model to belong to the insturment
        m = i.so2_model

        # Create a new datapoint
        data = dict(timestamp=datetime.datetime.utcnow(), so2=12, so2_we=456, so2_ae=345,
                    temp=23.4, rh=56.7, flag=7, instr_sn=i.sn, model_id=m.id)

        d = TrexData.create(data)

        db.session.add(d)
        db.session.commit()

        data_id = d.id

        # Make sure the datapoint model returns the model
        self.assertIsNotNone(m.id)
        self.assertEqual(d.model_id, m.id)

    def test_mit_data_link(self):
        i = MIT.query.first()

        # Get a datapoints for the sensor
        d = i.results.first()

        self.assertIsNotNone(d)

        # Make sure there are currently no models associated with the datapoint
        self.assertIsNone(d.co_model_id)
        self.assertIsNone(d.nox_model_id)
        self.assertIsNone(d.so2_model_id)
        self.assertIsNone(d.ox_model_id)
        self.assertIsNone(d.pm_model_id)

        # Add models for each of these and attach them to the device
        m_so2 = Model(filename="/test/models/model_so2.pkl", rmse=12, mae=3.4, r2=.996)
        m_co  = Model(filename="/test/models/model_co.pkl", rmse=12, mae=3.4, r2=.996)
        m_nox = Model(filename="/test/models/model_nox.pkl", rmse=12, mae=3.4, r2=.996)
        m_ox  = Model(filename="/test/models/model_ox.pkl", rmse=12, mae=3.4, r2=.996)
        m_pm  = Model(filename="/test/models/model_pm.pkl", rmse=12, mae=3.4, r2=.996)

        db.session.add_all([m_so2, m_co, m_nox, m_ox, m_pm])
        db.session.commit()

        i.so2_model = m_so2
        i.co_model = m_co
        i.nox_model = m_nox
        i.ox_model = m_ox
        i.pm_model = m_pm

        db.session.add(i)
        db.session.commit()

        # Create a datapoint
        data = {
            'timestamp': datetime.datetime.utcnow(),
            'instr_sn': i.sn,
            'co_we': 345, 'co_ae': 334, 'co': 12.1,
            'ox_we': 345, 'ox_ae': 334, 'o3': 12.1,
            'so2_we': 345, 'so2_ae': 334, 'so2': 12.1,
            'nox_we': 345, 'nox_ae': 334, 'nox': 12.1,
            'pm1': 12, 'pm25': 25, 'pm10': 100,
            'flag': 7,
            'co_model_id': m_co.id, 'nox_model_id': m_nox.id,
            'so2_model_id': m_so2.id, 'ox_model_id': m_ox.id,
            'pm_model_id': m_pm.id}

        d = MITData.create(data)

        db.session.add(d)
        db.session.commit()

        # Now, make sure everything works!
        self.assertIsNotNone(i.so2_model)

        self.assertIsNotNone(m_so2.id)
        self.assertEqual(d.so2_model_id, m_so2.id)
        self.assertEqual(m_co, d.co_model)

    def test_ebam_data_link(self):
        pass
