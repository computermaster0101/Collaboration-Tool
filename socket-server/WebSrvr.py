import secrets
import string
import asyncio
import os
import time

from dotenv import load_dotenv
from datetime import datetime
from fastapi import FastAPI, Cookie, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from socketio import AsyncServer, ASGIApp

from MyOpenAI import MyOpenAI
from BedrockHandler import Claude
from GeminiHandler import MyGemini

from ConversationHandler import ConversationHandler

class WebSrvr:
    def __init__(self, host='127.0.0.1', port=3004):      
        load_dotenv()
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        self.gemini_api_key =os.environ.get ('GEMINI_API_KEY')
        self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_session_token = os.environ.get('AWS_SESSION_TOKEN')
        self.aws_execution_env = os.environ.get('AWS_EXECUTION_ENV') 
        
        self.set_aws_credentials()
        self.openai = MyOpenAI(self.openai_api_key)
        self.claude = Claude(self.aws_access_key_id, self.aws_secret_access_key, self.aws_session_token)
        self.gemini = MyGemini(self.gemini_api_key)
        
        self.app = FastAPI()
        self.sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*', ping_interval=60, ping_timeout=28800)
        self.socket_app = ASGIApp(self.sio)
        self.app.mount("/socket.io", self.socket_app)
        self.host = host
        self.port = port

        self.connected_users = {}
        self.active_mode = None 
        self.draw_status = False
        self.conversations = ConversationHandler()

        self.static_conversation_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
        self.users_conversation_id = self.conversations.create_conversation(f'{self.static_conversation_key}-users')
        self.claude_conversation_id = self.conversations.create_conversation(f'{self.static_conversation_key}-claude')
        self.gemini_conversation_id = self.conversations.create_conversation(f'{self.static_conversation_key}-gemini')
        self.openai_conversation_id = self.conversations.create_conversation(f'{self.static_conversation_key}-openai')

        self.setup_routes()
        self.setup_socket_events()

    def setup_routes(self):
        @self.app.get('/')
        async def index():
            return FileResponse('static/index.html')

        @self.app.get('/favicon.ico')
        async def favicon():
            return FileResponse('static/favicon.ico')
        
        @self.app.get('/system_prompt.txt')
        async def system_prompt():
            return FileResponse('static/system_prompt.txt') 
        
    def setup_socket_events(self):
        @self.sio.event
        async def connect(client_id, environ):
            try:
                # Check for username cookie in headers
                headers = environ.get('asgi.scope', {}).get('headers', [])
                cookie_header = None
                for name, value in headers:
                    if name.decode('utf-8').lower() == 'cookie':
                        cookie_header = value.decode('utf-8')
                        break

                username = None
                if cookie_header:
                    # Parse cookies manually since we can't use FastAPI's Cookie dependency here
                    cookies = dict(cookie.split('=') for cookie in cookie_header.split('; '))
                    username = cookies.get('username')

                if not username:
                    username = f"user_{secrets.randbelow(9000) + 1000}"
                    # Set cookie through socket.io
                    await self.sio.emit('set_username_cookie', {'username': username}, room=client_id)

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.connected_users[client_id] = username

                history = {
                    'users': self.conversations.get_conversation(self.users_conversation_id),
                    'claude': self.conversations.get_conversation(self.claude_conversation_id),
                    'gemini': self.conversations.get_conversation(self.gemini_conversation_id),
                    'openai': self.conversations.get_conversation(self.openai_conversation_id)
                }
                connected_user = {
                    'username': username,
                    'timestamp': timestamp
                }
                message_object = {
                    'username': 'System',
                    'message': f"{username} has joined the chat.",
                    'timestamp': timestamp
                }

                if self.active_mode:
                    await self.sio.emit('toggle', {'mode': self.active_mode}, to=client_id)
                if self.draw_status:
                    await self.sio.emit('toggleStatus', to=client_id)
                await self.sio.emit('history', history, room=client_id)
                await self.sio.emit('welcome', connected_user, room=client_id)
                await self.sio.emit('systemMessage', message_object, skip_sid=client_id)
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)

                print(f"Client connected: {client_id} as {username}") 
            except Exception as e:
                print(f"Error during connect: {e}")

        @self.sio.event
        async def disconnect(client_id):
            if client_id in self.connected_users:
                username = self.connected_users.pop(client_id)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_object = {
                    'username': 'System',
                    'message': f"{username} has left the chat.",
                    'timestamp': timestamp
                }
                await self.sio.emit('systemMessage', message_object)
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)
                print(f"Client disconnected: {client_id} ({username})")

        @self.sio.event
        async def toggle(client_id, data):
            mode = data.get('mode')
            if mode:
                print(f"Toggle mode requested by {client_id}: {mode}")
                self.active_mode = mode
                await self.sio.emit('toggle', {'mode': mode}, skip_sid=client_id)

        @self.sio.event
        async def toggleStatus(client_id):
            self.draw_status = not self.draw_status
            await self.sio.emit('toggleStatus', skip_sid=client_id)

        @self.sio.event
        async def userMessage(client_id, data):
            if client_id in self.connected_users:
                username = self.connected_users[client_id]
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_object = {
                    'username': username,
                    'message': data['message'],
                    'timestamp': timestamp
                }
                self.conversations.add_message(self.users_conversation_id, message_object)
                await self.sio.emit('userMessage', message_object)

        @self.sio.event
        async def aiPrompt(client_id, data):
            print("Received chat query:", data['message'])  

            if client_id in self.connected_users:
                username = self.connected_users[client_id]
                message_object = {
                    'username': username,
                    'message': data['message'],
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)
                await self.sio.emit('aiMessage', message_object)

            if data['message'].lower() in ["", "hi", "hello", "hey"]: 
                echo_start_time = time.time()  
                echo_end_time = time.time()  
                echo_time_taken = echo_start_time - echo_end_time
                await self.sio.emit('aiMessage', {
                    'username': 'System', 
                    'message': f"{echo_time_taken}s<br>{data['message']}",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            else:
                await self.sio.emit('aiPending',{
                    'username': 'System',
                    'message': "One moment I'm thinking...",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                async def process_claude():
                    try:
                        start_time = time.time()
                        conversation = self.conversations.get_conversation(self.claude_conversation_id)
                        response = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            self.claude.process_message, 
                            data, 
                            conversation
                        )
                        end_time = time.time()
                        response_message = {
                            'username': 'Claude',
                            'message': f"{end_time - start_time:.2f}s<br>{response}",
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        self.conversations.add_message(self.claude_conversation_id, response_message)
                        self.conversations.trunctate_history(self.claude_conversation_id)
                        await self.sio.emit('aiResponse', response_message)
                    except Exception as e:
                        print(f"Claude Error: {e}")

                async def process_gemini():
                    try:
                        start_time = time.time()
                        conversation = self.conversations.get_conversation(self.gemini_conversation_id)
                        response = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self.gemini.process_message,
                            data,
                            conversation
                        )
                        end_time = time.time()
                        response_message = {
                            'username': 'Gemini',
                            'message': f"{end_time - start_time:.2f}s<br>{response}",
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        self.conversations.add_message(self.gemini_conversation_id, response_message)
                        self.conversations.trunctate_history(self.gemini_conversation_id)
                        await self.sio.emit('aiResponse', response_message)
                    except Exception as e:
                        print(f"Gemini Error: {e}")

                async def process_openai():
                    try:
                        start_time = time.time()
                        conversation = self.conversations.get_conversation(self.openai_conversation_id)
                        response = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self.openai.process_message,
                            data,
                            conversation
                        )
                        response = self.openai.clean_response(response)
                        end_time = time.time()
                        response_message = {
                            'username': 'OpenAI',
                            'message': f"{end_time - start_time:.2f}s<br>{response}",
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        self.conversations.add_message(self.openai_conversation_id, response_message)
                        self.conversations.trunctate_history(self.openai_conversation_id)
                        await self.sio.emit('aiResponse', response_message)
                    except Exception as e:
                        print(f"OpenAI Error: {e}")

                # Launch all processes independently
                asyncio.create_task(process_claude())
                asyncio.create_task(process_gemini())
                asyncio.create_task(process_openai())


        @self.sio.event
        async def resetUserChat(client_id):
            self.conversations.reset_conversation(self.users_conversation_id)
            await self.sio.emit('resetUserChat')
            print("Reset user chats")

        @self.sio.event
        async def resetAiChats(client_id):
            self.conversations.reset_conversation(self.claude_conversation_id)
            self.conversations.reset_conversation(self.gemini_conversation_id)
            self.conversations.reset_conversation(self.openai_conversation_id)
            await self.sio.emit('resetAiChats')
            print("Reset ai chats")


    def set_aws_credentials(self):
        if self.aws_execution_env:
            self.aws_access_key_id = None
            self.aws_secret_access_key = None

    def run(self):
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port)

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 3004
    print("Initializing server")
    server = WebSrvr(host=HOST, port=PORT)
    print("Starting server")
    server.run()