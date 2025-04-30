import json
import os
import re  # 正規表現モジュールをインポート
import urllib.request  # API呼び出し用
from botocore.exceptions import ClientError

# === MODIFIED ===
# 環境変数名を修正し、FastAPIのベースURLを取得
FASTAPI_URL = os.environ["https://f7b6-35-185-129-175.ngrok-free.app"].rstrip('/')

# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値

## グローバル変数としてクライアントを初期化（初期値）
#bedrock_client = None

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))

        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")

        # リクエストボディの解析
        body = json.loads(event.get('body', '{}'))
        message = body['message']
        conversation_history = body.get('conversationHistory', [])

        print("Processing message:", message)

        # 会話履歴を使用
        # 過去履歴を "[role]: content" の形で連結
        history_prompts = []
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_prompts.append(f"[{role}] {content}")
        # ユーザーメッセージを追加
        history_prompts.append(f"[user] {message}")
        prompt_text = "\n".join(history_prompts)

        # FastAPI LLMモデル用のペイロードを構築
        payload = {
            "prompt": prompt_text,
            "max_new_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.9,
            "do_sample": True
        }
        data = json.dumps(payload).encode("utf-8")

        # FastAPI の /generate エンドポイントを呼び出し
        url = f"{FASTAPI_URL}/generate"
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
        result = json.loads(resp_body)
        print("FastAPI response:", result)

        # 応答テキストを取得
        assistant_response = result.get("generated_text")

        # 会話履歴にアシスタント応答を追加
        messages = conversation_history.copy()
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })

        # 成功レスポンスを返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }

    except Exception as error:
        print("Error:", str(error))
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
