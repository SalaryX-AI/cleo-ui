(function(window) {
    'use strict';
    
    // Configuration for the chatbot API endpoints
    const CHATBOT_CONFIG = {
        apiBaseUrl: 'http://localhost:8000',
        wsBaseUrl: 'ws://localhost:8000'
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
            
            if (!options.jobId || !options.apiKey) {
                console.error('CleoChatbot: jobId and apiKey are required');
                return;
            }
            
            // Store configuration
            this.config = {
                jobId: options.jobId,
                apiKey: options.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl,
                position: 'bottom-right',
                primaryColor: '#667eea'
            };
            
            // Create the chat widget UI
            this.createWidget();
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
            
            widgetBtn.style.cssText = `
                position: fixed;
                ${positions[this.config.position]}
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: ${this.config.primaryColor};
                color: white;
                font-size: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                z-index: 999999;
                transition: transform 0.2s, box-shadow 0.2s;
            `;
            
            widgetBtn.addEventListener('mouseenter', () => {
                widgetBtn.style.transform = 'scale(1.1)';
                widgetBtn.style.boxShadow = '0 6px 16px rgba(0,0,0,0.4)';
            });
            
            widgetBtn.addEventListener('mouseleave', () => {
                widgetBtn.style.transform = 'scale(1)';
                widgetBtn.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
            });
            
            widgetBtn.addEventListener('click', () => this.toggleChat());
            
            document.body.appendChild(widgetBtn);
            
            // Create chat container (hidden initially)
            this.createChatUI();
        },
        
        createChatUI: function() {
            const chatContainer = document.createElement('div');
            chatContainer.id = 'cleo-chat-container';
            
            const positions = {
                'bottom-right': 'bottom: 90px; right: 20px;',
                'bottom-left': 'bottom: 90px; left: 20px;'
            };
            
            chatContainer.style.cssText = `
                position: fixed;
                ${positions[this.config.position]}
                width: 450px;
                height: 450px;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                z-index: 999998;
                display: none;
                animation: slideUp 0.3s ease-out;
            `;
            
            chatContainer.innerHTML = `
                <style>
                    @keyframes slideUp {
                        from {
                            opacity: 0;
                            transform: translateY(20px);
                        }
                        to {
                            opacity: 1;
                            transform: translateY(0);
                        }
                    }
                </style>
                <div style="height: 100%; display: flex; flex-direction: column; background: white; border-radius: 12px; overflow: hidden;">
                    <div style="background: ${this.config.primaryColor}; color: white; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 600; font-size: 16px; text-align:center;">Cleo Chatbot</div>
                        </div>
                        <button id="cleo-close-btn" style="background: none; border: none; color: white; font-size: 24px; cursor: pointer; padding: 0; width: 30px; height: 30px;">x</button>
                    </div>
                    <div id="chatbot-status" style="padding: 8px; text-align: center; font-size: 12px; color: #666; background: #f0f0f0;">
                        Not connected
                    </div>
                    <div id="chatbot-messages" style="flex: 1; overflow-y: auto; padding: 16px; background: #f8f9fa;"></div>
                    <div style="padding: 16px; background: white; border-top: 1px solid #e0e0e0; display: flex; gap: 8px;">
                        <input type="text" id="chatbot-input" placeholder="Type your message..." 
                            style="flex: 1; padding: 10px 14px; border: 2px solid #e0e0e0; border-radius: 20px; font-size: 14px; outline: none;"
                            disabled>
                        <button id="chatbot-send" 
                            style="padding: 10px 20px; background: ${this.config.primaryColor}; color: white; border: none; border-radius: 20px; font-size: 14px; font-weight: 600; cursor: pointer;"
                            disabled>Send</button>
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
                this.updateStatus('Connecting...', 'info');
                
                const response = await fetch(
                    `${this.config.apiUrl}/start-session?job_id=${this.config.jobId}&api_key=${this.config.apiKey}`,
                    { method: 'POST' }
                );
                
                if (!response.ok) {
                    throw new Error('Failed to start session');
                }
                
                const data = await response.json();
                this.sessionId = data.session_id;
                
                this.updateStatus(`Connected - ${data.position}`, 'connected');
                
                this.ws = new WebSocket(`${this.config.wsUrl}/ws/${this.sessionId}`);
                
                this.ws.onopen = () => {
                    this.updateStatus('Connected', 'connected');
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };
                
                this.ws.onerror = () => {
                    this.updateStatus('Connection error', 'disconnected');
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
                this.addMessage(data.content, true);
                this.enableInput();
            } 
            else if (data.type === 'workflow_complete') {
                this.updateStatus('Screening Complete', 'info');
                this.disableInput();

                const sendButton = document.getElementById('chatbot-send');
                if (sendButton) {
                    sendButton.disabled = true;
                    sendButton.style.cursor = 'not-allowed';
                    sendButton.style.opacity = '0.6';
    }
                
                // const summary = data.summary;
                // this.addMessage(
                //     `✅ Screening completed!\nScore: ${summary.total_score}/${summary.max_score}`,
                //     true
                // );
            } 
            else if (data.type === 'error') {
                this.updateStatus('Error occurred', 'disconnected');
                this.addMessage(`Error: ${data.message}`, true);
            }
        },
        
        addMessage(content, isBot = true) {
            const messagesDiv = document.getElementById('chatbot-messages');
            const messageDiv = document.createElement('div');
            messageDiv.style.cssText = `
                margin-bottom: 12px;
                display: flex;
                justify-content: ${isBot ? 'flex-start' : 'flex-end'};
                animation: slideUp 0.3s ease-out;
            `;
            
            const contentDiv = document.createElement('div');
            contentDiv.style.cssText = `
                max-width: 75%;
                padding: 10px 14px;
                border-radius: 16px;
                word-wrap: break-word;
                white-space: pre-wrap;
                font-size: 14px;
                ${isBot 
                    ? 'background: white; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);' 
                    : `background: ${this.config.primaryColor}; color: white; border-bottom-right-radius: 4px;`}
            `;
            contentDiv.textContent = content;
            
            messageDiv.appendChild(contentDiv);
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        },
        
        sendMessage() {
            const input = document.getElementById('chatbot-input');
            const message = input.value.trim();
            
            if (!message || !this.ws) return;
            
            this.addMessage(message, false);
            
            this.ws.send(JSON.stringify({
                type: 'user_message',
                content: message
            }));
            
            input.value = '';
            this.disableInput();
        },
        
        updateStatus(message, type = 'info') {
            const statusEl = document.getElementById('chatbot-status');
            if (statusEl) {
                statusEl.textContent = message;
                
                const colors = {
                    connected: '#d4edda',
                    disconnected: '#f8d7da',
                    info: '#f0f0f0'
                };
                statusEl.style.background = colors[type] || colors.info;
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
     * 1. Reads job_id from data-job-id attribute
     * 2. Calls server to validate job and get API key
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
        const jobId = container.dataset.jobId;

        if (!jobId) {
            console.error('CleoChatbot: data-job-id attribute is required on container element');
            return;
        }

        try {
            // Get current domain for validation
            const domain = window.location.hostname;

            // Call server to validate job_id and domain, get API key
            const response = await fetch(
                `${CHATBOT_CONFIG.apiBaseUrl}/validate-job?job_id=${encodeURIComponent(jobId)}&domain=${encodeURIComponent(domain)}`
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to validate job');
            }

            const config = await response.json();

            // Initialize chatbot with validated configuration
            CleoChatbot.init({
                jobId: config.jobId,
                apiKey: config.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl
            });

            console.log('CleoChatbot initialized successfully');

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