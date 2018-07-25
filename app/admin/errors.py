from flask import render_template, jsonify, request

from . import admin
from .. import sentry

@admin.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@admin.errorhandler(403)
def http_error(e):
    sentry.captureException()
    return render_template('403.html'), 403
