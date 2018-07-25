import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
	SECRET_KEY = os.environ.get('SECRET_KEY') or 'tata-2015-super-secret'
	SQLALCHEMY_COMMIT_ON_TEARDOWN = True
	CSRF_ENABLED = True
	ADMINS = ['david@david.com']
	USERNAME = 'apps'
	PASSWORD = 'tata_secret'
	DATA_POINTS_PER_PAGE = 100
	MAX_PER_PAGE = 10000
	SQLALCHEMY_RECORD_QUERIES = True
	SQLALCHEMY_TRACK_MODIFICATIONS = False
	SLOW_DB_QUERY_TIME = 0.25
	SENDGRID_API_KEY = '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'
	FROM_EMAIL = 'dhagan@mit.edu'
	FROM_NAME = 'Tata Center Air Quality Project'

	BOTO3_ACCESS_KEY 	= 'AKIAJ2ZG7ESMBNGAQB4Q'
	BOTO3_SECRET_KEY 	= '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'
	BOTO3_REGION 		= 'us-west-2'
	BOTO3_SERVICES 	 	= ['s3']
	AWS_BUCKET 			= 'tataaqdev'

	FBOOK_PAGE_ACCESS_TOKEN = 'EAAFvjJ75Ba0BANpZCMrKT2Tr2IYTPk8ay0nd4WA4gaRhsRSQ8o9AkwycAJUKdA8V4r7p9QOLZCYwDIhNZCZBO9ZCVzz32EuxESxECu7ZA7A3gzd11opOJmgE6HB3a9ZBC4vVU8BIc7gXyS9f3nsl56Fnp4ONZBfU77hc4kuwbU5WUwZDZD'
	FBOOK_CONFIG_TOKEN = '95cc63bda67c462f8b8a3023a3d3a371'

	SENTRY_DSN = ''

	TMP_DIR = 'temp_files'
	MODELS_DIR = 'ml_models'

	ALLOWED_EXTENSIONS	= ['csv', 'txt', 'png', 'jpg', 'jpeg', 'md', 'dat', 'pkl', 'sav']

	ALLOWED_POLLUTANTS = ['so2', 'h2s', 'pm25', 'pm10']
	MAX_AGE_ON_MAP_HRS = 12

	EMAILS = True

	@staticmethod
	def init_app(app):
		pass

class DevelopmentConfig(Config):
	DEBUG = True
	SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
	SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'mysql://apps:tata_secret@localhost/tataaq'
	API_KEY = ''

	MAX_AGE_ON_MAP_HRS = 12000

class TestingConfig(Config):
	TESTING = True
	DEBUG = False
	WTF_CSRF_ENABLED = False
	CSRF_ENABLED = False
	PRESERVE_CONTEXT_ON_EXCEPTION = False
	#LOGIN_DISABLED = False
	SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'test.db')

	AWS_BUCKET = 'tataaqtest'
	EMAILS = False

class ProductionConfig(Config):
	DEBUG = False
	WTF_CSRF_ENABLED = True
	SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
	SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://apps:tata_secret@localhost:3306/tata'
	API_KEY = ''

	AWS_BUCKET = 'tataaq'

	SENTRY_DSN = 'https://c7d42825fafe4d3593ec9b7518274bf3:ae40fabbbf1e45b7a250d0ca0dfe6f6b@sentry.io/206207'

config = {
	'development': DevelopmentConfig,
	'testing': TestingConfig,
	'production': ProductionConfig,
	'default': DevelopmentConfig
	}
