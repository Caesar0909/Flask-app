class ValidationError(ValueError):
	pass

class IntegrityError(Exception):
	pass

class AlreadyExistsError(Exception):
	pass

class EmptyDataFrameException(Exception):
	pass

class S3Exception(Exception):
	pass
