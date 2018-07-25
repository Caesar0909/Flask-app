
## API v1 Introduction

Welcome to the Tata Center Air Quality API documentation.

The Tata Center API allows you to retrieve data from our expanding network of
air quality monitoring stations in a simple, programmatic way using conventional
HTTP requests. The endpoints are intuitive, allowing you to easily make calls to
retrieve information and turn data into actionable insights.

The API documentation begins with a brief overview of the technology and
design of the API, followed by reference information for each endpoint.

Throughout this documentation, examples will be shown using the tool [httpie][1], a
great command line HTTP client that will help get your data! Example code will
appear as follows:

    $ http -a [username]:[password] GET https://tatacenter-airquality.mit.edu/api/v1.0/auth/

Each url is built using the following format:

    $ https://tatacenter-airquality.mit.edu/api/[api version]/[endpoint]

The current API version is `v1.0`. Thus, each unique URL you build will begin with:

    $ https://tatacenter-airquality.mit.edu/api/v1.0/[endpoint]


[1]: https://httpie.org/
