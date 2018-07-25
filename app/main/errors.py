from flask import render_template, jsonify, request, g

from . import main
from .. import sentry

@main.errorhandler(404)
def page_not_found(e):
	sentry.captureException()
	return render_template('404.html'), 404

@main.errorhandler(403)
def http_error(e):
	sentry.captureException()
	return render_template('403.html'), 403

@main.errorhandler(401)
def http_error2(e):
	sentry.captureException()
	return render_template('401.html'), 401

@main.errorhandler(500)
def internal_server_error(e):
	sentry.captureException()
	return render_template('500.html',
				event_id=g.sentry_event_id,
				public_dsn=sentry.client.get_public_dsn('https')), 500
