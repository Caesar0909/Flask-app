
### API Keys

In order to interact with the Tata AQ API, you must first authenticate. The API
handles this by issuing each user a unique API key that is registered to your
account. This allows us to ensure each user is only accessing public data and is
correctly limited.

You can generate an API key by going to the [API section][1] and clicking on the
**Generate New Token** button. Each token acts as a complete username:password
combination and handles the entire authentication request. Please keep this
secure!

[1]: {{url_for('main.user_api')}}
