import unittest
from app.models import *
from app import create_app, db
from helpers import prepare_db
from app import assets

class UserModelTestCase(unittest.TestCase):
    def setUp(self):
        assets._named_bundles = {}
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        try:
            prepare_db()
        except:
            pass

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_setter(self):
        u = User(password='cat', username='catsss', email='cats@puppiesarebetter.com')
        self.assertTrue(u._password_hash is not None)

    def test_no_password_getter(self):
        u = User(password='cat', username='catsss', email='cats@puppiesarebetter.com')
        with self.assertRaises(AttributeError):
            u.password

    def test_password_verification(self):
        u = User(password='cat', username='catsss', email='cats@puppiesarebetter.com')
        self.assertTrue(u.verify_password('cat'))
        self.assertFalse(u.verify_password('dog'))

    def test_password_salts_are_random(self):
        u = User.query.get(1)
        u2 = User.query.get(2)
        self.assertTrue(u._password_hash != u2._password_hash)

    def test_email_exists(self):
        u = User.query.first()

        self.assertTrue(u.email is not None)

    def test_user_priveleges(self):
        role = Role.query.filter_by(name='User').first()
        user = User.query.filter_by(role=role).first()

        # a user should be able to follow and API_READ
        self.assertTrue(user.can(Permission.FOLLOW))
        self.assertTrue(user.can(Permission.API_READ))

        self.assertFalse(user.can(Permission.API_WRITE))
        self.assertFalse(user.can(Permission.ADMINISTER))
        self.assertFalse(user.can(Permission.DELETE))
        self.assertFalse(user.can(Permission.VIEW_RESEARCH_DATA))

        self.assertFalse(user.can_manage)
        self.assertFalse(user.can_delete)
        self.assertFalse(user.can_view_research_data)

    def test_manager_priveleges(self):
        role = Role.query.filter_by(name='Manager').first()
        user = User.query.filter_by(role=role).first()

        # a user should be able to follow and API_READ
        self.assertTrue(user.can(Permission.FOLLOW))
        self.assertTrue(user.can(Permission.API_READ))
        self.assertTrue(user.can(Permission.ADMINISTER))
        self.assertTrue(user.can(Permission.VIEW_RESEARCH_DATA))
        self.assertTrue(user.can(Permission.API_WRITE))

        self.assertFalse(user.can(Permission.DELETE))

        self.assertTrue(user.can_manage)
        self.assertTrue(user.can_view_research_data)
        self.assertFalse(user.can_delete)

    def test_administrator_priveleges(self):
        role = Role.query.filter_by(name='Administrator').first()
        user = User.query.filter_by(role=role).first()

        # a user should be able to follow and API_READ
        self.assertTrue(user.can(Permission.FOLLOW))
        self.assertTrue(user.can(Permission.API_READ))
        self.assertTrue(user.can(Permission.API_WRITE))
        self.assertTrue(user.can(Permission.ADMINISTER))
        self.assertTrue(user.can(Permission.DELETE))
        self.assertTrue(user.can(Permission.VIEW_RESEARCH_DATA))

        self.assertTrue(user.can_manage)
        self.assertTrue(user.can_delete)
        self.assertTrue(user.can_view_research_data)

    def test_researcher_priveleges(self):
        role = Role.query.filter_by(name='Researcher').first()
        user = User.query.filter_by(role=role).first()

        self.assertTrue(user.can(Permission.VIEW_RESEARCH_DATA))
        self.assertTrue(user.can_view_research_data)
        self.assertFalse(user.can_manage)
        self.assertFalse(user.can_delete)

    def test_ping(self):
        a = User.query.first().last_seen

        User.query.first().ping()
        self.assertTrue(a != User.query.first().last_seen)

    def test_confirmation_token(self):
        u = User.query.first()

        token = u.generate_confirmation_token()
        tokenb = User.query.get(2).generate_confirmation_token()

        self.assertTrue(u.confirm(token))
        self.assertFalse(u.confirm('a1234'))
        self.assertFalse(u.confirm(tokenb))

    def test_credentials(self):
        u = User.query.get(3)

        self.assertIsNone(u.api_token)
        self.assertTrue(u.set_credentials())
        self.assertTrue(u.credentials.first().can_write)

        # Add a credential and drop it
        c = Credentials()

        db.session.add(c)
        db.session.commit()

        self.assertFalse(c.can_write)
        self.assertTrue(c.drop())

    def test_drop(self):
        u = User.query.filter_by(username='drop').first()

        self.assertTrue(u.drop())

    def test_anon_user(self):
        u = AnonymousUser()

        self.assertFalse(u.is_administrator())
        self.assertFalse(u.can(Permission.ADMINISTER))

    def test_user_grouped_devices(self):
        u = User.query.first()
        g = Group.query.first()
        d = Instrument.query.first()

        # Add the user to a group
        u.joingroup(g)

        # Add the device to the group
        d.joingroup(g)

        # Make sure the user has available devices
        self.assertTrue(u.canview(d))

        # Add another device to the group
        d = Instrument.query.all()

    def test_following_user(self):
        u = User.query.get(2)
        g = Group.query.get(2)

        # Get the number of devices the user in groups
        self.assertEqual(u.groups.count(), 1)
        self.assertEqual(g.devices.count(), 1)

        self.assertGreaterEqual(u.following.count(), 1)

    def test_can_view_private_devices(self):
        r_admin = Role.query.filter_by(name='Administrator').first()
        r_user = Role.query.filter_by(name='User').first()
        r_researcher = Role.query.filter_by(name='Researcher').first()

        admin = User.query.filter_by(role=r_admin).first()
        user = User.query.filter_by(role=r_user).first()
        researcher = User.query.filter_by(role=r_researcher).first()

        i = Instrument.query.first()

        # Admins should be able to view all devices
        self.assertTrue(admin.canview(i))

        # Get the first device of the user
        d1 = user.devices.first()

        if d1 is None:
            d1 = Orphan(sn='adasdasda', user_id=user.id)

            db.session.add(d1)
            db.session.commit()

        self.assertTrue(user.canview(d1))
        self.assertTrue(admin.canview(d1))
        self.assertFalse(user.can_view_research_data)
