import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO')))

kendra_client = boto3.client('kendra')
bedrock_runtime_client = boto3.client('bedrock-runtime')


# Kendra から検索結果を取得
def get_retrieval_result(query_text, index_id):
    response = kendra_client.query(
        QueryText=query_text,
        IndexId=index_id,
        AttributeFilter={
            "EqualsTo": {
                "Key": "_language_code",
                "Value": {"StringValue": "ja"},
            },
        },
    )

    # Kendra の応答から最初の5つの結果を抽出
    results = response['ResultItems'][:5] if response['ResultItems'] else []

    # 結果からドキュメントの抜粋部分のテキストを抽出
    for i in range(len(results)):
        results[i] = results[i].get("DocumentExcerpt", {}).get("Text", "").replace('\\n', ' ')

    print("Received results:" + json.dumps(results, ensure_ascii=False))

    return json.dumps(results, ensure_ascii=False)


def get_completion(user_prompt):
    index_id = os.getenv('KENDRA_INDEX_ID')

    prompt = f"""\n\nHuman:
    [参考]情報をもとに[質問]に適切に答えてください。
    [質問]
    {user_prompt}
    [参考]
    {get_retrieval_result(user_prompt, index_id)}
    Assistant:
    """

    # 各種パラメーターの指定
    model_id = 'anthropic.claude-v2'
    accept = 'application/json'
    content_type = 'application/json'

    body = json.dumps({
        "prompt": prompt,
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


