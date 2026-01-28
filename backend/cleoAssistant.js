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
            
            // Load external CSS
            this.loadCSS();
            
            // Store configuration
            this.config = {
                jobType: options.jobType,
                jobLocation: options.jobLocation,
                jobID: options.jobID,
                companyID: options.companyID,
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

                <style>
                    
                    /* ✅ Smooth fade for AI messages */
                   /* AI: Slide from left */
                    
                    .message-container.ai {
                        animation: aiSlideUp 0.6s ease-out forwards;
                    }

                    @keyframes aiSlideUp {
                        from {
                            opacity: 0;
                            transform: translateY(20px);
                        }
                        to {
                            opacity: 1;
                            transform: translateY(0);
                        }
                    }

                    /* User: Slide from right */
                    .message-container.user {
                        animation: userSlideUp 0.6s ease-out forwards;
                    }

                    @keyframes userSlideUp {
                        from {
                            opacity: 0;
                            transform: translateY(20px);
                        }
                        to {
                            opacity: 1;
                            transform: translateY(0);
                        }
                    }

                    #typing-indicator {
                        animation: none !important;
                    }
                    
                    /* ✅ Typing indicator - NO animation */
                    .typing-indicator {
                        display: flex;
                        align-items: center;
                        padding: 12px 16px;
                        background-color: #EFEFF0;
                        border-radius: 18px;
                        width: fit-content;
                        margin: 8px 0;
                        /* ❌ Remove this line: */
                        /* animation: messageFadeSlideIn 0.3s ease-out forwards; */
                    }

                    .typing-indicator span {
                        height: 8px;
                        width: 8px;
                        background-color: #999;
                        border-radius: 50%;
                        display: inline-block;
                        margin: 0 2px;
                        animation: typing 1.4s infinite;
                    }

                    .typing-indicator span:nth-child(2) {
                        animation-delay: 0.2s;
                    }

                    .typing-indicator span:nth-child(3) {
                        animation-delay: 0.4s;
                    }

                    @keyframes typing {
                        0%, 60%, 100% {
                            transform: translateY(0);
                            opacity: 0.7;
                        }
                        30% {
                            transform: translateY(-10px);
                            opacity: 1;
                        }
                    }
                    
                    /* ✅ Smooth transitions for message bubbles */
                    .cleo-bubble, .user-bubble {
                        transition: all 0.2s ease;
                    }
                    
                    .cleo-bubble:hover, .user-bubble:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    }
                </style>
                    
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
            const widgetBtn = document.getElementById('cleo-widget-button');
            
            chatContainer.style.display = 'block';
            widgetBtn.style.display = 'none';  // Hide widget button
            this.isOpen = true;
            
            // Start chat if not already started
            if (!this.sessionId) {
                this.startChat();
            }
        },
        
        closeChat: function() {
            const chatContainer = document.getElementById('cleo-chat-container');
            const widgetBtn = document.getElementById('cleo-widget-button');
            
            chatContainer.style.display = 'none';
            widgetBtn.style.display = 'flex';  // Show widget button again
            this.isOpen = false;
        },

        showTypingIndicator() {
            const messagesDiv = document.getElementById('chatbot-messages');
            
            // Remove any existing typing indicator
            this.hideTypingIndicator();
            
            // Create typing indicator
            const typingDiv = document.createElement('div');
            typingDiv.id = 'typing-indicator';
            typingDiv.className = 'message-container ai';
            typingDiv.innerHTML = `
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
            
            messagesDiv.appendChild(typingDiv);
            
            // Scroll to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollHeight,
                behavior: 'smooth'
            });
        },

        hideTypingIndicator() {
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
        },
        
        /**
         * Start a new chat session with the server
         * Creates session and establishes WebSocket connection
         */
        async startChat() {
            try {
                this.updateStatus('Connecting...', 'connecting');

                // Use stored job location from config
                const apiKey = this.config.apiKey;
                const jobType = this.config.jobType;
                const location = this.config.jobLocation;
                const jobID = this.config.jobID;
                const companyID = this.config.companyID;

                const response = await fetch(
                    `${this.config.apiUrl}/start-session?job_type=${jobType}&api_key=${apiKey}&location=${location}&job_id=${jobID}&company_id=${companyID}`,
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
                    
                    // Show typing for initial messages
                    this.showTypingIndicator();
                    this.enableInput();
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };
                
                this.ws.onerror = () => {
                    this.hideTypingIndicator();  // Hide on error
                    this.updateStatus('Connection error', 'disconnected');
                    this.disableInput();
                };
                
                this.ws.onclose = () => {
                    this.hideTypingIndicator();  // Hide on close
                    this.updateStatus('Disconnected', 'disconnected');
                    this.disableInput();
                };
                
            } catch (error) {
                this.hideTypingIndicator();  // Hide on error
                this.updateStatus('Failed to connect', 'disconnected');
                console.error('Connection error:', error);
            }
        },
        
        handleMessage(data) {
            
            if (data.type === 'typing') {
                this.showTypingIndicator();
                return;
            }
            
            if (data.type === 'ai_message') {
                // Hide typing indicator when message arrives
                this.hideTypingIndicator();
                
                const messageType = data.messageType || 'body';
                this.addMessage(data.content, true, messageType);
                this.enableInput();
            } else if (data.type === 'workflow_complete') {
                this.hideTypingIndicator();  // Hide on completion
                this.updateStatus('Complete', 'complete');
                this.disableInput();
            } else if (data.type === 'error') {
                this.hideTypingIndicator();  // Hide on error
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
                } 
                else if (messageType === 'questions') {
                    messageClass = 'cleo-question';
                }
                
                messageBubble.className = `cleo-bubble ai-message ${messageClass}`;
            } 
            else {
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
            
            if (messageType === 'intro' || messageType === 'questions') 
            {
                // Smooth scroll to bottom
                messagesDiv.scrollTo({
                    top: messagesDiv.scrollHeight,
                    behavior: 'smooth'
                });
            }
                    
            // Smooth scroll to bottom
            // messagesDiv.scrollTo({
            //     top: messagesDiv.scrollHeight,
            //     behavior: 'smooth'
            // });
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

            // Show typing indicator
            this.showTypingIndicator();
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

        // const jobType = container.dataset.jobType;
    
        // Read Values from data attribute
        const jobLocation = container.getAttribute('data-job-location') ||'unknown';
        const jobType = container.getAttribute('data-job-type') || 'Position';
        const jobID = container.getAttribute('data-job-id') || '123';
        const companyID = container.getAttribute('data-company-id') || '987';

        console.log('CleoChatbot: jobType from data attribute:', container.getAttribute('data-job-type'));
        console.log('CleoChatbot: jobLocation from data attribute:', container.getAttribute('data-job-location'));
        console.log('CleoChatbot: jobID from data attribute:', container.getAttribute('data-job-id'));
        console.log('CleoChatbot: companyID from data attribute:', container.getAttribute('data-company-id'));
        
        // Get job_id from URL parameters
        // const urlParams = new URLSearchParams(window.location.search);
        // const jobID = urlParams.get('job_id');

        // Get job location from URL parameter
        // const urlParams = new URLSearchParams(window.location.search);
        // const jobLocation = urlParams.get('location')

        if (!jobType) {
            console.error('CleoChatbot: job_type is required to initialize the chatbot');
            return;
        }

        // if (!jobID) {
        //     console.error('CleoChatbot: job_id is required to initialize the chatbot');
        //     return;
        // }

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
                jobType: jobType,  // Use jobType from data attribute
                jobLocation: jobLocation,
                jobID: jobID,
                companyID: companyID,
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