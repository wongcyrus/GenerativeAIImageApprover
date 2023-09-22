from cryptography.fernet import Fernet
from dotenv import load_dotenv
from pathlib import Path
import os
from urllib.parse import quote
from openpyxl import Workbook

dotenv_path = Path('../cdktf/.env')
load_dotenv(dotenv_path=dotenv_path)

emails = ["cywong@vtc.edu.hk","t-cywong@stu.vtc.edu.hk"]

fernet = Fernet(os.getenv('ENCRYPT_KEY'))
# key = Fernet.generate_key()
# print(key)

result = []
for email in emails:      
    encMessage = fernet.encrypt(email.encode())    
    # Encode the URL component using the quote function
    encoded_component = quote(encMessage)
    base_url = "https://storage.googleapis.com/website-asia-east1dz7rhjll/index.html?key=432fsdf34324f67gdf&api=https://asia-east1-gen-image-approver-dev.cloudfunctions.net/genimage&emailhash="
    url = base_url+encoded_component
    # print(url)
    result.append({"email":email,"url":url})

print(result)

wb = Workbook()
ws = wb.active
ws.append(["email","url"])
for key in result:
    ws.append([key["email"],key["url"]])
# save to current python directory
current_directory = os.path.dirname(os.path.realpath(__file__))
wb.save(os.path.join(current_directory, "gen_ai_urls.xlsx"))  