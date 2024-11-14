import json
import os
import boto3
import botocore
import base64
import shutil

region = os.environ['REGION']
s3 = boto3.client('s3')
S3_BUCKET=os.environ['S3_BUCKET']
FOLDER='/tmp/imageBuilder'

def lambda_handler(event, context):
    new_data=json.loads('{}') 
    release_history_data=json.loads('[]')
    fileExists = False
    file = None
    new_data_len = len(new_data)
    imageBuilderEvent=json.loads(event['Records'][0]['Sns']['Message'])
    
    # Remove the folder if it exists. 
    if os.path.exists(FOLDER):
        shutil.rmtree(FOLDER,ignore_errors=True)
    
    #Create the folder where the json file will be created, appended and then the zip file will be created of this folder
    os.mkdir(FOLDER)
    
    # Download the file from the S3 to append the new AMI details. If the file does not exist then its throws an exception and creates
    # a new file to write the new AMI details
    try:
        s3.download_file(S3_BUCKET,'releaseHistory.json','/tmp/imageBuilder/releaseHistory.json')
        file = open('/tmp/imageBuilder/releaseHistory.json','r+')
        release_history_data=json.load(file)
        file.seek(0)
        fileExists = True
        
    except botocore.exceptions.ClientError as error:
        print(error.response)
        if error.response['Error']['Code'] == "403" or error.response['Error']['Code'] == "404":
           print('File does not exist') 
           file = open('/tmp/imageBuilder/releaseHistory.json','a')
    
    # Gets the new AMI details from the SNS event that triggered the lambda function
    new_data['NewAMIID'] = imageBuilderEvent['outputResources']['amis'][0]['image']
    new_data['NewAMICreationDate'] = (imageBuilderEvent['outputResources']['amis'][0]['name'].split(" "))[1]
    param=imageBuilderEvent['imageRecipe']['components'][0]['parameters']
    
        
    for i in range(len(param)):
        new_data[param[i]['name']] = param[i]['value'][0]

    
    release_history_data.append(new_data)
    
    print(json.dumps(release_history_data, indent=4))
    
    json.dump(release_history_data, file, indent = 4)
    file.close()
    
    # Create a zip file to be uploaded to S3 bucket that would trigger the Codepipeline. Zip file is necessary because Codebuild needs
    # zip file from S3
    
    shutil.make_archive('/tmp/imageBuilder', 'zip', '/tmp/imageBuilder')
    
    # Upload both json file and the zip file to the S3 bucket
    s3.upload_file('/tmp/imageBuilder/releaseHistory.json', S3_BUCKET, 'releaseHistory.json')
    s3.upload_file('/tmp/imageBuilder.zip', S3_BUCKET, 'releaseHistory.zip')