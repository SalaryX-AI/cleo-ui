(function(window) {
    'use strict';
    
    // Configuration for the chatbot API endpoints
    const CHATBOT_CONFIG = {
        apiBaseUrl: window.apiBaseUrl,
        wsBaseUrl: window.wsBaseUrl
    };
    
    const CleoChatbot = {
        config: null,
        ws: null,
        sessionId: null,
        isOpen: false,
        
        /**
         * Initialize the chatbot with validated configuration
         * This is called internally after server validation
         */
        init: function(options) {
            if (!options.jobID || !options.apiKey) {
                console.error('CleoChatbot: jobID and apiKey are required');
                return;
            }
            
            // Load external CSS
            this.loadCSS();
            
            // Store configuration
            this.config = {
                jobID: options.jobID,
                apiKey: options.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl,
                position: 'bottom-right',
                primaryColor: '#667eea'
            };
            
            // Create the chat widget UI
            this.createWidget();
        },
        
        /**
         * Load external CSS file
         */
        loadCSS: function() {
            // Check if CSS is already loaded
            if (document.getElementById('cleo-typography-css')) {
                return;
            }
            
            const link = document.createElement('link');
            link.id = 'cleo-typography-css';
            link.rel = 'stylesheet';
            link.type = 'text/css';
            link.href = `${CHATBOT_CONFIG.apiBaseUrl}/cleo-typography.css`; // Use backend URL
            document.head.appendChild(link);
        },
        
        createWidget: function() {
            // Create widget button
            const widgetBtn = document.createElement('div');
            widgetBtn.id = 'cleo-widget-button';
            widgetBtn.innerHTML = '💬';
            
            const positions = {
                'bottom-right': 'bottom: 20px; right: 20px;',
                'bottom-left': 'bottom: 20px; left: 20px;'
            };
            
            // Position still needs to be inline (dynamic)
            widgetBtn.style.cssText = `
                position: fixed;
                ${positions[this.config.position]}
            `;
            
            widgetBtn.addEventListener('click', () => this.toggleChat());
            
            document.body.appendChild(widgetBtn);
            
            // Create chat container (hidden initially)
            this.createChatUI();
        },
        
        createChatUI: function() {
            const chatContainer = document.createElement('div');
            chatContainer.id = 'cleo-chat-container';
            chatContainer.className = 'chat-container';
            
            const positions = {
                'bottom-right': 'bottom: 90px; right: 20px;',
                'bottom-left': 'bottom: 90px; left: 20px;'
            };
            
            // Position and size need to be inline (dynamic)
            chatContainer.style.cssText = `
                position: fixed;
                ${positions[this.config.position]}
                width: 500px;
                height: 500px;
                border-radius: 16px;
                box-shadow: 0 12px 48px rgba(0,0,0,0.3);
                z-index: 999998;
                display: none;
                animation: slideUp 0.3s ease-out;
            `;
            
            chatContainer.innerHTML = `
                <div style="height: 100%; display: flex; flex-direction: column; background: white; border-radius: 16px; overflow: hidden;">
                    <!-- Header -->
                    <div id="cleo-chat-header">
                        <div style="flex: 1;">
                            <div class="title">Cleo Assistant</div>
                            <div id="chatbot-status-text" class="status">Connecting...</div>
                        </div>
                        <button id="cleo-close-btn">×</button>
                    </div>
                    
                    <!-- Messages Area -->
                    <div id="chatbot-messages"></div>
                    
                    <!-- Input Area -->
                    <div style="padding: 16px; background: white; border-top: 1px solid #e5e7eb; display: flex; gap: 10px; align-items: center;">
                        <input type="text" id="chatbot-input" placeholder="Type your message..." disabled>
                        <button id="chatbot-send" disabled>Send</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(chatContainer);
            
            // Add event listeners
            document.getElementById('cleo-close-btn').addEventListener('click', () => this.closeChat());
            document.getElementById('chatbot-send').addEventListener('click', () => this.sendMessage());
            document.getElementById('chatbot-input').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendMessage();
            });
        },
        
        toggleChat: function() {
            if (this.isOpen) {
                this.closeChat();
            } else {
                this.openChat();
            }
        },
        
        openChat: function() {
            const chatContainer = document.getElementById('cleo-chat-container');
            chatContainer.style.display = 'block';
            this.isOpen = true;
            
            // Start chat if not already started
            if (!this.sessionId) {
                this.startChat();
            }
        },
        
        closeChat: function() {
            const chatContainer = document.getElementById('cleo-chat-container');
            chatContainer.style.display = 'none';
            this.isOpen = false;
        },
        
        /**
         * Start a new chat session with the server
         * Creates session and establishes WebSocket connection
         */
        async startChat() {
            try {
                this.updateStatus('Connecting...', 'connecting');

                const params = new URLSearchParams(window.location.search);
                const location = params.get("location") || "unknown";
                
                const response = await fetch(
                    `${this.config.apiUrl}/start-session?job_id=${this.config.jobID}&api_key=${this.config.apiKey}&location=${location}`,
                    { method: 'POST' }
                );
                
                if (!response.ok) {
                    throw new Error('Failed to start session');
                }
                
                const data = await response.json();
                this.sessionId = data.session_id;
                
                this.ws = new WebSocket(`${this.config.wsUrl}/ws/${this.sessionId}`);
                
                this.ws.onopen = () => {
                    this.updateStatus('Online', 'connected');
                    this.enableInput();
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };
                
                this.ws.onerror = () => {
                    this.updateStatus('Connection error', 'disconnected');
                    this.disableInput();
                };
                
                this.ws.onclose = () => {
                    this.updateStatus('Disconnected', 'disconnected');
                    this.disableInput();
                };
                
            } catch (error) {
                this.updateStatus('Failed to connect', 'disconnected');
                console.error('Connection error:', error);
            }
        },
        
        handleMessage(data) {
            if (data.type === 'ai_message') {
                // messageType comes from backend: "intro", "questions", or "body"
                const messageType = data.messageType || 'body';
                this.addMessage(data.content, true, messageType);
                this.enableInput();
            } else if (data.type === 'workflow_complete') {
                this.updateStatus('Complete', 'complete');
                this.disableInput();
            } else if (data.type === 'error') {
                this.updateStatus('Error occurred', 'disconnected');
                this.addMessage(`Error: ${data.message}`, true, 'body');
            }
        },
        
        /**
         * Add message to chat
         * @param {string} content - Message content
         * @param {boolean} isBot - Is this a bot message?
         * @param {string} messageType - Type of message: "intro", "questions", or "body"
         */
        addMessage(content, isBot = true, messageType = 'body') {
            const messagesDiv = document.getElementById('chatbot-messages');
            
            // Get current time
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
            
            // Create message container
            const messageContainer = document.createElement('div');
            messageContainer.className = isBot ? 'message-container ai' : 'message-container user';
            
            // Create message bubble
            const messageBubble = document.createElement('div');
            
            if (isBot) {
                // Apply appropriate CSS class based on messageType from backend
                let messageClass = 'cleo-body'; // Default
                
                if (messageType === 'intro') {
                    messageClass = 'cleo-intro';
                } else if (messageType === 'questions') {
                    messageClass = 'cleo-question';
                }
                
                messageBubble.className = `cleo-bubble ai-message ${messageClass}`;
            } else {
                messageBubble.className = 'user-bubble';
            }
            
            messageBubble.textContent = content;
            
            // Create timestamp
            const timestamp = document.createElement('div');
            timestamp.className = 'message-timestamp';
            timestamp.textContent = timeString;
            
            // Append elements
            messageContainer.appendChild(messageBubble);
            messageContainer.appendChild(timestamp);
            messagesDiv.appendChild(messageContainer);
            
            // Smooth scroll to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollHeight,
                behavior: 'smooth'
            });
        },
        
        sendMessage() {
            const input = document.getElementById('chatbot-input');
            const message = input.value.trim();
            
            if (!message || !this.ws) return;
            
            this.addMessage(message, false, 'body'); // User messages always "body"
            
            this.ws.send(JSON.stringify({
                type: 'user_message',
                content: message
            }));
            
            input.value = '';
            this.disableInput();
        },
        
        updateStatus(message, type = 'info') {
            const statusEl = document.getElementById('chatbot-status-text');
            if (statusEl) {
                statusEl.textContent = message;
                
                const statusIcons = {
                    connected: '🟢',
                    connecting: '🟡',
                    disconnected: '🔴',
                    complete: '✅'
                };
                
                const icon = statusIcons[type] || '';
                if (icon) {
                    statusEl.textContent = `${icon} ${message}`;
                }
            }
        },
        
        enableInput() {
            const input = document.getElementById('chatbot-input');
            const sendBtn = document.getElementById('chatbot-send');
            if (input && sendBtn) {
                input.disabled = false;
                sendBtn.disabled = false;
                input.focus();
            }
        },
        
        disableInput() {
            const input = document.getElementById('chatbot-input');
            const sendBtn = document.getElementById('chatbot-send');
            if (input && sendBtn) {
                input.disabled = true;
                sendBtn.disabled = true;
            }
        }
    };
    
    // Expose CleoChatbot to global scope for manual initialization if needed
    window.CleoChatbot = CleoChatbot;
    
    /**
     * Auto-initialize chatbot when script loads
     * Implements domain-based validation:
     * 1. Reads job_id from data-job-id attribute
     * 2. Calls server to validate domain and get API key
     * 3. Initializes chatbot with validated configuration
     */
    async function autoInitChatbot() {
        
        // Find the chatbot container element
        const container = document.getElementById('cleo-chatbot') || 
                         document.querySelector('[data-job-id]');

        if (!container) {
            console.error('CleoChatbot: Container element with data-job-id attribute not found');
            return;
        }

        // Get job_id from data attribute
        // const jobID = container.dataset.jobID;
        
        // Get job_id from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const jobID = urlParams.get('job_id');

        if (!jobID) {
            console.error('CleoChatbot: job_id is required to initialize the chatbot');
            return;
        }

        // if (!jobID) {
        //     console.error('CleoChatbot: data-job-id attribute is required on container element');
        //     return;
        // }

        try {
            // Get current domain for validation
            const domain = window.location.hostname;
            console.log('CleoChatbot: Validating domain', domain, 'for job id', jobID);

            // Call server to validate domain and get API key
            const response = await fetch(
                `${CHATBOT_CONFIG.apiBaseUrl}/validate-domain?domain=${encodeURIComponent(domain)}`
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to validate domain');
            }

            const config = await response.json();

            // Initialize chatbot with validated configuration
            CleoChatbot.init({
                jobID: jobID,  // Use jobID from URL parameter
                apiKey: config.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl
            });

            console.log('CleoChatbot initialized successfully for job id:', jobID);

        } catch (error) {
            console.error('CleoChatbot initialization failed:', error.message);
            // Optionally show error to user
            alert(`Failed to load chatbot: ${error.message}`);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInitChatbot);
    } else {
        // DOM already loaded, initialize immediately
        autoInitChatbot();
    }
    
})(window);