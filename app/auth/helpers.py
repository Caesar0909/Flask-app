import sendgrid
from sendgrid.helpers.mail import *

def confirmation_email(to_email, from_email, from_name, link): #pragma: no cover
    ''' Send a confirmation email upon registration through mandrill '''

    from_email = Email(email=from_email, name=from_name)
    to_email = Email(to_email)
    subject = "Account Confirmation | Tata Center Air Quality Project"

    message = """
            <h3>Thank you for registering!</h3>
            <p>Please follow the link below (or paste in your browser) to verify
             your email address and complete the registration process.</p>
            <p>{}</p>
            """.format(link)

    content = Content("text/html", message)

    email = Mail(from_email=from_email, to_email=to_email, subject=subject, content=content)

    email.replyto = from_email

    return email.get()

def password_reset_email(to_email, from_email, from_name, link): #pragma: no cover
    ''' Send a confirmation email upon registration through mandrill '''

    from_email = Email(email=from_email, name=from_name)
    to_email = Email(to_email)
    subject = "Account Setting Update"

    message = """
            <h3>You're almost done!</h3>
            <p>Please follow the link below (or paste in your browser) to complete
             the password reset process.</p>
            <p>{}</p>
            """.format(link)

    content = Content("text/html", message)

    email = Mail(from_email=from_email, to_email=to_email, subject=subject, content=content)

    return email.get()
