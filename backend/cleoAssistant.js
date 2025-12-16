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
            if (!options.jobType || !options.apiKey) {
                console.error('CleoChatbot: jobType and apiKey are required');
                return;
            }
            
            // Store configuration
            this.config = {
                jobType: options.jobType,
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
                width: 500px;
                height: 500px;
                border-radius: 16px;
                box-shadow: 0 12px 48px rgba(0,0,0,0.3);
                z-index: 999998;
                display: none;
                animation: slideUp 0.3s ease-out;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
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
                    
                    @keyframes fadeIn {
                        from { opacity: 0; transform: translateY(10px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    
                    #chatbot-messages::-webkit-scrollbar {
                        width: 6px;
                    }
                    
                    #chatbot-messages::-webkit-scrollbar-track {
                        background: #f1f1f1;
                        border-radius: 10px;
                    }
                    
                    #chatbot-messages::-webkit-scrollbar-thumb {
                        background: #c1c1c1;
                        border-radius: 10px;
                    }
                    
                    #chatbot-messages::-webkit-scrollbar-thumb:hover {
                        background: #a8a8a8;
                    }
                </style>
                <div style="height: 100%; display: flex; flex-direction: column; background: white; border-radius: 16px; overflow: hidden;">
                    <!-- Header -->
                    <div style="background: linear-gradient(135deg, ${this.config.primaryColor} 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <div style="flex: 1;">
                            <div style="font-weight: 700; font-size: 18px; margin-bottom: 4px;">Cleo Assistant</div>
                            <div id="chatbot-status-text" style="font-size: 12px; opacity: 0.9;">Connecting...</div>
                        </div>
                        <button id="cleo-close-btn" style="background: rgba(255,255,255,0.2); border: none; color: white; font-size: 24px; cursor: pointer; padding: 0; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: background 0.2s;">×</button>
                    </div>
                    
                    <!-- Messages Area -->
                    <div id="chatbot-messages" style="flex: 1; overflow-y: auto; padding: 20px; background: #f7f8fc; display: flex; flex-direction: column; gap: 16px;"></div>
                    
                    <!-- Input Area -->
                    <div style="padding: 16px; background: white; border-top: 1px solid #e5e7eb; display: flex; gap: 10px; align-items: center;">
                        <input type="text" id="chatbot-input" placeholder="Type your message..." 
                            style="flex: 1; padding: 12px 16px; border: 2px solid #e5e7eb; border-radius: 24px; font-size: 14px; outline: none; transition: border-color 0.2s;"
                            disabled>
                        <button id="chatbot-send" 
                            style="padding: 12px 24px; background: linear-gradient(135deg, ${this.config.primaryColor} 0%, #764ba2 100%); color: white; border: none; border-radius: 24px; font-size: 14px; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; white-space: nowrap;"
                            disabled>Send</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(chatContainer);
            
            // Add event listeners
            document.getElementById('cleo-close-btn').addEventListener('click', () => this.closeChat());
            document.getElementById('cleo-close-btn').addEventListener('mouseenter', (e) => {
                e.target.style.background = 'rgba(255,255,255,0.3)';
            });
            document.getElementById('cleo-close-btn').addEventListener('mouseleave', (e) => {
                e.target.style.background = 'rgba(255,255,255,0.2)';
            });
            
            document.getElementById('chatbot-send').addEventListener('click', () => this.sendMessage());
            document.getElementById('chatbot-send').addEventListener('mouseenter', (e) => {
                e.target.style.transform = 'translateY(-2px)';
                e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            });
            document.getElementById('chatbot-send').addEventListener('mouseleave', (e) => {
                e.target.style.transform = 'translateY(0)';
                e.target.style.boxShadow = 'none';
            });
            
            document.getElementById('chatbot-input').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendMessage();
            });
            
            document.getElementById('chatbot-input').addEventListener('focus', (e) => {
                e.target.style.borderColor = this.config.primaryColor;
            });
            
            document.getElementById('chatbot-input').addEventListener('blur', (e) => {
                e.target.style.borderColor = '#e5e7eb';
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
                
                const response = await fetch(
                    `${this.config.apiUrl}/start-session?job_type=${this.config.jobType}&api_key=${this.config.apiKey}`,
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
                this.addMessage(data.content, true);
                this.enableInput();
            } else if (data.type === 'workflow_complete') {
                this.updateStatus('Complete', 'complete');
                this.disableInput();
            } else if (data.type === 'error') {
                this.updateStatus('Error occurred', 'disconnected');
                this.addMessage(`Error: ${data.message}`, true);
            }
        },
        
        addMessage(content, isBot = true) {
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
            messageContainer.style.cssText = `
                display: flex;
                flex-direction: column;
                align-items: ${isBot ? 'flex-start' : 'flex-end'};
                animation: fadeIn 0.4s ease-out;
                max-width: 100%;
            `;
            
            // Create message bubble
            const messageBubble = document.createElement('div');
            messageBubble.style.cssText = `
                max-width: 80%;
                padding: 12px 16px;
                border-radius: 18px;
                word-wrap: break-word;
                white-space: pre-wrap;
                font-size: 14px;
                line-height: 1.5;
                box-shadow: 0 1px 2px rgba(0,0,0,0.08);
                ${isBot 
                    ? `
                        background: #6A74DB;
                        color: white;
                        border-bottom-left-radius: 4px;
                        border: 1px solid #e5e7eb;
                    ` 
                    : `
                        background: linear-gradient(135deg, ${this.config.primaryColor} 0%, #764ba2 100%);
                        color: white;
                        border-bottom-right-radius: 4px;
                    `
                }
            `;
            messageBubble.textContent = content;
            
            // Create timestamp
            const timestamp = document.createElement('div');
            timestamp.style.cssText = `
                font-size: 11px;
                color: #9ca3af;
                margin-top: 4px;
                padding: 0 4px;
            `;
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
            
            this.addMessage(message, false);
            
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
     * 1. Reads job_type from data-job-type attribute
     * 2. Calls server to validate domain and get API key
     * 3. Initializes chatbot with validated configuration
     */
    async function autoInitChatbot() {
        // Find the chatbot container element
        const container = document.getElementById('cleo-chatbot') || 
                         document.querySelector('[data-job-type]');

        if (!container) {
            console.error('CleoChatbot: Container element with data-job-type attribute not found');
            return;
        }

        // Get job_type from data attribute
        const jobType = container.dataset.jobType;

        if (!jobType) {
            console.error('CleoChatbot: data-job-type attribute is required on container element');
            return;
        }

        try {
            // Get current domain for validation
            const domain = window.location.hostname;
            console.log('CleoChatbot: Validating domain', domain, 'for job type', jobType);

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
                jobType: jobType,  // Use jobType from DOM
                apiKey: config.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl
            });

            console.log('CleoChatbot initialized successfully for job type:', jobType);

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