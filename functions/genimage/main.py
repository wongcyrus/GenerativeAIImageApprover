
import os
from pathlib import Path

import requests

import functions_framework
from google.cloud import storage

import smtplib
import urllib.parse
from google.cloud import datastore
import datetime
from datetime import timezone
import re
from cryptography.fernet import Fernet

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import tempfile

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

vertexai.init(project=os.getenv("GCP_PROJECT"),
              location=os.getenv("MODEL_GARDEN_REGION"))


IMAGE_BUCKET = os.getenv("IMAGE_BUCKET")
APPROVED_IMAGE_BUCKET = os.getenv("APPROVED_IMAGE_BUCKET")


def is_valid_email(email):
    # Define a regular expression pattern for a valid email address
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    # Use the re module to match the pattern against the email address
    if re.match(pattern, email):
        return True
    else:
        return False


@functions_framework.http
def genimage(request):
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
            "Access-Control-Allow-Methods": "POST, GET, PUT",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }

        return ("", 204, headers)
    headers = {"Access-Control-Allow-Origin": "*",
               "Access-Control-Allow-Methods": "POST, GET, PUT",
               "Access-Control-Allow-Headers": "Content-Type"}

    request_args = request.args

    key = request_args["key"]
    prompt = request_args["prompt"]
    negative_prompt = request_args["negativePrompt"]
    emailhash = request_args["emailhash"]

    if key != os.getenv("SECRET_KEY"):
        return "Unauthorized", 401, headers

    fernet = Fernet(os.getenv("ENCRYPT_KEY"))
    email = fernet.decrypt(emailhash).decode()
    if not is_valid_email(email):
        return "Invalid encrypted email!", 401, headers
    print(f"email: {email}")

    if is_gen_image_job_exceed_rate_limit(email):
        return "Rate limit exceeded, and please wait for 30s!", 429, headers
    save_new_gen_image_job(email, prompt, negative_prompt)

    model = ImageGenerationModel.from_pretrained("imagegeneration@002")
    images = model.generate_images(
        prompt=prompt,
        negative_prompt=negative_prompt,
        number_of_images=1,
        seed=1
    )

    image_name = "image-"+str(hash(prompt)) + ".png"
    image_path = f"/tmp/{image_name}"
    images[0].save(location=image_path, include_generation_parameters=True)

    public_url = upload_image_to_bucket(image_path)

    params = {'key': key, 'email': email, 'public_url': public_url}
    approver_emails = os.getenv("APPROVER_EMAILS").split(",")
    subject = "Verify Gen Image for " + email
    sender = os.getenv("GMAIL")

    if reviewer_emailhash := request_args.get("reviewer_emailhash"):
        reviewer_email = fernet.decrypt(reviewer_emailhash).decode()
        if is_valid_email(reviewer_email):
            approver_emails.append(reviewer_email)
    # remove duplicate emails
    approver_emails = list(dict.fromkeys(approver_emails))

    recipients = approver_emails
    password = os.getenv("APP_PASSWORD")

    params = {'key': key, 'email': email, 'public_url': public_url}
    update_gen_image_job(email, public_url)
    send_email(subject, sender, recipients, password, params)

    approved_image_url = f"https://storage.googleapis.com/{APPROVED_IMAGE_BUCKET}/" + image_name

    return approved_image_url, 200, headers


def download_image(image_url):
    # Download image from url
    r = requests.get(image_url, allow_redirects=True)
    # Image name with hash or image_url
    image_name = "image-"+str(hash(image_url)) + ".png"
    image_path = f"/tmp/{image_name}"
    open(image_path, "wb").write(r.content)
    return image_path


def upload_image_to_bucket(image_path):
    # Upload image to bucket
    client = storage.Client()
    bucket = client.get_bucket(IMAGE_BUCKET)
    # extract image name from path
    image_name = Path(image_path).name
    blob = bucket.blob(image_name)
    blob.content_type = 'image/png'
    blob.upload_from_filename(image_path)
    return blob.public_url


def send_email(subject: str, sender: str, recipients: list[str], password: str, params: dict):
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender, password)
        for recipient in recipients:
            params['approver_email'] = recipient
            body = get_email_msg(subject, sender, recipient, params)
            smtp_server.sendmail(sender, recipient, body)

    print("Message sent!")


def get_email_msg(subject: str, sender: str, recipient: str, params: dict) -> str:
    approval_url = os.getenv("APPROVAL_URL")+"?" + \
        urllib.parse.urlencode(params, doseq=True)
    reject_url = os.getenv("REJECT_URL")+"?" + \
        urllib.parse.urlencode(params, doseq=True)
    public_url = params["public_url"]

    body = f"""
Please check the following image and click the link to approve it.
<br/>
<img src="cid:image1"><br/>
{public_url}
<br/>
<br/>
Approve: <br/>
{approval_url}
<br/>
<br/>
Reject:<br/>
{reject_url}
    """

    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = subject
    msgRoot['From'] = sender
    msgRoot['To'] = recipient

    msgHtml = MIMEText(body, 'html')

    # Define the image's ID as referenced in the HTML body above
    response = requests.get(public_url)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(response.content)
        gen_image_path = f.name
    img = open(gen_image_path, 'rb').read()
    msgImg1 = MIMEImage(img, 'png')
    msgImg1.add_header('Content-ID', '<image1>')
    msgImg1.add_header('Content-Disposition', 'inline',
                       filename="genimage.png")

    msgRoot.attach(msgHtml)
    msgRoot.attach(msgImg1)

    return msgRoot.as_string()


def save_new_gen_image_job(email: str, prompt: str, negative_prompt: str) -> bool:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    key = client.key('GenImageJob', email)
    entity = datastore.Entity(key=key)
    now = datetime.datetime.now(timezone.utc)
    entity.update({
        'email': email,
        'prompt': prompt,
        'negative_prompt': negative_prompt,
        'status': "GENERATING_IMAGE",
        'create_time': now,
        'modify_time': now
    })
    client.put(entity)


def update_gen_image_job(email: str, image_url: str) -> bool:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    with client.transaction():
        old_key = client.key('GenImageJob', email)
        old_entity = client.get(old_key)
        entity = datastore.Entity(key=client.key(
            'GenImageJob', email + "->" + image_url))
        entity.update({
            'email': email,
            'prompt': old_entity['prompt'],
            'negative_prompt': old_entity['negative_prompt'],
            'status': "WAITING_FOR_APPROVAL",
            'create_time': old_entity['create_time'],
            'modify_time': datetime.datetime.now(timezone.utc)
        })
        client.put(entity)
        client.delete(old_key)


def is_gen_image_job_exceed_rate_limit(email: str) -> bool:
    client = datastore.Client(project=os.environ.get('GCP_PROJECT'))
    query = client.query(kind='GenImageJob')
    query.add_filter('email', '=', email)
    query.order = ['-modify_time']
    results = list(query.fetch(limit=1))
    if len(results) == 0:
        return False
    else:
        last_approved_time = results[0]['modify_time']
        now = datetime.datetime.now(timezone.utc)
        diff = now - last_approved_time
        waiting_time = 60 / int(os.environ.get('RATE_LIMIT_PER_MINUTE'))
        return diff.seconds < waiting_time  # 30 seconds rate limit
