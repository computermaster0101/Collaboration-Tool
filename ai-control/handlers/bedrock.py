import boto3
from typing import Dict, List, Any

class Claude:
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, aws_session_token: str = None):
        session = boto3.Session(
            region_name="us-east-1",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token
        )
        self.client = session.client('bedrock-runtime')
        self.model = "anthropic.claude-3-sonnet-20240229-v1:0"

    async def process_message(self, data: Dict[str, Any], conversation: List[Dict[str, Any]]) -> str:
        messages = []
        for msg in conversation:
            role = "assistant" if msg["username"] == "Claude" else "user"
            messages.append({
                "role": role,
                "content": msg["message"]
            })

        response = self.client.invoke_model(
            modelId=self.model,
            body={"messages": messages}
        )
        return response['body']['choices'][0]['message']['content']
