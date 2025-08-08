import boto3, os, json
from boto3.dynamodb.conditions import Key

ddb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
connections_table = ddb.Table(os.environ['CONNECTIONS_TABLE'])

def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    print(f"New connection: {connection_id}")
    try:
        connections_table.put_item(Item={'connectionId': connection_id})
    except Exception as e:
        print(f"Failed to save connection: {e}")
        return {'statusCode': 500, 'body': 'DB Error'}

    try:
        lambda_client.invoke(
            FunctionName=os.environ['ASYNC_CONNECT_WORKER'],
            InvocationType='Event',
            Payload=json.dumps({'connectionId': connection_id})
        )
    except Exception as e:
        print(f"Failed to invoke async worker: {e}")
    return {'statusCode': 200}