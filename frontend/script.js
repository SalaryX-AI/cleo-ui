let ws = null;
let sessionId = null;

const statusEl = document.getElementById('status');
const messagesEl = document.getElementById('chatMessages');
const inputEl = document.getElementById('userInput');
const sendBtn = document.getElementById('sendButton');

// Add message to chat
function addMessage(content, isBot = true) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isBot ? 'bot' : 'user'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    messagesEl.appendChild(messageDiv);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Update status
function updateStatus(message, type = 'info') {
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
}

// Send message
function sendMessage() {
    const message = inputEl.value.trim();
    if (!message || !ws) return;
    
    addMessage(message, false);
    
    ws.send(JSON.stringify({
        type: 'user_message',
        content: message
    }));
    
    inputEl.value = '';
    inputEl.disabled = true;
    sendBtn.disabled = true;
}

// Initialize session and connect
async function initChat() {
    try {
        // Create session
        const response = await fetch('http://localhost:8000/start-session', {
            method: 'POST'
        });
        const data = await response.json();
        sessionId = data.session_id;
        
        // Connect WebSocket
        ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
        
        ws.onopen = () => {
            updateStatus('Connected', 'connected');
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'ai_message') {
                addMessage(data.content, true);
                inputEl.disabled = false;
                sendBtn.disabled = false;
                inputEl.focus();
            } 
            else if (data.type === 'workflow_complete') {
                updateStatus('Screening Complete', 'info');
                inputEl.disabled = true;
                sendBtn.disabled = true;
                
                const summary = data.summary;
                addMessage(
                    `✅ Screening completed!\nCandidate: ${summary.name}\nScore: ${summary.total_score}/${summary.max_score}`,
                    true
                );
            }
            else if (data.type === 'error') {
                updateStatus('Error occurred', 'disconnected');
                addMessage(`Error: ${data.message}`, true);
            }
        };
        
        ws.onerror = () => {
            updateStatus('Connection error', 'disconnected');
        };
        
        ws.onclose = () => {
            updateStatus('Disconnected', 'disconnected');
            inputEl.disabled = true;
            sendBtn.disabled = true;
        };
        
    } catch (error) {
        updateStatus('Failed to connect', 'disconnected');
        console.error('Connection error:', error);
    }
}

// Event listeners
sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Start chat on load
initChat();