
import datetime
from datetime import timezone
import os
import tempfile
import requests
from flask import escape
import functions_framework
import smtplib
from email.mime.text import MIMEText
from google.cloud import datastore

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


def send_email(subject, body, sender, recipients, password):

    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = subject
    msgRoot['From'] = sender
    msgRoot['To'] = ', '.join(recipients)

    msgHtml = MIMEText(body, 'html')  
    msgRoot.attach(msgHtml)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msgRoot.as_string())
    print("Message sent!")

def generate_qrcode(public_url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(public_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qrcode_image_path = tempfile.NamedTemporaryFile(suffix='.png').name
    img.save(qrcode_image_path)
    return qrcode_image_path
    
@functions_framework.http
def rejectimage(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """

    # Set CORS headers for the preflight request
    if request.method == "OPTIONS":
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }

        return ("", 204, headers)
    headers = {"Access-Control-Allow-Origin": "*"}

    request_args = request.args
  
    public_url = request_args["public_url"]
    email = request_args["email"]
    key = request_args["key"]
    approver_email = request_args["approver_email"]
    print(f"email: {email}")

    if key != os.getenv("SECRET_KEY"):
        return "Unauthorized", 401, headers
    
    if is_gen_image_job_approvaed_or_rejected(email, public_url):
        return "Already approved or rejected!", 200, headers


    subject = "Sorry your Gen Image at " + datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S") + " is not good!" 
    body = f"""<html>
<body>
    <p>
       Sorry, please try another prompt!
    </p> 
</body>
</html> 
"""
    sender = os.getenv("GMAIL")
    recipients = [email]
    password = os.getenv("APP_PASSWORD")

    send_email(subject, body, sender, recipients, password)   
                  
    return "Rejected!", 200, headers
    


def is_gen_image_job_approvaed_or_rejected(email: str, image_url:str) -> str:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    student = client.get(client.key('GenImageJob', email + "->" +image_url))
    return student['status'] == "APPROVAED" or student['status'] == "REJECTED"