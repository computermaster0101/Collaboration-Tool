const socket = io.connect();

const sendButton = document.getElementById('send-btn');
const resetButton = document.getElementById('reset-btn');
const messageInput = document.getElementById('message-input');
const chatContainer = document.getElementById('chat-messages');

function addMessage(sender, message, timestamp, className = "") {
    const messageElement = document.createElement('div');
    messageElement.innerHTML = `<p><span class="timestamp">[${timestamp}]</span> <strong>${sender}:</strong> ${message}</p>`;
    if (className) {
        messageElement.classList.add(className);
    }
    chatContainer.appendChild(messageElement);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function sendMessage() {
    const message = messageInput.value.trim();

    if (message !== '') {
        socket.emit('message', { message });
        messageInput.value = '';
    }
}

function resetChat() {
    chatContainer.innerHTML = `<div><strong>System:</strong> Chat Reset!</div>`;
    socket.emit('reset');
}
socket.off('welcome');
socket.on('welcome', function (data) {
    const { username, timestamp } = data;
    const chatHeader = document.querySelector('.chat-header');
    chatHeader.innerHTML = `Connected as <strong>${username}</strong> at <strong>${timestamp}</strong>`;
    addMessage('System', `Welcome, ${username}!`, timestamp);
});

socket.off('message');
socket.on('message', function (data) {
    addMessage(data.username, data.message, data.timestamp);
});

socket.off('reset');
socket.on('reset', function () {
    chatContainer.innerHTML = `<div><strong>System:</strong> Chat has been reset!</div>`;
});

socket.off('history');
socket.on('history', function (data) {
    data.forEach(function (item) {
        const { username, message, timestamp } = item; 
        addMessage(username, message, timestamp); 
    });
});

sendButton.addEventListener('click', sendMessage);
resetButton.addEventListener('click', resetChat);
messageInput.addEventListener('keypress', function (event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        sendMessage();
    }
});
