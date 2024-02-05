import json
import os
import boto3
import botocore
import base64

region = os.environ['REGION']
codecommit = boto3.client('codecommit', region_name=region)
imagebuilder = boto3.client('imagebuilder', region_name=region)
REPO_NAME=os.environ['REPO_NAME']
BRANCH_NAME=os.environ['BRANCH_NAME']
def lambda_handler(event, context):
    lastCommitID=""
    new_data=json.loads('{}') 
    release_history_data=json.loads('[]')
    fileExists = False
    new_data_len = len(new_data)
    imageBuilderEvent=json.loads(event['Records'][0]['Sns']['Message'])
    
    #Getfile from the codecommit to get the details of the past releases
    
    try:
        release_history_data=json.loads(codecommit.get_file(repositoryName=REPO_NAME,filePath='releaseHistory.json')['fileContent'])
        fileExists = True

    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'FileDoesNotExistException':
           print('No file created')          
    
    

    new_data['NewAMIID'] = imageBuilderEvent['outputResources']['amis'][0]['image']
    new_data['NewAMICreationDate'] = (imageBuilderEvent['outputResources']['amis'][0]['name'].split(" "))[1]
    param=imageBuilderEvent['imageRecipe']['components'][0]['parameters']

    
    for i in range(len(param)):
        new_data[param[i]['name']] = param[i]['value'][0]

    
    release_history_data.append(new_data)
    print(json.dumps(release_history_data, indent=4))
    

    
    try:
      lastCommitID=codecommit.get_branch(repositoryName=REPO_NAME,branchName=BRANCH_NAME)['branch']['commitId']

    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'BranchDoesNotExistException':
           print('No Branch created yet hence uploading file without parentCommitId')
           codecommit.put_file(repositoryName=REPO_NAME,branchName=BRANCH_NAME,fileContent=json.dumps(release_history_data, indent=4),filePath='releaseHistory.json',commitMessage="Updating new ami creation details in releaseHistory.json")
           return 

    print("Last Commit ID is "+ lastCommitID)
    codecommit.put_file(repositoryName=REPO_NAME,branchName=BRANCH_NAME,fileContent=json.dumps(release_history_data, indent=4),filePath='releaseHistory.json',parentCommitId=lastCommitID, commitMessage="Updating new ami creation details in releaseHistory.json")