
import datetime
from datetime import timezone
import os
import requests
from flask import escape
import functions_framework
import smtplib
from email.mime.text import MIMEText
from google.cloud import datastore


def send_email(subject, body, sender, recipients, password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())
    print("Message sent!")


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
    
    if is_gen_image_job_approvaed(email, public_url):
        return "Already approved!", 200, headers

    subject = "Your Gen Image at " + datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    body = f"""
Check out your generated image at

{public_url}

"""
    sender = os.getenv("GMAIL")
    recipients = [email]
    password = os.getenv("APP_PASSWORD")

    send_email(subject, body, sender, recipients, password)

    update_gen_image_job(email, public_url, approver_email)
                  
    return "Approved!", 200, headers
    
def update_gen_image_job(email: str, image_url:str, approver_email:str) -> bool:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    with client.transaction():
        key = client.key('GenImageJob', email + "->" +image_url)
        entity = client.get(key)  
        entity['approver_email'] = approver_email
        entity['status'] = "APPROVAED"
        entity['modify_time'] = datetime.datetime.now(timezone.utc);   
        client.put(entity)

def is_gen_image_job_approvaed(email: str, image_url:str) -> str:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    student = client.get(client.key('GenImageJob', email + "->" +image_url))
    return student['status'] == "APPROVAED"