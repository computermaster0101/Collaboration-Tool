import secrets
import string
import os
import asyncio
import base64
from datetime import datetime
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from socketio import AsyncServer, ASGIApp

from tools.computer import ComputerTool
from handlers.bedrock import Claude
from handlers.conversation import ConversationHandler

class AIControlServer:
    def __init__(self, host='127.0.0.1', port=3003):      
        load_dotenv()
        
        # Load AWS credentials
        self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_session_token = os.environ.get('AWS_SESSION_TOKEN')
        
        # Initialize Claude
        self.claude = Claude(self.aws_access_key_id, self.aws_secret_access_key, self.aws_session_token)
        
        # Initialize computer control
        self.computer = ComputerTool()
        
        # Initialize FastAPI and Socket.IO
        self.app = FastAPI()
        self.sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*', ping_interval=60)
        self.socket_app = ASGIApp(self.sio)
        self.app.mount("/socket.io", self.socket_app)
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        
        self.host = host
        self.port = port

        # Track state
        self.connected_users = {}
        self.active_mode = None 
        self.draw_status = False
        self.conversations = ConversationHandler()

        # Create conversation channels
        self.static_conversation_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
        self.users_conversation_id = self.conversations.create_conversation(f'{self.static_conversation_key}-users')
        self.claude_conversation_id = self.conversations.create_conversation(f'{self.static_conversation_key}-claude')

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
                # Parse connection headers
                headers = environ.get('asgi.scope', {}).get('headers', [])
                cookie_header = None
                for name, value in headers:
                    if name.decode('utf-8').lower() == 'cookie':
                        cookie_header = value.decode('utf-8')
                        break

                username = None
                if cookie_header:
                    cookies = dict(cookie.split('=') for cookie in cookie_header.split('; '))
                    username = cookies.get('username')

                if not username:
                    username = f"user_{secrets.randbelow(9000) + 1000}"
                    await self.sio.emit('set_username_cookie', {'username': username}, room=client_id)

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.connected_users[client_id] = username

                # Send connection history
                history = {
                    'users': self.conversations.get_conversation(self.users_conversation_id),
                    'claude': self.conversations.get_conversation(self.claude_conversation_id)
                }
                
                # Send welcome messages
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
                
                # Store in conversation channels
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)

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
                
                # Store disconnect message
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)
                
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
        async def computerAction(client_id, data):
            if client_id in self.connected_users:
                action = data.get('action')
                if not action:
                    return
                    
                try:
                    result = await self.computer(
                        action=action,
                        text=data.get('text'),
                        coordinate=data.get('coordinate')
                    )
                    
                    message = {
                        'username': 'Computer',
                        'message': f"Action '{action}' completed successfully",
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    if result.output:
                        message['message'] = result.output
                    if result.base64_image:
                        message['image'] = result.base64_image
                        
                    await self.sio.emit('computerResult', message)
                    
                except Exception as e:
                    error_message = {
                        'username': 'Computer Error',
                        'message': str(e),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    await self.sio.emit('computerError', error_message)

        @self.sio.event
        async def aiPrompt(client_id, data):
            if client_id in self.connected_users:
                username = self.connected_users[client_id]
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Create prompt message object
                message_object = {
                    'username': username,
                    'message': data['message'],
                    'timestamp': timestamp
                }
                
                # Store in Claude channel and emit
                self.conversations.add_message(self.claude_conversation_id, message_object)
                await self.sio.emit('aiMessage', message_object)
                
                # Emit thinking message
                await self.sio.emit('aiPending', {
                    'username': 'System',
                    'message': "One moment I'm thinking...",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                # Process with Claude
                try:
                    claude_response = await self.claude.process_message(
                        data, 
                        self.conversations.get_conversation(self.claude_conversation_id)
                    )
                    claude_message = {
                        'username': 'Claude',
                        'message': claude_response,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    await self.sio.emit('aiResponse', claude_message)
                    self.conversations.add_message(self.claude_conversation_id, claude_message)
                except Exception as e:
                    print(f"Claude Error: {e}")

def create_app():
    server = AIControlServer()
    return server.app

if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=3003)
