from flask import Flask
from flask_socketio import SocketIO
from flask_moment import Moment
from flask_pagedown import PageDown
from flaskext.markdown import Markdown
from flask_sqlalchemy import SQLAlchemy
from config import config
from flask_login import LoginManager
from flask_caching import Cache
from flask_assets import Environment, Bundle
import logging
import datetime
from raven.contrib.flask import Sentry

login_manager 						= LoginManager()
login_manager.session_protection 	= 'strong'
login_manager.login_view 			= 'auth.login'

moment 		= Moment()
db 			= SQLAlchemy()
pagedown 	= PageDown()
cache 		= Cache(config={'CACHE_TYPE': 'simple'})
socketio 	= SocketIO()	# engineio_logger=True for debugging
sentry 		= Sentry()
assets 		= Environment()

def create_app(config_name):
	app = Flask(__name__)
	app.config.from_object(config[config_name])

	config[config_name].init_app(app)

	# register static assets
	js = Bundle(
		'js/jquery-3.3.1.min.js',
		'js/popper.js',
		'js/tether.js',
		'js/moment-with-locales.min.js',
		'js/jquery.tablesorter.min.js',
		'js/tatasockets.js',
		'js/toolkit.min.js',
		filters='jsmin', output='gen/packed.js')

	css = Bundle(
		'css/tata.css',
		'css/toolkit-light.min.css',
		filters='cssmin', output='gen/packed.css')

	assets.register('js_all', js)
	assets.register('css_all', css)

	moment.init_app(app)
	pagedown.init_app(app)
	socketio.init_app(app)
	db.init_app(app)
	login_manager.init_app(app)
	cache.init_app(app)
	assets.init_app(app)
	sentry.init_app(app, logging=True, level=logging.WARNING)

	markdown = Markdown(app)

	# Set up logging
	if not app.debug:
		sentry.init_app(app, logging=True, level=logging.WARNING)

		#app.logger.addHandler(logging.StreamHandler())
		#app.logger.setLevel(logging.DEBUG)
		app.logger.propagate = True

		#logger = logging.getLogger('flask_logger')
	else:
		logging.basicConfig()

	from .main import main as main_blueprint
	from .auth import auth as auth_blueprint
	from .admin import admin as admin_blueprint
	from .api_1_0 import api_1_0 as api_1_0_blueprint

	app.register_blueprint(main_blueprint)
	app.register_blueprint(auth_blueprint, url_prefix='/auth')
	app.register_blueprint(admin_blueprint, url_prefix='/admin')
	app.register_blueprint(api_1_0_blueprint, url_prefix='/api/v1.0')

	return app

if __name__ == "__main__":
	# Might need to change this back to development/production
	app = create_app('development')
