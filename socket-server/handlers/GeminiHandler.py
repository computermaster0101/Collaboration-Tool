import google.generativeai as genai

class MyGemini:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def format_conversation(self, system_prompt, conversation):
        formattedConversation = []
        formattedConversation.append({'role': 'user', 'parts': f"{system_prompt}"})
        for message in conversation:
            if message['username'] == 'System':
                continue
            elif message['username'] == 'Gemini':
                formattedConversation.append({'role': 'model', 'parts': f"{message['message']}"})
            else:
                formattedConversation.append({'role': 'user', 'parts': f"{message['username']}: {message['message']}"})
        return formattedConversation
     
    def get_response(self, request):
        history = request['messages'][:-1]
        current_message = request['messages'][-1]['parts']
        chat = self.model.start_chat(history=history)
        response = chat.send_message(current_message, stream=False)
        for candidate in response._result.candidates:
            generated_text = candidate.content.parts[0].text
            return generated_text   
    
    def process_message(self, request, conversation):
        system_prompt = request['system_prompt']
        temp = request['temp']
        top_p = request['top_p']
        max_tokens = request['max_tokens']
        formatted_conversation = self.format_conversation(system_prompt, conversation)
        response = self.get_response({'messages': formatted_conversation})
        return response
