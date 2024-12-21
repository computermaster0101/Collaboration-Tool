from typing import Dict, List, Any
import openai

class MyOpenAI:
    def __init__(self, api_key: str):
        self.client = openai.Client(api_key=api_key)
        self.model = "gpt-4"

    async def process_message(self, data: Dict[str, Any], conversation: List[Dict[str, Any]]) -> str:
        messages = []
        for msg in conversation:
            role = "assistant" if msg["username"] == "OpenAI" else "user"
            messages.append({
                "role": role,
                "content": msg["message"]
            })

        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return completion.choices[0].message.content