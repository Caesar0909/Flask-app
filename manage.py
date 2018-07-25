import eventlet

eventlet.monkey_patch()

import os

COV = None

if os.environ.get('FLASK_COVERAGE'):
	import coverage
	COV = coverage.coverage(branch=True, include='app/*')
	COV.start()

import sys

from app import create_app, db, socketio
from app.models import User, Role, Permission, Group
from flask_script import Manager, Command, Server as _Server, Option, Shell
from flask_migrate import Migrate, MigrateCommand

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)

def make_shell_context():
	return dict(app=app, db=db, User=User, Role=Role, Permission=Permission)


class Server(_Server):
	help = description = "Runs the Socket-IO web server"

	def get_options(self):
		options = (
			Option('-h', '--host',
				dest='host',
				default=self.host),

			Option('-p', '--port',
				dest='port',
				type=int,
				default=self.port),

			Option('-d', '--debug',
				action='store_true',
				dest='use_debugger',
				help='enable the werkzeug debugger',
				default=self.use_debugger),

			Option('-D', '--no-debug',
				action='store_false',
				dest='use_debugger',
				help='disable the werkzeug debugger',
				default=self.use_debugger),

			Option('-r', '--reload',
				action='store_true',
				dest='use_reloader',
				default=self.use_reloader),

			Option('-R', '--no-reload',
				action='store_false',
				dest='use_reloader',
				default=self.use_reloader),
			)
		return options

	def __call__(self, app, host, port, use_debugger, use_reloader):
		# Override the default runserver command to start a SocketIO Server
		if use_debugger is None:
			use_debugger = app.debug

			if use_debugger is None:
				use_debugger = True

		if use_reloader is None:
			use_reloader = app.debug

		socketio.run(app,
					 host=host,
					 port=port,
					 debug=use_debugger,
					 use_reloader=use_reloader,
					 **self.server_options)

manager.add_command("runserver", Server())
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

# sudo python manage.py test --pattern='test_views*'
@manager.command
def test(coverage=1, pattern="*"):
	"""Run the unittests"""
	coverage = bool(int(coverage))

	if coverage and not os.environ.get('FLASK_COVERAGE'):
		import sys
		os.environ['FLASK_COVERAGE'] = '1'
		os.execvp(sys.executable, [sys.executable] + sys.argv)

	import unittest
	tests = unittest.TestLoader().discover('tests', pattern=pattern)
	unittest.TextTestRunner(verbosity=2).run(tests)

	if COV:
		COV.stop()
		COV.save()

		print ("Coverage Summary: ")
		COV.report()

		basedir = os.path.abspath(os.path.dirname(__file__))
		covdir = os.path.join(basedir, 'tmp/coverage')

		COV.html_report(directory=covdir)

		print ("HTML version: file://%s/index.html" % covdir)

		COV.erase()

@manager.command
def deploy():
	"""Build Roles and migrate/upgrade the database(?)
	"""
	print ("Inserting Roles...")

	Role.insert_roles()

	Group.insert_groups()

	print ("Finished!")

	return

@manager.command
def build_database():
	"""Build the development database from scratch or update if necessary
	"""
	from fake_data import setup_initial_database, more_data

	print ("Updating Local Development Database...")

	setup_initial_database()

	print ("Finished!")

	return

@manager.command
def fakedata(n=1000):
	"""Create a fake dataset"""
	from fake_data import more_data

	more_data(n=n)

@manager.command
def backup(prev_month=False, debug=False):
	"""Generate the days CSVs for every instrument"""

	from config import config
	from app.utilities import daily_backup_data_to_s3, monthly_backup_data_to_s3

	def props(obj):
		pr = {}
		for name in dir(obj):
			value = getattr(obj, name)
			if not name.startswith('__'):
				pr[name] = value
		return pr

	if debug:
		fig = props(config['development'])
	else:
		fig = props(config['production'])

	if prev_month:
		monthly_backup_data_to_s3(fig)
	else:
		daily_backup_data_to_s3(fig)

if __name__ == '__main__':
	manager.run()
