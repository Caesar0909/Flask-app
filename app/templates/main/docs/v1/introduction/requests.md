
### Requests

Any tool that is fluent in HTTP can easily communicate with the API
with the correct URI. Requests must be made using HTTPS protocol to ensure the
traffic is encrypted. The response varies depending on the action required.

<table class = 'table'>
    <thead>
        <tr class = 'active'>
            <th>Method</th>
            <th>Usage</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>GET</td>
            <td>
                <p>
                    For simple retrieval of an object or data, you will use a <strong>GET</strong> object. It returns
                    a simple JSON object.
                </p>
                <p>
                    The JSON object can then be used to form additonal requests. Any request made with GET is read-only
                    and will not affect the objects you are querying.
                </p>
         </td>
        </tr>
        <tr>
            <td>DELETE</td>
            <td>
                <p>
                    To destroy a resource and remove it, the <strong>DELETE</strong> method should be used. This will
                    destroy the specified object if it is found. If the resource is not found, the return will indicate so.
                </p>
                <p>
                    <strong>DELETE</strong> requests are idempotent, which means you do not need to check for its existence
                    prior to issuing the DELETE request.
                </p>
            </td>
        </tr>
        <tr>
            <td>PUT</td>
            <td>
                <p>
                    To update a resource, the <strong>PUT</strong> method should be used. Like the DELETE request,
                    the PUT request is idempotent, so checking for current attributes is not required.
                </p>
            </td>
        </tr>
        <tr>
            <td>POST</td>
            <td>
                <p>
                    To create a new object, the <strong>POST</strong> method should be used.
                </p>
                <p>
                    The POST request includes all of the attributes needed to create a new object.
                </p>
            </td>
        </tr>
        <tr>
            <td>HEAD</td>
            <td>
                <p>
                    To retrieve metadata information, issue the <strong>HEAD</strong> method to get the headers.
                </p>
                <p>
                    Response headers contain some useful information about your API access and the results that are
                    available to you.
                </p>
            </td>
        </tr>
    </tbody>
</table>

For more information on HTTP requests, check out [this tutorial][1]. As of August 2017,
only GET requests are allowed by users.


[1]: http://www.tutorialspoint.com/http/http_requests.htm
