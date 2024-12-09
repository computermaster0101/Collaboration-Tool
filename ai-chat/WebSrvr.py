import secrets
import string
import threading
import os
import time

from flask import Flask, request, send_from_directory, session
from flask_session import Session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from datetime import datetime

from MyOpenAI import MyOpenAI
from BedrockHandler import Claude
from GeminiHandler import MyGemini

from ConversationHandler import ConversationHandler

class WebSrvr:
    def __init__(self, host='127.0.0.1', port=3004):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        self.app.config['SESSION_TYPE'] = 'filesystem'  

        load_dotenv()
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        self.gemini_api_key =os.environ.get ('GEMINI_API_KEY')
        self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_session_token = os.environ.get('AWS_SESSION_TOKEN')
        self.aws_execution_env = os.environ.get('AWS_EXECUTION_ENV')  # AWS ECS sets this variable
        
        self.set_aws_credentials()
        self.openai = MyOpenAI(self.openai_api_key)
        self.claude = Claude(self.aws_access_key_id, self.aws_secret_access_key, self.aws_session_token)
        self.gemini = MyGemini(self.gemini_api_key)
        
        Session(self.app)
        self.host = host
        self.port = port
        self.socketio = SocketIO(self.app)

        self.conversations = ConversationHandler()
        self.static_coversation_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        self.claude_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_id}-claude')
        self.gemini_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_id}-gemini')
        self.openai_conversation_id = self.conversations.create_conversation(f'{self.static_coversation_id}-openai')
        self.connected_users = {}
        
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
            client_id = request.sid
            session['client_id'] = client_id
            username = f"user_{secrets.randbelow(9000) + 1000}"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.connected_users[client_id] = username
            history = {
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

            self.socketio.emit('message', message_object, include_self=False)
            self.socketio.emit('history', history, room=client_id)
            self.socketio.emit('welcome', connected_user, room=client_id)
            self.conversations.add_message(self.claude_conversation_id, message_object)
            self.conversations.add_message(self.gemini_conversation_id, message_object)
            self.conversations.add_message(self.openai_conversation_id, message_object)
            print(f"Client connected: {client_id} as {username}")

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
                self.socketio.emit('message', message_object)
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)
                print(f"Client disconnected: {client_id} ({username})")

        @self.socketio.on('reset')
        def reset():
            client_id = session.get('client_id')
            self.conversations.reset_conversation(self.claude_conversation_id)
            self.conversations.reset_conversation(self.gemini_conversation_id)
            self.conversations.reset_conversation(self.openai_conversation_id)
            self.socketio.emit('reset')
            print("Reset chats")
                
        @self.socketio.on('request')
        def getResponse(request):
            client_id = session.get('client_id')
            print("Received chat query:", request)
            print("Received chat query:", request['message'])  
            if client_id in self.connected_users:
                username = self.connected_users[client_id]
                message_object = {
                    'username': username,
                    'message': request['message'],
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                self.conversations.add_message(self.claude_conversation_id, message_object)
                self.conversations.add_message(self.gemini_conversation_id, message_object)
                self.conversations.add_message(self.openai_conversation_id, message_object)
                self.socketio.emit('message', message_object)

            if request['message'].lower() in ["", "hi", "hello", "hey"]: 
                echo_start_time = time.time()  
                echo_end_time = time.time()  
                echo_time_taken = echo_start_time - echo_end_time
                self.socketio.emit('reply', {
                    'username': 'System', 
                    'response': f"{echo_time_taken}s<br>{request['message']}",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            else:
                self.socketio.emit('thinking',{
                    'username': 'System',
                    'response': "One moment I'm thinking...",
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                def process_claude():
                    claude_start_time = time.time()  
                    claude_conversation = self.conversations.get_conversation(self.claude_conversation_id)
                    claude_response = self.claude.process_message(request, claude_conversation)
                    self.conversations.add_message(self.claude_conversation_id, claude_response)
                    self.conversations.trunctate_history(self.claude_conversation_id)
                    claude_end_time = time.time()
                    claude_time_taken = claude_end_time - claude_start_time
                    self.socketio.emit('reply', {
                        'username': 'Claude', 
                        'response': f"{claude_time_taken}s<br>{claude_response}",
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                def process_gemini():
                    gemini_start_time = time.time()
                    gemini_coversation = self.conversations.get_conversation(self.gemini_conversation_id)
                    gemini_response = self.gemini.get_response(f"{request['system_prompt']}{request['message']}")
                    self.conversations.add_message(self.gemini_conversation_id, gemini_response)
                    self.conversations.trunctate_history(self.gemini_conversation_id)
                    gemini_end_time = time.time()
                    gemini_time_taken = gemini_end_time - gemini_start_time
                    self.socketio.emit('reply', {
                        'username': 'Gemini', 
                        'response': f"{gemini_time_taken}s<br>{gemini_response}",
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                def process_openai():
                    openai_start_time = time.time()        
                    openai_conversation = self.conversations.get_conversation(self.openai_conversation_id)
                    openai_response = self.openai.process_message(request, openai_conversation)
                    self.conversations.add_message(self.openai_conversation_id, openai_response)
                    self.conversations.trunctate_history(self.openai_conversation_id)
                    openai_end_time = time.time()
                    openai_time_taken = openai_end_time - openai_start_time
                    self.socketio.emit('reply', {
                        'username': 'OpenAI', 
                        'response': f"{openai_time_taken}s<br>{openai_response}",
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
    print("Initializing EvalAI")
    MyWebSrvr = WebSrvr(host=HOST, port=PORT)
    print("Starting EvalAI")
    MyWebSrvr.run()
