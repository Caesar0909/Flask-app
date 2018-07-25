
### device/

**Available methods: [ GET, POST ]**

The `device/` endpoint allows you to add a new device (POST) or retrieve
information about existing devices (GET). Data can be filtered or sorted
using the methods described above in the 'Advanced API Queries section'. Adding
new devices is limited to administrators at this point in time.

Results are paginated and you are only able to receive information about devices
that are either public or are within your permissions. If successful, a 200
response will be returned along with the data.

The response data includes the following:

  * `city`: the city where the sensor is located (string)
  * `country`: the country where the sensor is located (ISO country code)
  * `last_updated`: the timestamp corresponding to when the sensor was last updated. This
                        should correspond to the timezone listed below with a default of UTC.
  * `latitude`: latitude of last known location (string)
  * `longitude`: longitude of last known location (string)
  * `location`: description of the location (string)
  * `model`: model type of the sensor (string)
  * `outdoors`: true if the sensor is outdoors (boolean)
  * `timezone`: timezone of the sensor
  * `sn`: serial number
  * `url`: url for the sensor

If working with sensor data, the most important columns will be the serial number (`sn`)
and the url (`url`). Details on the **POST** method are forthcoming.

##### Sample Response

    $ http -a [api-key]: GET https://tatacenter-airquality.mit.edu/api/v1.0/device/

    HTTP/1.1 200 OK
    Connection: keep-alive
    Content-Length: 779
    Content-Type: application/json
    Date: Wed, 16 May 2018 00:57:21 GMT
    Etag: "50286961588c97c8c8b9e73b1ab71500"
    Server: nginx/1.10.3 (Ubuntu)

    {
        "meta": {
            "first_url": "https://tatacenter-airquality.mit.edu/api/v1.0/device/?page=1&per_page=1&expand=1",
            "last_url": "https://tatacenter-airquality.mit.edu/api/v1.0/device/?page=4&per_page=1&expand=1",
            "next_url": "https://tatacenter-airquality.mit.edu/api/v1.0/device/?page=2&per_page=1&expand=1",
            "page": 1,

            "pages": 4,
            "per_page": 1,
            "prev_page": null,
            "total": 4
            },
        "data": [
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
        ],
        ...
    }
