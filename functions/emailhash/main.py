
import datetime
import os
from flask import escape
from urllib.parse import quote
import functions_framework
import re
from cryptography.fernet import Fernet

def is_valid_email(email):
    # Define a regular expression pattern for a valid email address
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    # Use the re module to match the pattern against the email address
    if re.match(pattern, email):
        return True
    else:
        return False


@functions_framework.http
def emailhash(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """


    request_args = request.args
    key = request_args["key"]
    email = request_args["email"]
    reviewer_email = request_args["reviewer_email"]
  
    SECRET_KEY = os.getenv("SECRET_KEY")
    if key != SECRET_KEY:
        return "Unauthorized", 401   
   
   
    if not is_valid_email(email):
        return "Invalid encrypted email!", 401
    
    print(f"email: {email}") 
    fernet = Fernet(os.getenv("ENCRYPT_KEY"))  

    IMAGE_BUCKET = os.getenv("IMAGE_BUCKET")
    GEN_IMAGE_URL = quote(os.getenv("GEN_IMAGE_URL"))
    
    encMessage = fernet.encrypt(email.encode())    
    # Encode the URL component using the quote function
    emailhash = quote(encMessage)
    url = f"https://storage.googleapis.com/{IMAGE_BUCKET}/index.html?key={SECRET_KEY}&api={GEN_IMAGE_URL}&emailhash={emailhash}"
   
    if is_valid_email(reviewer_email):
        reviewer_emailhash = quote(fernet.encrypt(reviewer_email.encode()))
        url = f"{url}&reviewer_emailhash={reviewer_emailhash}"

    # Caching issue.
    url = f"{url}&now={datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    # print(url)
    result = f"""
Receiver: {email}
<br/>
Specific Reviewer: {reviewer_email}
<br/> 
Gen Image URL:
<br/> 
<br/> 
<a href="{url}">{url}</a>
""";

    return result, 200
