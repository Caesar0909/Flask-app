import logging
import logging.config

from app import create_app

application = create_app('production')
application.secret_key = 'super secret key 3000'

if __name__ == '__main__':
    application.run()
