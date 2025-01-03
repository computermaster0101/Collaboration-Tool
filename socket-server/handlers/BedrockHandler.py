import re
import json
import boto3

debug = False

class Claude:
    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, session_token=None):
        self.region = 'us-east-1'
        self.session = boto3.Session(
            region_name=self.region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=session_token
        )
        self.bedrock = self.session.client('bedrock')
        self.bedrock_runtime = self.session.client('bedrock-runtime')
        self.model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'


    def format_conversation(self, conversation):
        print("Claude.format_conversation") if debug else None
        formattedConversation = []
        for message in conversation:
            if message['username'] == 'System':
                continue
            elif message['username'] == 'Claude':
                formattedConversation.append({'role': 'assistant', 'content': f"{message['message']}"})
            else:
                formattedConversation.append({'role': 'user', 'content': f"{message['username']}: {message['message']}"})
        
        return formattedConversation
        
    def get_response(self, request):
        print("Claude.get_response") if debug else None
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": request['system_prompt'],
                "messages": request['messages'],
                "max_tokens": int(request['max_tokens']),
                "temperature": float(request['temperature'])
            }

            # The actual call to retrieve an answer from the model
            response = self.bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )
            
            response_body = response['body'].read().decode('utf-8')
            response_text = json.loads(response_body)['content'][0]['text']
            response_text = re.sub(r'\*.*?\*', '', response_text)
            answer = response_text

        except Exception as e:
            print("An error occurred:", e)
            answer = "An error occurred: {}".format(e)

        return answer

    def get_audio(self, text, file_name="/tmp/openai_audio.mp3"):
        print("Claude.get_audio") if debug else None

    def clean_response(self, response):
        print("Claude.clean_response") if debug else None
    
    def process_message(self, request, conversation):
        print("Claude.process_message") if debug else None
        system_prompt = request['system_prompt']
        temp = request['temp']
        top_p = request['top_p']
        max_tokens = request['max_tokens']
        formatted_conversation = self.format_conversation(conversation)
        response = self.get_response({'system_prompt': system_prompt, 'messages': formatted_conversation, 'max_tokens': max_tokens, 'temperature': temp, 'top_p': top_p})
        return response