import boto3, os, json, time
from boto3.dynamodb.conditions import Key

# Async worker to send messages after connection established
def lambda_handler(event, context):
    connection_id = event.get('connectionId')
    print(f"Async PostConnectWorker: {connection_id}")

    ddb = boto3.resource('dynamodb')
    msg_table = ddb.Table(os.environ['MESSAGES_TABLE'])

    gateway_url = f"https://{os.environ['API_GATEWAY_ID']}.execute-api.{os.environ['CURR_AWS_REGION']}.amazonaws.com/{os.environ['STAGE']}"
    apigw = boto3.client('apigatewaymanagementapi', endpoint_url=gateway_url)

    try:
        response = msg_table.query(
            KeyConditionExpression=Key('partitionKey').eq('global'),
            ScanIndexForward=False,
            Limit=10
        )
        messages = response.get('Items', [])[::-1]
        for msg in messages:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=msg['message'].encode('utf-8')
            )
    except apigw.exceptions.GoneException:
        print(f"Connection {connection_id} is gone.")
    except Exception as e:
        print(f"Error sending: {e}")