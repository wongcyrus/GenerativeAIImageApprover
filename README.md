# Generative AI Image Approver
When holding a workshop on generative AI images, students are full of creativity and there will inevitably be #embarrassing moments! To avoid such situations, each picture needs to be quickly reviewed and approved. Here’s a simple demonstration of our approval process Google Cloud Platform Serverless #application through Gmail.


## Deployment
1. Fork this repo and create a GitHub Codespaces.
2. Rename .env.template to .env. and fill in 
```
PROJECTID=Your GCP project gonna to be created
BillING_ACCOUNT=Billing Account
SECRET_KEY=Use it for simple Authentication
ENCRYPT_KEY=encrypt email key and please use email_hash_generator.py to generate it.
GMAIL=Use it to send email
APP_PASSWORD=Gmail App password from https://support.google.com/accounts/answer/185833?hl=en 
APPROVER_EMAILS=List of email seperated by comma and they will receive email to review and approve the generated images.
RATE_LIMIT_PER_MINUTE=Control the number of images genrerate by email.
MODEL_GARDEN_REGION=
REGION=Deployment Region (asia-east1)
GOOGLE_APPLICATION_CREDENTIALS=/home/codespace/.config/gcloud/application_default_credentials.json
```
2. Login your GCP account ```gcloud auth application-default login``` and ```gcloud auth application-default set-quota-project```
3. Run ```./deploy.sh```
4. You will get error ```Error waiting to create function: Error waiting for Creating function: Error code 7, message: Unable to retrieve the repository metadata for..```
And, it is known bug https://github.com/firebase/firebase-tools/issues/5244, and it will work when you retry.
5. Run ```./deploy.sh``` again.
6. Share gen-image-url for your workshop.

## Caching issue
if you updated the index.html, you will not be able to get the latest verions due to caching.
The solution is to add a dummy parameter in the gen-image-url, and it will load the new version.


