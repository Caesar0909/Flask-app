
### HTTP Status Codes

Along with the HTTP methods that the API responds to, it will also return
standard HTTP statuses, including error codes when necessary.

If there is an issue with the request, an error will be returned as indicated
both by the HTTP status code and the response body. In general, if the status
code is in the 200's, the request was successful. If the status code is in the
400's, there was an error with the request. This could range from improper
authentication to an illegal operation (you were trying to request data you do
    not have permissions to view!).

If a 500 error is returned, there was a server-side error which means we were
not able to process the request for some reason.


An example error response:

    HTTP/1.1 403 Forbidden

    {
        "id": "forbidden",
        "message": "You do not have access for the attempted action"
    }
