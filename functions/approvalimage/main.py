
import datetime
from datetime import timezone
import os
import tempfile
import requests
from flask import escape
import functions_framework
import smtplib
from google.cloud import datastore
import qrcode

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


def send_email(subject, body, qrcode_image_path, gen_image_path, sender, recipients, password):

    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = subject
    msgRoot['From'] = sender
    msgRoot['To'] = ', '.join(recipients)

    msgHtml = MIMEText(body, 'html')
  
    # Define the image's ID as referenced in the HTML body above
    img = open(gen_image_path, 'rb').read()
    msgImg1 = MIMEImage(img, 'png')
    msgImg1.add_header('Content-ID', '<image1>')
    msgImg1.add_header('Content-Disposition', 'inline', filename="genimage.png")

    img = open(qrcode_image_path, 'rb').read()
    msgImg2 = MIMEImage(img, 'png')
    msgImg2.add_header('Content-ID', '<image2>')
    msgImg2.add_header('Content-Disposition', 'inline', filename="qrcode.png")

    msgRoot.attach(msgHtml)
    msgRoot.attach(msgImg1)
    msgRoot.attach(msgImg2)

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
def approvalimage(request):
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

    # Download the image from the URL public_url and save it to a temporary file
    response = requests.get(public_url)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(response.content)
        gen_image_path = f.name

    qrcode_image_path = generate_qrcode(public_url)

    subject = "Your Gen Image at " + datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    body = f"""<html>
<body>
    <p>
        Check out your generated image at: <br/>
        <img src="cid:image1"><br/>
        {public_url}
    </p>
    <p>
        Scan this QR Code: <br/>
        <img src="cid:image2">
    </p>
</body>
</html> 
"""
    sender = os.getenv("GMAIL")
    recipients = [email]
    password = os.getenv("APP_PASSWORD")

    send_email(subject, body, qrcode_image_path, gen_image_path, sender, recipients, password)

    update_gen_image_job(email, public_url, approver_email)
                  
    return "Approved and sent to " + email, 200, headers
    
def update_gen_image_job(email: str, image_url:str, approver_email:str) -> bool:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    with client.transaction():
        key = client.key('GenImageJob', email + "->" +image_url)
        entity = client.get(key)  
        entity['approver_email'] = approver_email
        entity['status'] = "APPROVAED"
        entity['modify_time'] = datetime.datetime.now(timezone.utc);   
        client.put(entity)

def is_gen_image_job_approvaed_or_rejected(email: str, image_url:str) -> str:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    student = client.get(client.key('GenImageJob', email + "->" +image_url))
    return student['status'] == "APPROVAED" or student['status'] == "REJECTED"