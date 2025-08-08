import boto3
import os
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
def lambda_handler(event, context):
    connectionId = event['requestContext']['connectionId']
    table.delete_item(Key={'connectionId': connectionId})
    return {'statusCode': 200}