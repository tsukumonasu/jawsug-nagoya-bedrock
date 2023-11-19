import base64
import datetime

import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO')))

bedrock_runtime_client = boto3.client('bedrock-runtime', os.getenv("AWS_DEFAULT_REGION"))
s3 = boto3.client('s3')


# Kendra から検索結果を取得
def get_sd_prompt(query_text):
    prompt = "Human: " + query_text + """\n
あなたはStable Diffusionのプロンプトを生成するAIアシスタントです。
以下の step でStableDiffusionのプロンプトを生成してください。

<step>
* rule を理解してください。ルールは必ず守ってください。例外はありません。
* ユーザは生成して欲しい画像の要件をチャットで指示します。チャットのやり取りを全て理解してください。
* チャットのやり取りから、生成して欲しい画像の特徴を正しく認識してください。
* 画像生成において重要な要素をから順にプロンプトに出力してください。ルールで指定された文言以外は一切出力してはいけません。例外はありません。
</step>

<rule>
* プロンプトは output-format の通りに、JSON形式で出力してください。JSON以外の文字列は一切出力しないでください。JSONの前にも後にも出力禁止です。
* JSON形式以外の文言を出力することは一切禁止されています。挨拶、雑談、ルールの説明など一切禁止です。
* プロンプトは単語単位で、カンマ区切りで出力してください。長文で出力しないでください。プロンプトは必ず英語で出力してください。
* プロンプトには以下の要素を含めてください。
 * 画像のクオリティ、被写体の情報、衣装・ヘアスタイル・表情・アクセサリーなどの情報、画風に関する情報、背景に関する情報、構図に関する情報、ライティングやフィルタに関する情報
* 画像に含めたくない要素については、negativePromptとして出力してください。なお、negativePromptは必ず出力してください。
* フィルタリング対象になる不適切な要素は出力しないでください。
</rule>

<output-format>
{
  prompt: string,
  negativePrompt: string,
}
</output-format>

\n\nAssistant:
"""

    body = json.dumps(
        {
            "prompt": prompt,
            "max_tokens_to_sample": 500,
        }
    )

    resp = bedrock_runtime_client.invoke_model(
        modelId="anthropic.claude-v2",
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    answer = resp["body"].read().decode()
    return json.loads(json.loads(answer)['completion'])


def get_location(sd_prompt):
    model_id = "stability.stable-diffusion-xl-v0"
    accept = "application/json"
    content_type = "application/json"

    # 10回の繰り返しを実行
    body = json.dumps({
        "text_prompts": [
            {
                "text": sd_prompt['prompt'],
                "weight": 1.0
            },
            {
                "text": sd_prompt['negativePrompt'],
                "weight": -1.0
            }
        ],
        "cfg_scale": 10,
        "seed": 20,
        "steps": 50
    })

    response = bedrock_runtime_client.invoke_model(
        body=body, modelId=model_id, accept=accept, contentType=content_type
    )
    response_body = json.loads(response.get("body").read())
    print(response_body['result'])

    # 取得した画像データのデコード
    encoded_png_data = response_body.get("artifacts")[0].get("base64")
    decoded_png_data = base64.b64decode(encoded_png_data)

    # ファイル名の付与
    now = datetime.datetime.now()
    formatted_date = now.strftime('%y%m%d-%H%M%S%f')[:-4]
    file_name = f"output-{formatted_date}.png"

    # S3バケットへ出力
    s3.put_object(Bucket=os.getenv('BUCKET_NAME'),
                  Key=file_name,
                  Body=decoded_png_data,
                  ContentType="image/png")

    # 署名つきURLにするとサムネが見えません
    # header_location = s3.generate_presigned_url(
    #     ClientMethod='get_object',
    #     Params={'Bucket': os.getenv('BUCKET_NAME'), 'Key': file_name},
    #     ExpiresIn=3600,
    #     HttpMethod='GET'
    # )
    #
    # return {"Location": header_location}
    return 'https://{0}.s3.amazonaws.com/{1}'.format(os.getenv('BUCKET_NAME'), file_name)


# Lambda のハンドラー関数
def lambda_handler(event, context):
    if 'AppsheetBot' not in event['headers']['user-agent']:
        return {
            'statusCode': 401,
            'body': json.dumps('401 Unauthorized')
        }
    print(event)

    # sd_prompt = get_sd_prompt("ラーメンを食べる猫")
    sd_prompt = get_sd_prompt(json.loads(event['body'])['user_prompt'])
    location = get_location(sd_prompt)

    result = {
        'statusCode': 200,
        'body': {'completion': location}
    }
    print(result)
    return result
