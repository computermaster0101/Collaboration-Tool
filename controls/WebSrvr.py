import secrets
import string

from flask import Flask, request, send_from_directory, session
from flask_cors import CORS
from flask_session import Session
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

class WebSrvr:
    def __init__(self, host='127.0.0.1', port=3006):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        self.app.config['SESSION_TYPE'] = 'filesystem'
        load_dotenv()
        
        Session(self.app)
        CORS(self.app, resources={r"/*": {"origins": "http://localhost:3000"}})

        self.host = host
        self.port = port
        self.socketio = SocketIO(self.app, cors_allowed_origins="http://localhost:3000")
        self.connected_users = {}
        self.active_mode = None  # Variable to store the active mode

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

        # Handle user connection
        @self.socketio.on('connect')
        def handle_connect():
            client_id = request.sid
            session['client_id'] = client_id
            username = f"user_{secrets.randbelow(9000) + 1000}"
            self.connected_users[client_id] = username
            print(f"Client connected: {client_id} ({username})")
            
            # Send the current active mode to the newly connected client
            if self.active_mode:
                emit('toggle', {'mode': self.active_mode}, to=client_id)

        # Handle user disconnection
        @self.socketio.on('disconnect')
        def handle_disconnect():
            client_id = session.get('client_id')
            if client_id in self.connected_users:
                username = self.connected_users.pop(client_id)
                print(f"Client disconnected: {client_id} ({username})")

        # Handle toggle event
        @self.socketio.on('toggle')
        def handle_toggle(data):
            client_id = request.sid
            mode = data.get('mode')
            
            if mode:
                print(f"Toggle mode requested by {client_id}: {mode}")
                self.active_mode = mode  # Update the active mode
                
                # Broadcast to all clients except the sender
                emit('toggle', {'mode': mode}, broadcast=True, include_self=False)

    def run(self):
        print(f"Running Flask app on {self.host}:{self.port}")
        self.socketio.run(self.app, host=self.host, port=self.port, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 3006
    print("Initializing user chat")
    MyWebSrvr = WebSrvr(host=HOST, port=PORT)
    print("Starting user chat")
    MyWebSrvr.run()
