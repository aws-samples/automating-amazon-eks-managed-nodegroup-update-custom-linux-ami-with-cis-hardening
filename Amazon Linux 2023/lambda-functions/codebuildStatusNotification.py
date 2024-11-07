import boto3
import os
import json

region = os.environ['REGION']
s3 = boto3.client('s3')
sns = boto3.client('sns', region_name=region)
S3_BUCKET=os.environ['S3_BUCKET']
SNS_TOPIC=os.environ['SNS_TOPIC']
def lambda_handler(message, context):
    release_history_data=json.loads('[]')
    
    s3.download_file(S3_BUCKET,'releaseHistory.json','/tmp/releaseHistory.json')
    file = open('/tmp/releaseHistory.json','r+')
    release_history_data=json.load(file)
   
    
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