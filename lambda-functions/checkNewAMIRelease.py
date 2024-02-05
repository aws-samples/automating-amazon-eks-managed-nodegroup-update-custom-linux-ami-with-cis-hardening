import boto3
import os
from datetime import datetime

region = os.environ['REGION']

ssm = boto3.client('ssm', region_name=region)
ec2 = boto3.client('ec2', region_name=region)
codebuild = boto3.client('codebuild', region_name=region)
eks = boto3.client('eks', region_name=region)
imagebuilder = boto3.client('imagebuilder', region_name=region)

CLUSTER_NAME = os.environ['CLUSTER_NAME']
IMAGE_BUILDER_PIPELINE = os.environ['IMAGE_BUILDER_PIPELINE']
CUSTOM_NODEGROUP = [];


def lambda_handler(event, context):
    NODEGROUP_VERSION = "";
    RECOMMENDED_NEW_AMI = False;
    CIS_NEW_AMI = False;
    CLUSTER_VERSION = eks.describe_cluster(name=CLUSTER_NAME)['cluster']['version']
    
    #This is the recommended AMI ID provided by the SSM paramter
    RECOMMENDED_EKS_AMI_ID = ssm.get_parameter(Name=f'/aws/service/eks/optimized-ami/{CLUSTER_VERSION}/amazon-linux-2/recommended/image_id')['Parameter']['Value']
    
    #Below we find the AMI ID and creation date of the latest CIS Level 2 AMI.
    CIS_LEVEL2_AMIS = ec2.describe_images(
        Filters=[
            {
                'Name': 'name',
                'Values': ["CIS Amazon Linux 2 Benchmark*- Level 2*"]
            }
            ]
        );
    
    sorted_AMIs = sorted(CIS_LEVEL2_AMIS['Images'], key=lambda cd: cd['CreationDate'], reverse=True)
    LATEST_CIS_LEVEL2_AMI_ID = sorted_AMIs[0]['ImageId']
    
    #This is the creation-date of the LATEST_CIS_LEVEL2_AMI_ID
    LATEST_CIS_LEVEL2_AMI_CREATION_DATE = sorted_AMIs[0]['CreationDate']
    LATEST_CIS_LEVEL2_AMI_CREATION_DATE = datetime.strptime(LATEST_CIS_LEVEL2_AMI_CREATION_DATE, '%Y-%m-%dT%H:%M:%S.%fZ')
    
    #This is the creation-date of the RECOMMENDED_EKS_AMI_ID
    RECOMMENDED_EKS_AMI_CREATION_DATE = ec2.describe_images(ImageIds=[f'{RECOMMENDED_EKS_AMI_ID}'])['Images'][0]['CreationDate'];
    RECOMMENDED_EKS_AMI_CREATION_DATE = datetime.strptime(RECOMMENDED_EKS_AMI_CREATION_DATE, '%Y-%m-%dT%H:%M:%S.%fZ')
    CURRENT_NODEGROUP_AMI_ID = ""
    UPDATE_REASON = ""
    NODEGROUP_LIST = eks.list_nodegroups(clusterName=CLUSTER_NAME)['nodegroups']
    print(NODEGROUP_LIST)
    
    for nodegroup in NODEGROUP_LIST:
        current_nodegroup_details = eks.describe_nodegroup(clusterName=CLUSTER_NAME,nodegroupName=nodegroup)
        if NODEGROUP_VERSION == "":
            print("Inside version if")
            NODEGROUP_VERSION = current_nodegroup_details['nodegroup']['version']
            
        if current_nodegroup_details['nodegroup']['amiType'] == 'CUSTOM':
            CURRENT_NODEGROUP_AMI_ID = current_nodegroup_details['nodegroup']['releaseVersion']
            
            #This is the creation-date of the CURRENT_NODEGROUP_AMI_ID from the NODEGROUP_LIST
            CURRENT_NODEGROUP_AMI_CREATION_DATE = ec2.describe_images(ImageIds=[f'{CURRENT_NODEGROUP_AMI_ID}'])['Images'][0]['CreationDate'];
            CURRENT_NODEGROUP_AMI_CREATION_DATE = datetime.strptime(CURRENT_NODEGROUP_AMI_CREATION_DATE, '%Y-%m-%dT%H:%M:%S.%fZ')
            
            if LATEST_CIS_LEVEL2_AMI_CREATION_DATE > CURRENT_NODEGROUP_AMI_CREATION_DATE:
              print("A latest CIS AMI "+ LATEST_CIS_LEVEL2_AMI_ID + "has been launched after CURRENT NODEGROUP AMI " + CURRENT_NODEGROUP_AMI_ID + " associated with the nodegroup " + nodegroup + "\n")
              CIS_NEW_AMI = True;
              CUSTOM_NODEGROUP.append(nodegroup)
            elif RECOMMENDED_EKS_AMI_CREATION_DATE > CURRENT_NODEGROUP_AMI_CREATION_DATE:
              print("A recommended CIS AMI "+ RECOMMENDED_EKS_AMI_ID + "has been launched after CURRENT NODEGROUP AMI " + CURRENT_NODEGROUP_AMI_ID + " associated with the nodegroup " + nodegroup + "\n")
              RECOMMENDED_NEW_AMI = True;
              CUSTOM_NODEGROUP.append(nodegroup)
              
    if CIS_NEW_AMI == True and RECOMMENDED_NEW_AMI == False:
        UPDATE_REASON = "Update due to new CIS Level 2 AMI Release"
    elif CIS_NEW_AMI == False and RECOMMENDED_NEW_AMI == True:
        UPDATE_REASON = "Update due to new recommended EKS AMI Release"
    else:
        UPDATE_REASON = "Update due to both new CIS Level 2 and recommended EKS AMI Release"
    
        
    
    if CIS_NEW_AMI == True or RECOMMENDED_NEW_AMI == True:
        IMAGE_PIPELINE_DETAILS = imagebuilder.get_image_pipeline(imagePipelineArn=IMAGE_BUILDER_PIPELINE)
        IMAGE_RECIPE_ARN = IMAGE_PIPELINE_DETAILS['imagePipeline']['imageRecipeArn']
    
        
        IMAGE_RECIPE_DETAILS = imagebuilder.get_image_recipe(imageRecipeArn=IMAGE_RECIPE_ARN)
        IMAGE_RECIPE_VERSION = IMAGE_RECIPE_DETAILS['imageRecipe']['version']
        IMAGE_RECIPE_NAME = IMAGE_RECIPE_DETAILS['imageRecipe']['name']
        COMPONENT_ARN = IMAGE_RECIPE_DETAILS['imageRecipe']['components'][0]['componentArn']
        
        
        temp_version = IMAGE_RECIPE_VERSION.split('.')
        temp_version[2] = str(int(temp_version[2]) + 1)
        NEW_IMAGE_RECIPE_VERSION = '.'.join(temp_version)
        
        
        NEW_IMAGE_RECIPE_ARN=imagebuilder.create_image_recipe(
                name=IMAGE_RECIPE_NAME,
                semanticVersion=NEW_IMAGE_RECIPE_VERSION,
                components=[{
                    'componentArn': COMPONENT_ARN, 'parameters': [
                    {
                        'name': 'EKSClusterVersion',
                        'value': [
                            NODEGROUP_VERSION,
                        ]
                    },
                    {
                        'name': 'CurrentNodegroupAMI',
                        'value': [
                            CURRENT_NODEGROUP_AMI_ID,
                        ]
                    },
                   {
                       'name': 'UpdateReason',
                       'value': [
                           UPDATE_REASON,
                        ]
                    },
                    {
                        'name': 'UpdatedNodegroups',
                        'value': [
                            ','.join(NODEGROUP_LIST),
                        ]
                    },
                 ]
                }],
                parentImage=LATEST_CIS_LEVEL2_AMI_ID,
                workingDirectory='/var/tmp'
            )['imageRecipeArn']
            
            
        imagebuilder.update_image_pipeline(imagePipelineArn=IMAGE_BUILDER_PIPELINE,imageRecipeArn=NEW_IMAGE_RECIPE_ARN,infrastructureConfigurationArn=IMAGE_PIPELINE_DETAILS['imagePipeline']['infrastructureConfigurationArn'],enhancedImageMetadataEnabled=False)
        imagebuilder.start_image_pipeline_execution(imagePipelineArn=IMAGE_BUILDER_PIPELINE)        
