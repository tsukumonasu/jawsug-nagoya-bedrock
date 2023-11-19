import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO')))
bedrock_runtime_client = boto3.client('bedrock-runtime')


def get_completion(user_prompt):
    model_id = 'anthropic.claude-v2'
    accept = 'application/json'
    content_type = 'application/json'

    body = json.dumps({
        "prompt": user_prompt,
        "max_tokens_to_sample": 600,
    })

    response = bedrock_runtime_client.invoke_model(
        modelId=model_id,
        accept=accept,
        contentType=content_type,
        body=body
    )

    response_body = json.loads(response.get('body').read())

    print("Received response_body:" + json.dumps(response_body, ensure_ascii=False))

    return response_body.get('completion')


# Lambda のハンドラー関数
def lambda_handler(event, context):
    if 'AppsheetBot' not in event['headers']['user-agent']:
        return {
            'statusCode': 401,
            'body': json.dumps('401 Unauthorized')
        }
    print(event)
    # return get_completion(event.get('user_prompt'))

    result = {
        'statusCode': 200,
        'body': {'completion': get_completion(json.loads(event['body'])['user_prompt'])}
    }
    print(result)
    return result
