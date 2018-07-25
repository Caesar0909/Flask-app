
### device/[sn]/data/

**Available methods: [ GET ]**

The `device/[serial-number]/data/` endpoint allows you to retrieve data for an
existing device (**GET**). Data can be filtered or sorted using the methods described above
in the 'Advanced API Queries section'.

Users can only receive information about devices that are either public or are
within your permissions. If successful, a 200 response will be returned along
with the data.

The response data are paginated and include the following:

  * `flag`: a status flag (anything other than 0 means something was wrong and data is suspect)
  * `instrument`: the url for the parent instrument
  * `timestamp`: the timestamp corresponding to sensor reading in UTC.
  * `timestamp_local`: the timestamp corresponding to sensors local timezone.
  * `parameter`: the pollutant parameter
  * `unit`: the units for the given parameter
  * `value`: the logged value (float)

##### Sample Response

    $ http -a [api-key]: GET https://tatacenter-airquality.mit.edu/api/v1.0/device/OZONE001/data/

    HTTP/1.1 200 OK
    Connection: keep-alive
    Content-Length: 772
    Content-Type: application/json
    Date: Wed, 16 May 2018 02:09:25 GMT
    Etag: "f477b7dc34e5c631c9ca1a9fa136bd47"
    Server: nginx/1.10.3 (Ubuntu)

    {
        "city": "Delhi",
        "country": "IN",
        "last_updated": "2017-11-02T22:34:01",
        "latitude": "35",
        "location": "",
        "longitude": "53",
        "model": "2BTech Model 202",
        "outdoors": true,
        "sn": "OZONE001",
        "timezone": "Asia/Kolkata",
        "url": "https://tatacenter-airquality.mit.edu/api/v1.0/device/OZONE001"
    }
