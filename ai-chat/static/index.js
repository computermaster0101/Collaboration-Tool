const socket = io.connect()

const sendButton = document.getElementById('send-btn')
const resetButton = document.getElementById('reset-btn')
const messageInput = document.getElementById('message-input');

const chatClaude = document.getElementById('chat-messages1')
const chatGemini = document.getElementById('chat-messages2')
const chatOpenai = document.getElementById('chat-messages3')

const tempInput = document.getElementById('temp')
const topPInput = document.getElementById('top_p')
const maxTokenInput = document.getElementById('max_token')
const systemPromptInput = document.getElementById('paragraphInput')

function addMessage(sender, message, timestamp, className = "") {
    const messageElement = document.createElement('div');
    messageElement.innerHTML = `<p><span class="timestamp">[${timestamp}]</span> <strong>${sender}:</strong> ${message}</p>`;
    if (className) {
        messageElement.classList.add(className);
    }
    if (sender === 'OpenAI') {
        const chatOpenaiMessage = messageElement.cloneNode(true);
        chatOpenai.appendChild(chatOpenaiMessage);
        chatOpenai.scrollTop = chatOpenai.scrollHeight;
    } else if (sender === 'Claude') {
        const chatClaudeMessage = messageElement.cloneNode(true);
        chatClaude.appendChild(chatClaudeMessage);
        chatClaude.scrollTop = chatClaude.scrollHeight;
    } else if (sender === 'Gemini') {
        const chatGeminiMessage = messageElement.cloneNode(true);
        chatGemini.appendChild(chatGeminiMessage);
        chatGemini.scrollTop = chatGemini.scrollHeight;
    } else {
        const chatClaudeMessage = messageElement.cloneNode(true);
        const chatGeminiMessage = messageElement.cloneNode(true);
        const chatOpenaiMessage = messageElement.cloneNode(true);

        chatClaude.appendChild(chatClaudeMessage);
        chatGemini.appendChild(chatGeminiMessage);
        chatOpenai.appendChild(chatOpenaiMessage);
        
        chatClaude.scrollTop = chatClaude.scrollHeight;
        chatGemini.scrollTop = chatGemini.scrollHeight;
        chatOpenai.scrollTop = chatOpenai.scrollHeight;
    } 
}

function sendMessage() {
    const message = messageInput.value.trim();
    const temp = tempInput.value;
    const top_p = topPInput.value;
    const max_token = maxTokenInput.value;
    const system_prompt = systemPromptInput.value;

    if (message !== '') {
        messageInput.value = '';
        socket.emit('request', {
            message: message, 
            temp: temp, 
            top_p: top_p, 
            max_tokens: max_token, 
            system_prompt: system_prompt
        });
    }
}

function resetChats() {
    chatClaude.innerHTML = "<div><strong>System:</strong> Chat Reset!</div>"; 
    chatGemini.innerHTML = "<div><strong>System:</strong> Chat Reset!</div>"; 
    chatOpenai.innerHTML = "<div><strong>System:</strong> Chat Reset!</div>"; 
    socket.emit('reset')
}

socket.off('welcome');
socket.on('welcome', function(data){
    const { username, timestamp } = data;
    const userInfo = document.querySelector('.user-info');
    userInfo.innerHTML = `Connected as <strong>${username}</strong> at <strong>${timestamp}</strong>`;
    addMessage('System', `Welcome, ${username}!`, timestamp);
});

socket.off('message');
socket.on('message', function(data){
    addMessage(data.username, data.message, data.timestamp);
});

socket.off('reset');
socket.on('reset', function(){
    chatClaude.innerHTML = "<div><strong>System:</strong> Chat has been reset!</div>";
    chatGemini.innerHTML = "<div><strong>System:</strong> Chat has been reset!</div>";
    chatOpenai.innerHTML = "<div><strong>System:</strong> Chat has been reset!</div>";
});

socket.off('history');
socket.on('history', function(data){
    const history = data.claude.concat(data.gemini).concat(data.openai);
    const uniqueHistory = Array.from(new Set(history.map(JSON.stringify))).map(JSON.parse);
    uniqueHistory.forEach(function(message) {
        addMessage(message.username, message.message, message.timestamp);
    });
});

socket.off('reply');
socket.on('reply', function(response){
    removeThinkingMessage(response.username);
    addMessage(response.username, response.response, response.timestamp);
});

socket.on('thinking', function(response){
    addMessage('System', `${response.response} <span class="spinner"></span>`, response.timestamp, 'thinking-message');
});

function removeThinkingMessage(llm) {
    if (llm === 'Claude') {
        const thinkingMessagesClaude = chatClaude.getElementsByClassName('thinking-message');
        while (thinkingMessagesClaude.length > 0) {
            thinkingMessagesClaude[0].remove();
        }
    } else if (llm === 'Gemini') {
        const thinkingMessagesGemini = chatGemini.getElementsByClassName('thinking-message');
        while (thinkingMessagesGemini.length > 0) {
            thinkingMessagesGemini[0].remove();
        }
    } else if (llm === 'OpenAI') {
        const thinkingMessagesOpenAI = chatOpenai.getElementsByClassName('thinking-message');
        while (thinkingMessagesOpenAI.length > 0) {
            thinkingMessagesOpenAI[0].remove();
        }
    }
}

function openPrompt() {
    document.getElementById('overlay').style.display = 'block';
    document.getElementById('popup').style.display = 'block';
}

function hidePopup() {
    document.getElementById('overlay').style.display = 'none';
    document.getElementById('popup').style.display = 'none';
}

sendButton.addEventListener('click',sendMessage)
resetButton.addEventListener('click', resetChats)
messageInput.addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      sendMessage();
    }
  });