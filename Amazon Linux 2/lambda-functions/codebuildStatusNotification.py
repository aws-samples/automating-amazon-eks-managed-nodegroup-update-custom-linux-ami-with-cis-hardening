import boto3
import os
import json

region = os.environ['REGION']
codecommit = boto3.client('codecommit', region_name=region)
sns = boto3.client('sns', region_name=region)
REPO_NAME=os.environ['REPO_NAME']
BRANCH_NAME=os.environ['BRANCH_NAME']
SNS_TOPIC=os.environ['SNS_TOPIC']
def lambda_handler(message, context):
    release_history_data=json.loads('[]')
    
    release_history_data=json.loads(codecommit.get_file(repositoryName=REPO_NAME,filePath='releaseHistory.json')['fileContent'])[-1]
    
    print(json.dumps(release_history_data, indent=4))
    status = message['detail']['build-status']
    project = message['detail']['project-name']
    build_id = message['detail']['build-id']
    subject = "{status}: AWS CodeBuild {project}".format(status=status, project=project)
    body = "Build {build_id} for build project {project} has reached the build status of {status}.The update details are as follows: \n {release_history_data}".format(status=status, project=project, build_id=build_id, release_history_data=json.dumps(release_history_data,indent=4))
 
    sns_topic = SNS_TOPIC
    sns.publish(
        TopicArn=sns_topic,
        Subject=subject,
        Message=body
    )

    return ('Sent a message to an Amazon SNS topic.')