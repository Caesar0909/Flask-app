[![CircleCI](https://circleci.com/gh/tataaq/web-tata.svg?style=svg&circle-token=f2c752aa255a484d405db2059fe2121cefe6003a)](https://circleci.com/gh/tataaq/web-tata)
[![Maintainability](https://api.codeclimate.com/v1/badges/6b4db4fa3ab6a0ffacff/maintainability)](https://codeclimate.com/repos/599987db6c529b026f0022ba/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/6b4db4fa3ab6a0ffacff/test_coverage)](https://codeclimate.com/repos/599987db6c529b026f0022ba/test_coverage)


# web-tata
Website for the Tata air quality project

## The Basics

  * Python v3.5.2
  * MySQL v5.7.22
  * the local and test environments use sqlite for the database
  * the production server uses MySQL
  * the server is running through NGINX using gunicorn with eventlet, spawning 5 workers.
  * everything runs in a virtual environments

#### To restart the server and/or gunicorn, issue the commands ([ref](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-16-04)):

    $ sudo reload tata
    $ sudo systemctl restart nginx

## Config File Locations

| Title | Location | Purpose |
|:-----:|:---------|:--------|
| upstart script | **/etc/init/tata.conf** | to start gunicorn and serve flask on server startup |
| nginx | **/etc/nginx/sites-available/tata** | to tell nginx to pass web requests to a specific socket |

## Log File Locations

| Title | Location | Purpose |
|:-----:|:--------:|:-------:|
| gunicorn_stderr.log | /var/log/gunicorn/ ||

## Useful Tutorials

  * [Serving Nginx/Gunicorn/Flask on DO](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-14-04)


## Virtual Environment

### Activation

    $ source flask/bin/activate

### Deactivation

    $ (flask) deactivate


## Database Management

### Build the Database

    mysql> create database tataaq character set utf8 collate utf8_bin;
    mysql> create user 'apps'@'localhost' indentified by 'tata_secret';
    mysql> grant all privileges on tataaq.* to 'apps'@'localhost';
    mysql> flush privileges;
    mysql> quit;

### Initialization

    (venv) python manage.py db init

### Migrations

     (venv) python manage.py db migrate

### Upgrade/Downgrade

    (venv) python manage.py db upgrade

            -or-

    (venv) python manage.py db downgrade

## Local Server

    $ (venv) python manage.py runserver

## Shell Access

    $ (venv) python manage.py shell



## Testing

Unittests can be found in `/tests`. They are written using python's unittest
framework and coverage reports can be found both locally as well as through  
codeclimate. There are several options available when running tests that are
documented below.

### Unittests

    $ (venv) python manage.py test

Test only a specific subsection

    $ (venv) python manage.py test --pattern='test_api*'

#### With Coverage Statistics and Info.

    $ (venv) python manage.py test --coverage=1

# Fake Data

    $ (venv) python manage.py fakedata

## Config File Locations

  * Gunicorn: `/etc/init/tata.conf`
  * NGINX: `/etc/nginx/sites-available/tata`

# Generating CSV Files

The goal is to use a cronjob to generate daily and monthly logfiles

## Daily logfiles

    (flask) python manage.py gen_csv

## Monthly logfiles

    (flask) python manage.py gen_csv --month

# Helpful Links for Standing up the Server

  * [Automatic Deployment with Git][1]
  *

# Server Configuration

## Process

  1. Push the code from git (eventually replace all of this with Docker)
  2. Stop the server using supervisor (e.g. `sudo supervisorctl stop tata`)
  3. Make database upgrades
  4. Reactivate the server (e.g. `sudo supervisorctl start tata`)


## New Gunicorn Start File via Supervisor

    [program:microblog]
    command=/var/www/tata/tata/flask/bin/gunicorn --worker-class eventlet -w 1 --timeout 300 --bind 127.0.0.1:8000 wsgi:application
    directory=/var/www/tata/tata
    user=apps
    autostart=true
    autorestart=true
    stopasgroup=true
    killasgroup=true

## NGINX Config for Websockets

    server {
        server_name www.tatacenter-airquality.mit.edu;

        listen *:80;

        return 301 http://$host$request_uri;
    }

    server {
        server_name tatacenter-airquality.mit.edu;
        listen *:80;
        listen [::]*:80;

        return 301 https://$host$request_uri;
    }

    upstream socketio_nodes {
        ip_hash;

        server 127.0.0.1:8000;
        # add more nodes here to scale
    }

    server {
        server_name tatacenter-airquality.mit.edu;

        ssl_certificate /etc/apache2/ssl/tatacenter-airquality.chained.crt;
        ssl_certificate_key /etc/apache2/ssl/tatacenter-airquality.mit.edu.key;

        listen *:443 ssl;

        access_log /var/log/nginx/gunicorn-access.log;
        error_log /var/log/nginx/tata/error/log debug;  # can remove debug if needed

        location / {
            proxy_pass http://socketio_nodes;
            proxy_redirect off;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /socket.io {
            proxy_pass http://socketio_nodes/socket.io;
            proxy_http_version 1.1;
            proxy_redirect off;
            proxy_buffering off;

            proxy_connect_timeout 7d;
            proxy_read_timeout 7d;
            proxy_send_timeout 7d;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        location ^~/static/ {
            root /var/www/tata/tata/app/;
        }

        location =/favicon.ico {
            root /var/www/tata/tata/app/static/img/favicon.ico;
        }

    }

[1]: https://www.digitalocean.com/community/tutorials/how-to-set-up-automatic-deployment-with-git-with-a-vps
