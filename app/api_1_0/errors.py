from flask import jsonify, make_response
from . import api_1_0
from app.exceptions import ValidationError
from sqlalchemy.exc import IntegrityError, InvalidRequestError

def bad_request(message):
	response = jsonify({'error': 'bad request', 'message': message})
	response.status_code = 400
	return response

def unauthorized(message):
	response = jsonify({'error': 'unauthorized', 'message': message})
	response.status_code = 401
	return response

def forbidden(message):
	response = jsonify({'error': 'forbidden', 'message': message})
	response.status_code = 403
	return response

@api_1_0.errorhandler(ValidationError)
def validation_error(e):
	return bad_request(e.args[0])

@api_1_0.errorhandler(IntegrityError)
def integrity_error(e):
	return bad_request(e.args[0])

@api_1_0.errorhandler(InvalidRequestError)
def request_error(e):
	return make_response(jsonify({'InvalidRequestError': 'Not Found'}), 403)

@api_1_0.app_errorhandler(404)
def not_found_error(e):
	return make_response(jsonify({'Error 404': 'Not Found'}), 404)

@api_1_0.app_errorhandler(409)
def resource_exists_error(e):
	return make_response(jsonify({'Error 409': 'Resource Exists'}), 409)

@api_1_0.app_errorhandler(405)
def server_error(e):
	return make_response(jsonify({'Error 405': 'Method not allowed'}), 405)

@api_1_0.app_errorhandler(400)
def bad_request_error(e):
	return make_response(jsonify({'Error 400': 'Bad Request'}), 400)

@api_1_0.app_errorhandler(409)
def bad_request_error(e):
	return make_response(jsonify({'Error 409': 'Invalid Device'}), 409)
