import google.generativeai as genai
from typing import Dict, List, Any

class MyGemini:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    async def process_message(self, data: Dict[str, Any], conversation: List[Dict[str, Any]]) -> str:
        messages = []
        for msg in conversation:
            role = "model" if msg["username"] == "Gemini" else "user"
            messages.append({
                "role": role,
                "parts": [msg["message"]]
            })

        chat = self.model.start_chat(history=messages)
        response = chat.send_message(data["message"])
        return response.text