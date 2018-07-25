
### auth/

**Available methods: [ GET ]**

The authentication endpoint will return the status of the authentication
credentials you provided. If your credentials are good, a 200 response will be
returned. If they fail, a 401 response will be returned. If you are trying to
access a URI for which you do not have permission, a 403 response will be returned.

##### Sample Response

    $ http -a [api-key]: GET https://tatacenter-airquality.mit.edu/api/v1.0/auth/

    HTTP/1.1 200 OK

    {
        "Authentication Check": "All good!"
    }
