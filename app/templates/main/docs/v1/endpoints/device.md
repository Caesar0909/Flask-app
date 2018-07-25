
### device/[serial-number]

**Available methods: [ GET, PUT, DELETE ]**

The `device/[serial-number]` endpoint allows you to edit a device (**PUT**),
delete a device (**DELETE**) or retrieve information about an existing device
(**GET**). Data can be filtered or sorted using the methods described above
in the 'Advanced API Queries section'. Editing a device is only available if
you are the rightful owner (and have the necessary permissions). Deleting devices
can only be performed by the benevolent dictator.

Users can only receive information about devices that are either public or are
within your permissions. If successful, a 200 response will be returned along
with the data.

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

    $ http -a [api-key]: GET https://tatacenter-airquality.mit.edu/api/v1.0/device/OZONE001

    HTTP/1.1 200 OK
    Connection: keep-alive
    Content-Length: 331
    Content-Type: application/json
    Date: Wed, 16 May 2018 01:49:21 GMT
    Etag: "5de9d27a6a21e58413a8d1e3411bffd0"
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
