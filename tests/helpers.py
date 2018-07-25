from flask import current_app
from app import db
from app.models import *
import datetime
import random

def prepare_db():
    Role.insert_roles()

    manager = Role.query.filter_by(name='Manager').first()
    researcher = Role.query.filter_by(name='Researcher').first()
    admin = Role.query.filter_by(name='Administrator').first()

    # Add a few users
    u0 = User(email='david@david.com', username='david', password='password') # admin
    u1 = User(email='user@test.com', username='test_user', password='password')
    u2 = User(email='admin@test.com', username='test_admin', password='password', role=admin)
    u3 = User(email='drop@me.com', username='dropp', password='password', role=manager)
    u4 = User(email='researcher@test.com', username='research_test',
                password='password!', role=researcher)
    u5 = User(email='user2@test.com', username='test_user2', password='password')

    g = Group('Public')
    g2 = Group('MIT')

    # Confirm these folks
    u1.confirmed = True
    u2.confirmed = True
    u4.confirmed = True
    u5.confirmed = True

    db.session.add_all([u0, u1, u2, u3, u4, u5, g, g2])
    db.session.commit()

    u0.set_credentials()
    u1.set_credentials()
    u4.set_credentials()
    u5.set_credentials()

    # Add u2 to the public group
    u0.joingroup(g)
    u1.joingroup(g2)
    u2.joingroup(g)
    u2.joingroup(g2)
    u4.joingroup(g2)
    u5.joingroup(g2)

    db.session.add_all([u0, u2, u4, u5])
    db.session.commit()

    # E-BAM as it is in the system now!
    i0 = EBAM.create(dict(sn='EBAM001', location='Connaught Place', city='Delhi',
                country='IN', timezone='Asia/Kolkata', outdoors='True',
                model='E-BAM', private=True))

    # O3 Monitor as in the system now!
    i1 = Orphan.create(dict(sn='OZONE001', location='Connaught Place', city='Delhi',
                country='IN', timezone='Asia/Kolkata', outdoors='True',
                model='2BTech 202', particle_id='123456789', private=False))

    # Add an EBAM instrument
    i2 = EBAM.create(dict(sn='EBAM002', location='Connaught Place', city='Delhi',
            country='IN', timezone='Asia/Kolkata', outdoors=True, model='E-BAM',
            private=False))

    i3 = MIT.create(dict(sn='MIT001', location='CP',
                city='Delhi', country='IN', private=False, particle_id='asdasda'))

    i4 = TREX.create(dict(sn='1231324134123123123', particle_id='123180231b3n1kjb321k231',
            location='Valcano National Park', city='Valcano Village',
            country='US', private=False))

    i5 = TrexPM.create(dict(sn='TREXPM001', location='Hilo DOH', city='Hilo',
                    country='US', timezone='US/Hawaii', private=False, particle_id='a123456789'))

    i0.owner = u0
    i3.owner = u1
    i2.owner = u4
    i5.owner = u4

    i1.joingroup(g)
    i3.joingroup(g2)

    db.session.add_all([i0, i1, i2, i3, i4, i5])
    db.session.commit()

    # Set the credentials for the instrument
    i0.set_credentials()
    i1.set_credentials()
    i2.set_credentials()
    i3.set_credentials()
    i4.set_credentials()
    i5.set_credentials()

    i0.fakedata(n=10)
    i1.fakedata(n=10)
    i2.fakedata(n=10)
    i3.fakedata(n=10)
    i4.fakedata(n=10)
    i5.fakedata(n=10)


def instrument_data(json=False):
    ''' Return random instrument! '''
    sn = 'INSTR' + random.randint(0, 1000)

def fake_log(instr, n=1):
    for i in range(n):
        event = Log(
            level=random.choice(['INFO', 'WARN', 'CRITICAL']),
            message='test logging',
            instr_sn=instr.sn
            )

        db.session.add(event)
    db.session.commit()

    return
