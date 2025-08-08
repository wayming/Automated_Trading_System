import boto3
import os
import json
import time
from boto3.dynamodb.conditions import Key

ddb = boto3.resource('dynamodb')
conn_table = ddb.Table(os.environ['CONNECTIONS_TABLE'])
msg_table = ddb.Table(os.environ['MESSAGES_TABLE'])

gateway_url = f"https://{os.environ['API_GATEWAY_ID']}.execute-api.{os.environ['CURR_AWS_REGION']}.amazonaws.com/{os.environ['STAGE']}"
apigw_client = boto3.client('apigatewaymanagementapi', endpoint_url=gateway_url)
print(f"API Gateway endpoint URL: {gateway_url}")

# Lambda function to store and forward messages
def lambda_handler(event, context):
    try:
        # Read body as raw string
        message = event.get('body', '')
        if not message:
            return {'statusCode': 400, 'body': 'Empty message body'}
    except Exception as e:
        return {'statusCode': 400, 'body': f"Error reading message: {str(e)}"}

    timestamp = int(time.time() * 1000)
    msg_item = {
        'partitionKey': 'global',
        'timestamp': timestamp,
        'message': message  # Store as-is
    }

    print("Storing message:", msg_item)

    try:
        msg_table.put_item(Item=msg_item)
    except Exception as e:
        print("Error writing to DynamoDB:", str(e))
        return {'statusCode': 500, 'body': 'Failed to write message'}

    # Trim to latest 10 messages
    messages = msg_table.query(
        KeyConditionExpression=Key('partitionKey').eq('global'),
        ScanIndexForward=True  # oldest first
    )['Items']

    if len(messages) > 10:
        for old in messages[:-10]:
            msg_table.delete_item(
                Key={
                    'partitionKey': 'global',
                    'timestamp': old['timestamp']
                }
            )

    # Send to all connections
    connections = conn_table.scan(ProjectionExpression='connectionId')['Items']
    for connection in connections:
        try:
            print(f"Send message to {connection['connectionId']}")
            apigw_client.post_to_connection(
                ConnectionId=connection['connectionId'],
                Data=message.encode('utf-8')
            )
        except apigw_client.exceptions.GoneException:
            conn_table.delete_item(Key={'connectionId': connection['connectionId']})

    return {'statusCode': 200}