import secrets
import string

from flask import Flask, request, send_from_directory, session
from flask_session import Session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from datetime import datetime

from ConversationHandler import ConversationHandler

class WebSrvr:
    def __init__(self, host='127.0.0.1', port=3005):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        self.app.config['SESSION_TYPE'] = 'filesystem'
        load_dotenv()
        
        Session(self.app)
        self.host = host
        self.port = port
        self.socketio = SocketIO(self.app)

        self.conversations = ConversationHandler()
        self.static_coversation_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        self.conversation_id = self.conversations.create_conversation(self.static_coversation_id)
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

        @self.socketio.on('connect')
        def handle_connect():
            client_id = request.sid
            session['client_id'] = client_id
            username = f"user_{secrets.randbelow(9000) + 1000}"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.connected_users[client_id] = username

            history=self.conversations.get_conversation(self.conversation_id)
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
   
            self.conversations.add_message(self.conversation_id, message_object)
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
                self.conversations.add_message(self.conversation_id, message_object)
                print(f"Client disconnected: {client_id} ({username})")

        @self.socketio.on('message')
        def handle_message(data):
            client_id = session.get('client_id')
            if client_id in self.connected_users:
                username = self.connected_users[client_id]
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_object = {
                    'username': username,
                    'message': data['message'],
                    'timestamp': timestamp
                }
                self.conversations.add_message(self.conversation_id, message_object)
                self.socketio.emit('message', message_object)

        @self.socketio.on('reset')
        def reset():
            self.conversations.reset_conversation(self.conversation_id)
            self.socketio.emit('reset')
            print("Reset chats")

    def run(self):
        print(f"Running Flask app on {self.host}:{self.port}")
        self.socketio.run(self.app, host=self.host, port=self.port, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 3005
    print("Initializing user chat")
    MyWebSrvr = WebSrvr(host=HOST, port=PORT)
    print("Starting user chat")
    MyWebSrvr.run()
