import eventlet
eventlet.monkey_patch()

import secrets
import string
import threading
import os
import time

from flask import Flask, request, send_from_directory, session
from flask_session import Session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime

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
        
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        self.app.config['SESSION_TYPE'] = 'filesystem'
        Session(self.app)
        CORS(self.app, resources={r"/*": {"origins": "*"}})

        self.host = host
        self.port = port
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        self.connected_users = {}
        self.active_mode = None 
        self.conversations = ConversationHandler()

        self.static_coversation_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
        self.users_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_key}-users')
        self.claude_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_key}-claude')
        self.gemini_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_key}-gemini')
        self.openai_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_key}-openai')

        @self.app.route('/')
        def index():
            return send_from_directory('static', 'index.html')

        @self.app.route('/index.js')
        def js():
            return send_from_directory('static', 'index.js')

        @self.app.route('/index.css')
        def css():
            return send_from_directory('static', 'index.css')

        @self.app.route('/favicon.ico')
        def favicon():
            return send_from_directory('static', 'favicon.ico')
        
        @self.app.route('/system_prompt.txt')
        def prompt():
            return send_from_directory('static', 'system_prompt.txt') 
        
        @self.socketio.on('connect')
        def handle_connect():
            try:
                client_id = request.sid
                session['client_id'] = client_id
                username = f"user_{secrets.randbelow(9000) + 1000}"
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
                    emit('toggle', {'mode': self.active_mode}, to=client_id)
                self.socketio.emit('history', history, room=client_id)
                self.socketio.emit('welcome', connected_user, room=client_id)
                self.socketio.emit('system-message', message_object, include_self=False)
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)

                print(f"Client connected: {client_id} as {username}") 
            except Exception as e:
                print(f"Error during connect: {e}")

        @self.socketio.on('disconnect')
        def handle_disconnect():
            client_id = session.get('client_id')
            if client_id in self.connected_users:
                username = self.connected_users.pop(client_id)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_object = {
                    'username': 'System',
                    'message': f"{username} has left the chat.",
                    'timestamp': timestamp
                }
                self.socketio.emit('system-message', message_object)
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)
                print(f"Client disconnected: {client_id} ({username})")

        @self.socketio.on('toggle')
        def handle_toggle(data):
            client_id = request.sid
            mode = data.get('mode')
            if mode:
                print(f"Toggle mode requested by {client_id}: {mode}")
                self.active_mode = mode
                emit('toggle', {'mode': mode}, broadcast=True, include_self=False)

        @self.socketio.on('user-message')
        def handle_user_message(data):
            client_id = session.get('client_id')
            if client_id in self.connected_users:
                username = self.connected_users[client_id]
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_object = {
                    'username': username,
                    'message': data['message'],
                    'timestamp': timestamp
                }
                self.conversations.add_message(self.users_conversation_id, message_object)
                self.socketio.emit('user-message', message_object)

        @self.socketio.on('ai-prompt')
        def handle_ai_prompt(data):
            client_id = session.get('client_id')
            print("Received chat query:", data)
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
                self.socketio.emit('ai-message', message_object)

            if data['message'].lower() in ["", "hi", "hello", "hey"]: 
                echo_start_time = time.time()  
                echo_end_time = time.time()  
                echo_time_taken = echo_start_time - echo_end_time
                self.socketio.emit('ai-message', {
                    'username': 'System', 
                    'message': f"{echo_time_taken}s<br>{data['message']}",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            else:
                self.socketio.emit('ai-pending',{
                    'username': 'System',
                    'message': "One moment I'm thinking...",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                def process_claude():
                    claude_start_time = time.time()  
                    claude_conversation = self.conversations.get_conversation(self.claude_conversation_id)
                    claude_response = self.claude.process_message(data, claude_conversation)
                    self.conversations.add_message(self.claude_conversation_id, claude_response)
                    self.conversations.trunctate_history(self.claude_conversation_id)
                    claude_end_time = time.time()
                    claude_time_taken = claude_end_time - claude_start_time
                    self.socketio.emit('ai-response', {
                        'username': 'Claude', 
                        'message': f"{claude_time_taken}s<br>{claude_response}",
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                def process_gemini():
                    gemini_start_time = time.time()
                    gemini_coversation = self.conversations.get_conversation(self.gemini_conversation_id)
                    gemini_response = self.gemini.get_response(f"{data['system_prompt']}{data['message']}")
                    self.conversations.add_message(self.gemini_conversation_id, gemini_response)
                    self.conversations.trunctate_history(self.gemini_conversation_id)
                    gemini_end_time = time.time()
                    gemini_time_taken = gemini_end_time - gemini_start_time
                    self.socketio.emit('ai-response', {
                        'username': 'Gemini', 
                        'message': f"{gemini_time_taken}s<br>{gemini_response}",
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                def process_openai():
                    openai_start_time = time.time()        
                    openai_conversation = self.conversations.get_conversation(self.openai_conversation_id)
                    openai_response = self.openai.process_message(data, openai_conversation)
                    self.conversations.add_message(self.openai_conversation_id, openai_response)
                    self.conversations.trunctate_history(self.openai_conversation_id)
                    openai_end_time = time.time()
                    openai_time_taken = openai_end_time - openai_start_time
                    self.socketio.emit('ai-response', {
                        'username': 'OpenAI', 
                        'message': f"{openai_time_taken}s<br>{openai_response}",
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                threads = []
                threads.append(threading.Thread(target=process_claude))
                threads.append(threading.Thread(target=process_gemini))
                threads.append(threading.Thread(target=process_openai))

                for thread in threads:
                    thread.start()

                for thread in threads:
                    thread.join()

        @self.socketio.on('reset-user-chat')
        def resetUserChat():
            self.conversations.reset_conversation(self.users_conversation_id)
            self.socketio.emit('reset-user-chat')
            print("Reset user chats")

        @self.socketio.on('reset-ai-chats')
        def resetAiChats():
            self.conversations.reset_conversation(self.claude_conversation_id)
            self.conversations.reset_conversation(self.gemini_conversation_id)
            self.conversations.reset_conversation(self.openai_conversation_id)
            self.socketio.emit('reset-ai-chats')
            print("Reset ai chats")


    def set_aws_credentials(self):
        if self.aws_execution_env:
            self.aws_access_key_id = None
            self.aws_secret_access_key = None

    def run(self):
        print(f"Running Flask app on {self.host}:{self.port}")
        self.socketio.run(self.app, host=self.host, port=self.port, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 3004
    print("Initializing server")
    MyWebSrvr = WebSrvr(host=HOST, port=PORT)
    print("Starting server")
    MyWebSrvr.run()
