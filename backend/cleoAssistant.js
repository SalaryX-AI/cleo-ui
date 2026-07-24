const link = document.createElement("link");
link.rel = "stylesheet";
link.href = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css";
document.head.appendChild(link);


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
        reconnecting: false, // prevent multiple reconnect attempts
        heartbeatInterval: null,
        conversationEnded: false, 
        
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
                mode: options.mode || 'job',
                jobType: options.jobType,
                jobTemplateID: options.jobTemplateID,
                singleCompany: options.singleCompany,
                jobLocation: options.jobLocation,
                jobID: options.jobID,
                jobShift: options.jobShift,
                brandName: options.brandName,
                companyID: options.companyID,
                verificationRequired: options.verificationRequired,
                isLive: options.isLive,
                apiKey: options.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl,
                position: 'bottom-right',
                primaryColor: '#667eea'
            };
            
            // Create the chat widget UI
            this.createWidget();

            // Set up page visibility listener
            this.setupVisibilityListener();
        },

        setupVisibilityListener: function() {
            // ✅ Detect when user returns to the tab
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible') {
                    console.log('[VISIBILITY] Tab became visible');
                    this.handlePageVisible();
                } else {
                    console.log('[VISIBILITY] Tab hidden');
                }
            });
            
            // ✅ iOS Safari uses different events
            window.addEventListener('pageshow', (event) => {
                if (event.persisted) {
                    console.log('[PAGESHOW] Page restored from cache');
                    this.handlePageVisible();
                }
            });
        },
        
        handlePageVisible: function() {
                    if (this.conversationEnded) {
                        console.log('[RECONNECT] Conversation ended — skipping reconnect');
                        return;
                    }
                    if (!this.sessionId) return;
                    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                        console.log('[RECONNECT] WebSocket disconnected, attempting reconnect...');
                        this.reconnectWebSocket();
                    }
        },

        updateConnectionStatus: function(status) {
            const header = document.getElementById('cleo-chat-header');
            if (!header) return;
                
            // Remove existing status indicator
            const existingStatus = header.querySelector('.connection-status');
            if (existingStatus) existingStatus.remove();
                
            if (status === 'disconnected') {
                const statusDiv = document.createElement('div');
                statusDiv.className = 'connection-status';
                statusDiv.style.cssText = `
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 12px;
                    color: #f44336;
                    margin-left: 8px;
                `;
                statusDiv.innerHTML = '🔴 Disconnected';
                header.appendChild(statusDiv);
                } 
                else if (status === 'connected') {
                    // Connected - no indicator needed, or show briefly
                    const statusDiv = document.createElement('div');
                    statusDiv.className = 'connection-status';
                    statusDiv.style.cssText = `
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        font-size: 12px;
                        color: #4caf50;
                        margin-left: 8px;
                    `;
                    statusDiv.innerHTML = '🟢 Connected';
                    header.appendChild(statusDiv);
                    
                    // Remove after 2 seconds
                    setTimeout(() => {
                        if (statusDiv.parentNode) statusDiv.remove();
                    }, 2000);
                }

                else if (status === 'completed') {
                const statusDiv = document.createElement('div');
                statusDiv.className = 'connection-status';
                statusDiv.style.cssText = `
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 12px;
                    color: #8b5cf6;
                    margin-left: 8px;
                `;
                statusDiv.innerHTML = '✅ Complete';
                header.appendChild(statusDiv);
            }
        },
        
        reconnectWebSocket: function() {
            if (this.conversationEnded) return; 
            // Prevent multiple simultaneous reconnect attempts
            if (this.reconnecting) {
                console.log('[RECONNECT] Already reconnecting, skipping...');
                return;
            }
            
            this.reconnecting = true;
            
            // Show reconnecting message to user
            this.showReconnectingMessage();
            
            // Close old connection if it exists
            if (this.ws) {
                this.ws.onclose = null;  // Remove handler to prevent recursion
                this.ws.close();
            }
            
            // Wait a moment, then reconnect
            setTimeout(() => {
                this.connectWebSocket();
                this.reconnecting = false;
            }, 500);
        },
        
        showReconnectingMessage: function() {
            const messagesDiv = document.getElementById('chatbot-messages');
            if (!messagesDiv) return;
            
            // Remove any existing reconnect message
            const existing = document.getElementById('reconnect-message');
            if (existing) existing.remove();
            
            const reconnectDiv = document.createElement('div');
            reconnectDiv.id = 'reconnect-message';
            reconnectDiv.style.cssText = `
                padding: 12px;
                margin: 10px 0;
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 8px;
                text-align: center;
                font-size: 14px;
                color: #856404;
            `;
            reconnectDiv.innerHTML = '🔄 Reconnecting...';
            
            messagesDiv.appendChild(reconnectDiv);
            
            // Remove after successful reconnection
            setTimeout(() => {
                if (reconnectDiv.parentNode) {
                    reconnectDiv.remove();
                }
            }, 3000);
        },
        
        connectWebSocket: function() {
            const wsPath = this.config.mode === 'passport'
                ? `${this.config.wsUrl}/passport/ws/${this.sessionId}`
                : `${this.config.wsUrl}/ws/${this.sessionId}`;
            this.ws = new WebSocket(wsPath);
            
            this.ws.onopen = () => {
                console.log('✅ WebSocket connected');

                // ✅ Update connection status
                this.updateConnectionStatus('connected');
                this.updateStatus('Online', 'connected');
                
                this.enableInput();
                this.reconnecting = false;
                
                // ✅ Request state sync from server
                this.ws.send(JSON.stringify({ type: 'sync_state' }));
                
                this.startHeartbeat();
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                // Handle heartbeat
                if (data.type === 'ping') {
                    console.log('[HEARTBEAT] Received ping, sending pong');
                    this.ws.send(JSON.stringify({ type: 'pong' }));
                    return;
                }
                
                if (data.type === 'pong') {
                    console.log('[HEARTBEAT] Received pong');
                    return;
                }

                if (data.type === 'conversation_ended') {
                    console.log('[CLEO] Conversation ended — blocking reconnect');
                    this.conversationEnded = true;
                    return;
                }
                
                // Handle state sync response
                if (data.type === 'state_synced') {
                    console.log('[SYNC] State synchronized');
                    return;
                }
                
                this.handleMessage(data);
            };
            
            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected', event.code, event.reason);
                this.disableInput();
                this.stopHeartbeat();

                if (this.conversationEnded) {
                    this.updateStatus('Application complete', 'connected');
                    return;   // ← no reconnect attempt
                }

                this.updateConnectionStatus('disconnected');

                if (event.code !== 1000 && !this.reconnecting) {
                    console.log('[RECONNECT] Unexpected disconnect, reconnecting in 2s...');
                    setTimeout(() => this.reconnectWebSocket(), 2000);
                }
            };
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
                'bottom-right': 'top: 50%; right: 20px; transform: translateY(-50%);',
                'bottom-left': 'top: 50%; left: 20px; transform: translateY(-50%);'
            };
            
            // Position and size need to be inline (dynamic)
            chatContainer.style.cssText = `
                position: fixed;
                ${positions[this.config.position]}
                width: 520px;
                height: 590px;
                border-radius: 16px;
                box-shadow: 0 12px 48px rgba(0,0,0,0.3);
                z-index: 999998;
                display: none;
                animation: slideUp 0.3s ease-out;
            `;
            
            chatContainer.innerHTML = `

                <style>
                    
                    /* Smooth fade for AI messages */
                   /* AI: Slide from left */
                    
                    .message-container.ai {
                        animation: aiSlideUp 0.8s ease-out forwards;
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
                        animation: userSlideUp 0.8s ease-out forwards;
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
                    
                    /* Typing indicator - NO animation */
                    .typing-indicator {
                        display: flex;
                        align-items: center;
                        padding: 12px 16px;
                        background-color: #EFEFF0;
                        border-radius: 18px;
                        width: fit-content;
                        margin: 8px 0;
                    }

                    .typing-indicator span {
                        height: 8px;
                        width: 8px;
                        background-color: #999;
                        border-radius: 50%;
                        display: inline-block;
                        margin: 0 2px;
                        animation: typing 1.2s infinite;
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
                    
                    /* Smooth transitions for message bubbles */
                    .cleo-bubble, .user-bubble {
                        transition: all 0.2s ease;
                    }
                    
                    .cleo-bubble:hover, .user-bubble:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    }
                </style>
                    
                <div style="height: 100%; display: flex; flex-direction: column; background: white; border-radius: 10px; overflow: hidden;">
                    <!-- Header -->
                    <div id="cleo-chat-header" style="height: 9%;">
                        <div style="flex: 1;">
                            <div class="title">Cleo Assistant</div>
                            <div id="chatbot-status-text" class="status">Connecting...</div>
                        </div>
                        <button id="cleo-close-btn">×</button>
                    </div>
                    
                    <!-- Messages Area -->
                    <div id="chatbot-messages"></div>
                    
                    <!-- Input Area -->
                    <div style="padding: 8px 12px; background: white; border-top: 1px solid #e5e7eb; display: flex; gap: 8px; align-items: center;">
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

                const apiKey    = this.config.apiKey;
                const jobType   = this.config.jobType;
                
                const jobTemplateID = this.config.jobTemplateID;
                const location  = this.config.jobLocation;
                const jobID     = this.config.jobID;
                const companyID = this.config.companyID;
                const verificationRequired = this.config.verificationRequired;
                const isLive    = this.config.isLive;
                const jobShift  = this.config.jobShift;
                const brandName = this.config.brandName;
                const singleCompany = this.config.singleCompany;
                
                let response;
                if (this.config.mode === 'passport') {
                    response = await fetch(`${this.config.apiUrl}/start-passport-session`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            api_key: apiKey,
                            is_live: isLive,
                        })
                    });
                } else {
                    response = await fetch(`${this.config.apiUrl}/start-session`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            api_key:    apiKey,
                            job_type:   jobType,
                            job_template_id: jobTemplateID,
                            location:   location,
                            job_id:     jobID,
                            company_id: companyID,
                            verification_required: verificationRequired,
                            is_live:    isLive,
                            job_shift:  jobShift,
                            brand_name: brandName,
                            single_company: singleCompany
                        })
                    });
                }
                
                if (!response.ok) {
                    throw new Error('Failed to start session');
                }
                
                const data = await response.json();
                this.sessionId = data.session_id;
                
                this.connectWebSocket();
                
                this.ws.onopen = () => {
                    this.updateStatus('Online', 'connected');
                    
                    // Show typing for initial messages
                    // this.showTypingIndicator();
                    this.enableInput();
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);

                    // Handle ping - respond with pong
                    if (data.type === 'ping') {
                        console.log('[HEARTBEAT] Received ping, sending pong');
                        this.ws.send(JSON.stringify({ type: 'pong' }));
                        return;  // Don't process ping as a normal message
                    }

                    this.handleMessage(data);
                };
                
                this.ws.onerror = () => {
                    this.hideTypingIndicator();  // Hide on error
                    this.updateStatus('Connection error', 'disconnected');
                    this.disableInput();
                };
                
                this.ws.onclose = () => {
                    this.hideTypingIndicator();
                    if (this.conversationEnded) {
                        this.updateStatus('Application complete', 'connected');
                    } else {
                        this.updateStatus('Disconnected', 'disconnected');
                    }
                    this.disableInput();
                };
                
            } catch (error) {
                this.hideTypingIndicator();  // Hide on error
                this.updateStatus('Failed to connect', 'disconnected');
                console.error('Connection error:', error);
            }
        },
        
        handleMessage(data) {

            // ── Conversation ended by stop command ────────────────────────────
            if (data.type === 'conversation_ended') {
                console.log('[CLEO] Conversation ended');
                this.conversationEnded = true;
                this.hideTypingIndicator();
                this.disableInput();
                this.updateStatus('Application complete', 'connected');
                return;
            }
            
            // Handle typing event
            if (data.type === 'typing') {
                this.showTypingIndicator();
                return;
            }
            
            if (data.type === 'ai_message') {
                // Hide typing indicator when message arrives
                this.hideTypingIndicator();
                
                const messageType = data.messageType || 'body';
                this.addMessage(data.content, true, messageType);
                
                // Check if we should show work experience UI
                if (data.show_work_experience_ui) 
                {
                    WorkExperienceUI.show();
                }
                // Check if we should show education UI
                else if (data.show_education_ui) 
                {
                    EducationUI.show();
                }
                // Show address autocomplete UI
                else if (data.show_address_ui) 
                {
                    if (data.passport_address_mode) {
                        PassportLocationUI.show();
                    } else {
                        AddressUI.show();
                    }
                }
                // Show shift preference checkboxes (passport mode only)
                else if (data.show_shift_ui)
                {
                    ShiftPreferenceUI.show();
                }
                else if (data.show_privacy_consent_ui)
                {
                    PrivacyConsentUI.show();
                }
                // Show GPS verification button
                else if (data.show_gps_ui) 
                {
                    LocationVerificationUI.show();
                }  
                else if (data.show_id_verify_ui) {
                    IdVerificationUI.show(data.id_verify_link || "");
                }
                else 
                {
                    this.enableInput();
                }
            
            }
            
            else if (data.type === 'workflow_complete') {
                this.hideTypingIndicator();  // Hide on completion
                this.updateStatus('Complete', 'complete');
                this.disableInput();
            } 
            else if (data.type === 'error') {
                this.hideTypingIndicator();  // Hide on error
                this.updateStatus('Error occurred', 'disconnected');
                this.addMessage(`Error: ${data.message}`, true, 'body');
            }
            else if (data.type === 'id_verify_result') {
                IdVerificationUI.showWebhookResult(data.verified);
                // Auto-close modal after 1.5s so user sees the status briefly
                IdVerificationUI.closeModal()
                // setTimeout(() => IdVerificationUI.closeModal(), 800);
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
            
            if (isBot) {
                // Convert newlines to <br> and URLs to clickable anchor text
                const linkedContent = content
                    .replace(/\n/g, '<br>')
                    .replace(
                        /(https?:\/\/[^\s<]+)/g,
                        '<a href="$1" target="_blank" rel="noopener noreferrer" style="color:#667eea;font-weight:600;text-decoration:underline;">My Passport</a>'
                    );
                messageBubble.innerHTML = linkedContent;
            } 
            else {
                messageBubble.textContent = content;
            }
            
            // // Create timestamp
            // const timestamp = document.createElement('div');
            // timestamp.className = 'message-timestamp';
            // timestamp.textContent = timeString;
            
            // Append elements
            messageContainer.appendChild(messageBubble);
            // messageContainer.appendChild(timestamp);
            
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
        },

        startHeartbeat() {
            this.stopHeartbeat(); // clear any existing interval first
            this.heartbeatInterval = setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ type: 'ping' }));
                    console.log('[HEARTBEAT] Sent ping');
                }
            }, 30000); // every 30 seconds
        },

        stopHeartbeat() {
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
                this.heartbeatInterval = null;
                console.log('[HEARTBEAT] Stopped');
            }
        }
    };

    // ── Passport Location UI (ZIP / city only) ────────────────────────────────
    const PassportLocationUI = {

        render() {
            const container = document.createElement('div');
            container.id = 'passport-location-ui';

            container.innerHTML = `
                <style>
                    #passport-location-ui {
                        margin: 8px 0;
                        padding: 10px;
                        background: #f7f7fa;
                        border-radius: 14px;
                        border: 1px solid rgba(102,126,234,0.15);
                    }
                    .ploc-label {
                        font-size: 12px;
                        font-weight: 600;
                        color: #4a4a55;
                        margin-bottom: 8px;
                        display: block;
                    }
                    .ploc-input {
                        width: 100%;
                        padding: 8px 12px;
                        border: 1.5px solid #e0e0e8;
                        border-radius: 10px;
                        font-size: 13px;
                        font-family: inherit;
                        outline: none;
                        margin-bottom: 8px;
                        box-sizing: border-box;
                        transition: border-color 0.15s;
                    }
                    .ploc-input:focus {
                        border-color: #667eea;
                    }
                    .ploc-confirm-btn {
                        width: 100%;
                        padding: 8px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                        color: #ffffff !important;
                        border: none;
                        border-radius: 10px;
                        font-size: 13px;
                        font-weight: 600;
                        cursor: pointer;
                        font-family: inherit;
                        transition: opacity 0.2s;
                        -webkit-text-fill-color: #ffffff;
                    }
                    .ploc-confirm-btn:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                    }
                    .ploc-confirm-btn:hover:not(:disabled) {
                        opacity: 0.9;
                    }
                    .ploc-suggestion {
                        padding: 8px 12px;
                        font-size: 12px;
                        cursor: pointer;
                        border-bottom: 1px solid #f0f0f5;
                        color: #333;
                        transition: background 0.1s;
                    }
                    .ploc-suggestion:last-child {
                        border-bottom: none;
                    }
                    .ploc-suggestion:hover {
                        background: rgba(102,126,234,0.08);
                    }
                </style>

                <span class="ploc-label">Enter your city/state or ZIP code 📍</span>
                <input
                    type="text"
                    class="ploc-input"
                    id="ploc-input"
                    placeholder="e.g. Miami, FL or 33101"
                    maxlength="100"
                    autocomplete="off"
                />
                <div id="ploc-suggestions" style="
                    display: none;
                    background: #fff;
                    border: 1.5px solid #e0e0e8;
                    border-radius: 10px;
                    margin-bottom: 8px;
                    overflow: hidden;
                    max-height: 160px;
                    overflow-y: auto;
                "></div>
                <button class="ploc-confirm-btn" id="ploc-confirm-btn" disabled>
                    Confirm Location
                </button>
            `;

            return container;
        },

        attachEventListeners() {
            const input         = document.getElementById('ploc-input');
            const confirmBtn    = document.getElementById('ploc-confirm-btn');
            const suggBox       = document.getElementById('ploc-suggestions');
            const sessionToken  = crypto.randomUUID();
            let selectedPlace   = null;

            input.addEventListener('input', async () => {
                const query = input.value.trim();
                confirmBtn.disabled = query.length < 2;
                selectedPlace = null;

                if (query.length < 2) {
                    suggBox.innerHTML = '';
                    suggBox.style.display = 'none';
                    return;
                }

                try {
                    const resp = await fetch(
                        `${window.apiBaseUrl}/places/autocomplete?input=${encodeURIComponent(query)}&session_token=${sessionToken}&types=(cities)`
                    );
                    const data = await resp.json();
                    const predictions = data.predictions || [];

                    if (!predictions.length) {
                        suggBox.style.display = 'none';
                        return;
                    }

                    // Format display: show only city, state/country — not full street
                    const formatLocation = (description) => {
                        const parts = description.split(',').map(p => p.trim());
                        // Return first 2-3 parts (city, state, country)
                        return parts.slice(0, 3).join(', ');
                    };

                    suggBox.innerHTML = predictions.map(p => `
                        <div class="ploc-suggestion" data-place-id="${p.place_id}" data-description="${formatLocation(p.description)}">
                            📍 ${formatLocation(p.description)}
                        </div>
                    `).join('');
                    
                    suggBox.style.display = 'block';

                    suggBox.querySelectorAll('.ploc-suggestion').forEach(item => {
                        item.addEventListener('click', async () => {
                            const placeId     = item.getAttribute('data-place-id');
                            const description = item.getAttribute('data-description');
                            input.value       = description;
                            suggBox.innerHTML  = '';
                            suggBox.style.display = 'none';
                            confirmBtn.disabled   = false;

                            // Fetch place details for lat/lng
                            try {
                                const detResp = await fetch(
                                    `${window.apiBaseUrl}/places/details?place_id=${placeId}`
                                );
                                selectedPlace = await detResp.json();
                            } catch {
                                selectedPlace = { full: description };
                            }
                        });
                    });
                } catch {
                    suggBox.style.display = 'none';
                }
            });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !confirmBtn.disabled) this.submit(selectedPlace, input.value);
            });

            confirmBtn.addEventListener('click', () => this.submit(selectedPlace, input.value));
        },

        submit(selectedPlace, rawInput) {
            const location = (rawInput || document.getElementById('ploc-input')?.value || '').trim();

            if (!location) return;

            // Show as user bubble
            window.CleoChatbot.addMessage(location, false, 'body');

            // Build address payload from selected place or raw text
            const addressData = selectedPlace ? {
                full:   selectedPlace.full   || location,
                city:   selectedPlace.city   || location,
                state:  selectedPlace.state  || '',
                zip:    selectedPlace.zip    || '',
                street: '',
                lat:    selectedPlace.lat    || 0,
                lng:    selectedPlace.lng    || 0,
            } : {
                full:   location,
                city:   location,
                street: '',
                state:  '',
                zip:    '',
                lat:    0,
                lng:    0,
            };

            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'address_data',
                    data: addressData,
                }));
            }

            window.dispatchEvent(new CustomEvent('passportUpdate', {
                detail: { location: location }
            }));

            this.hide();
        },

        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui          = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();
            messagesDiv.scrollTo({
                top:      messagesDiv.scrollTop + (messagesDiv.clientHeight / 2),
                behavior: 'smooth'
            });
            window.CleoChatbot.disableInput();

            // Auto-focus input
            setTimeout(() => {
                const input = document.getElementById('ploc-input');
                if (input) input.focus();
            }, 100);
        },

        hide() {
            const ui = document.getElementById('passport-location-ui');
            if (ui) ui.remove();
            window.CleoChatbot.enableInput();
        }
    };
    // ── End PassportLocationUI ────────────────────────────────────────────────

    // ── Shift Preference UI (passport mode) ──────────────────────────────────
    const ShiftPreferenceUI = {

        render() {
            const container = document.createElement('div');
            container.id = 'shift-preference-ui';

            container.innerHTML = `
                <style>
                    #shift-preference-ui {
                        margin: 8px 0;
                        padding: 10px;
                        background: #f7f7fa;
                        border-radius: 14px;
                        border: 1px solid rgba(102,126,234,0.15);
                    }

                    .shift-label {
                        font-size: 13px;
                        font-weight: 600;
                        color: #4a4a55;
                        margin-bottom: 12px;
                        display: block;
                    }

                    .shift-options {
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 8px;
                        margin-bottom: 14px;
                    }

                    .shift-option {
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        padding: 7px 10px;
                        background: #fff;
                        border: 2px solid #e0e0e8;
                        border-radius: 10px;
                        cursor: pointer;
                        font-size: 13px;
                        font-weight: 500;
                        color: #333;
                        transition: border-color 0.15s, background 0.15s;
                        user-select: none;
                    }

                    .shift-option.selected {
                        border-color: #667eea;
                        background: rgba(102,126,234,0.07);
                        color: #667eea;
                    }

                    .shift-option input[type="checkbox"] {
                        accent-color: #667eea;
                        width: 15px;
                        height: 15px;
                        flex-shrink: 0;
                    }

                    .shift-confirm-btn {
                        width: 100%;
                        padding: 8px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 12px;
                        font-size: 13px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: opacity 0.2s, transform 0.12s;
                        font-family: inherit;
                    }

                    .shift-confirm-btn:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                    }

                    .shift-confirm-btn:hover:not(:disabled) {
                        transform: translateY(-1px);
                        opacity: 0.92;
                    }
                </style>

                <span class="shift-label">Select all shifts that work for you 👇</span>

                <div class="shift-options">
                    <label class="shift-option" id="shift-days">
                        <input type="checkbox" value="Days" /> 🌅 Days
                    </label>
                    <label class="shift-option" id="shift-evenings">
                        <input type="checkbox" value="Evenings" /> 🌆 Evenings
                    </label>
                    <label class="shift-option" id="shift-overnights">
                        <input type="checkbox" value="Overnights" /> 🌙 Overnights
                    </label>
                    <label class="shift-option" id="shift-weekends">
                        <input type="checkbox" value="Weekends" /> 📅 Weekends
                    </label>
                </div>

                <button class="shift-confirm-btn" id="shift-confirm-btn" disabled>
                    Confirm Availability
                </button>
            `;

            return container;
        },

        attachEventListeners() {
            const checkboxes = document.querySelectorAll('#shift-preference-ui input[type="checkbox"]');
            const confirmBtn = document.getElementById('shift-confirm-btn');

            checkboxes.forEach(cb => {
                cb.addEventListener('change', () => {
                    // Toggle selected style on parent label
                    cb.closest('.shift-option').classList.toggle('selected', cb.checked);

                    // Enable confirm only if at least one selected
                    const anySelected = [...checkboxes].some(c => c.checked);
                    confirmBtn.disabled = !anySelected;
                });
            });

            confirmBtn.addEventListener('click', () => this.submit());
        },

        submit() {
            const checkboxes = document.querySelectorAll('#shift-preference-ui input[type="checkbox"]:checked');
            const selected = [...checkboxes].map(cb => cb.value);

            if (!selected.length) return;

            // Show as user bubble
            window.CleoChatbot.addMessage(
                `My availability: ${selected.join(', ')}`,
                false,
                'body'
            );

            // Send to backend
            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'shift_selection',
                    data: selected
                }));
            }

            // Dispatch passport preview update
            window.dispatchEvent(new CustomEvent('passportUpdate', {
                detail: { shifts: selected }
            }));

            this.hide();
        },

        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();
            messagesDiv.scrollTo({ top: messagesDiv.scrollHeight, behavior: 'smooth' });
            window.CleoChatbot.disableInput();
        },

        hide() {
            const ui = document.getElementById('shift-preference-ui');
            if (ui) ui.remove();
        }
    };
    // ── End ShiftPreferenceUI ─────────────────────────────────────────────────


    // ── Privacy Consent UI (passport mode) ───────────────────────────────────
    const PrivacyConsentUI = {

        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const container   = document.createElement('div');
            container.id      = 'privacy-consent-ui';

            container.innerHTML = `
                <style>
                    #privacy-consent-ui {
                        margin: 8px 0;
                        padding: 10px;
                        background: #f7f7fa;
                        border-radius: 14px;
                        border: 1px solid rgba(102,126,234,0.15);
                    }
                    .consent-label {
                        display: flex;
                        align-items: flex-start;
                        gap: 8px;
                        cursor: pointer;
                        font-size: 12px;
                        line-height: 1.5;
                        color: #333;
                        user-select: none;
                    }
                    .consent-checkbox {
                        width: 18px;
                        height: 18px;
                        accent-color: #667eea;
                        flex-shrink: 0;
                        margin-top: 2px;
                        cursor: pointer;
                    }
                </style>
                <label class="consent-label">
                    <input type="checkbox" class="consent-checkbox" id="privacy-checkbox" />
                    I understand and agree that my information will only be shared with employers I authorize.
                </label>
            `;

            messagesDiv.appendChild(container);
            messagesDiv.scrollTo({ top: messagesDiv.scrollHeight, behavior: 'smooth' });
            window.CleoChatbot.disableInput();

            // Auto-submit on checkbox click
            document.getElementById('privacy-checkbox').addEventListener('change', function() {
                if (this.checked) {
                    // Brief visual feedback
                    this.disabled = true;
                    setTimeout(() => {
                        PrivacyConsentUI.submit();
                    }, 300);
                }
            });
        },

        submit() {
            // Show as user bubble
            window.CleoChatbot.addMessage('✅ I agree', false, 'body');

            // Send to backend
            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type:    'user_message',
                    content: 'I agree'
                }));
            }

            this.hide();
            window.CleoChatbot.enableInput();
        },

        hide() {
            const ui = document.getElementById('privacy-consent-ui');
            if (ui) ui.remove();
        }
    };
    // ── End PrivacyConsentUI ──────────────────────────────────────────────────



    // ─────────────────────────────────────────────────────────────────────────
    //  Work Experience UI Component - Multiple Jobs Support
    // ─────────────────────────────────────────────────────────────────────────
    const WorkExperienceUI = {
        
        jobRoles: [
            "Painter", "Assistant Manager", "Server", "Assistant Store Manager", "Barista", "Cashier",
            "Coffee Specialist", "Cook", "Crew Member", "Customer Support",
            "Dining Room", "Dishwasher", "Drive Thru", "Grill Cook",
            "Guest Experience", "Host", "Kitchen Staff", "Maintenance",
            "Overnight Crew", "Prep Cook", "Prep Team", "Shift Coordinator",
            "Shift Lead", "Shift Leader", "Shift Manager", "Shift Supervisor",
            'Store Support', 'Team Lead', 'Team Member', 'Trainer'
        ],
        
        experiences: [],  // Store multiple experiences
        currentData: {
            company: '',
            role: '',
            startDate: '',
            endDate: ''
        },
        
        render() {
            const container = document.createElement('div');
            container.id = 'work-experience-ui';
            container.className = 'work-exp-container';
            
            container.innerHTML = `
                <style>
                    .work-exp-container {
                        background: #f0f0f5;
                        border-radius: 16px;
                        padding: 12px;
                        margin: 8px 0;
                        animation: slideDown 0.3s ease-out;
                    }
                    
                    @keyframes slideDown {
                        from { opacity: 0; transform: translateY(-20px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    
                    .work-exp-header {
                        font-size: 16px;
                        font-weight: 600;
                        color: #333;
                        margin-bottom: 16px;
                    }
                    
                    .work-exp-list {
                        margin-bottom: 16px;
                    }

                    .work-exp-subheading {
                        font-size: 12px;
                        font-weight: 600;
                        color: #667eea;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 8px;
                        margin-top: 8px;
                    }

                    .work-exp-edit-btn {
                        position: absolute;
                        top: 12px;
                        right: 12px;
                        background: transparent;
                        border: none;
                        color: #667eea;
                        font-size: 16px;
                        cursor: pointer;
                        padding: 6px;
                        border-radius: 6px;
                        transition: all 0.2s;
                        opacity: 0.7;
                    }

                    .work-exp-edit-btn:hover {
                        opacity: 1;
                        background: #f0f0f8;
                    }
                    
                    .work-exp-card {
                        position: relative;
                        background: white;
                        border-radius: 10px;
                        padding: 8px;
                        margin-bottom: 6px;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        border: 1px solid #e0e0e0;
                    }
                    
                    .work-exp-logo {
                        width: 40px;
                        height: 28px;
                        background: #667eea;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-weight: bold;
                        font-size: 14px;
                        flex-shrink: 0;
                    }
                    
                    .work-exp-details {
                        flex: 1;
                    }
                    
                    .work-exp-role {
                        font-weight: 600;
                        font-size: 14px;
                        color: #333;
                    }
                    
                    .work-exp-company {
                        font-size: 13px;
                        color: #666;
                    }
                    
                    .work-exp-dates {
                        font-size: 12px;
                        color: #999;
                    }
                    
                    .work-exp-form {
                        background: white;
                        border-radius: 10px;
                        padding: 10px;
                        margin-bottom: 10px;
                    }

                    .work-exp-form-heading {
                        font-size: 14px;
                        font-weight: 600;
                        color: #333;
                        margin-bottom: 14px;
                        padding-bottom: 10px;
                        border-bottom: 1px solid #e5e5e5;
                    }
                    
                    .work-exp-input-group {
                        margin-bottom: 14px;
                    }
                    
                    .work-exp-label {
                        display: block;
                        font-size: 12px;
                        font-weight: 500;
                        color: #555;
                        margin-bottom: 6px;
                    }
                    
                    .work-exp-input-wrapper {
                        position: relative;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }
                    
                    .work-exp-input,
                    .work-exp-select {
                        width: 100%;
                        padding: 7px 10px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        font-size: 12px;
                        font-family: inherit;
                        transition: border-color 0.2s;
                    }
                    
                    .work-exp-input:focus,
                    .work-exp-select:focus {
                        outline: none;
                        border-color: #667eea;
                    }
                    
                    .work-exp-voice-btn {
                        width: 36px;
                        height: 28px;
                        background: #f5f5f5;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-shrink: 0;
                        transition: all 0.2s;
                    }
                    
                    .work-exp-voice-btn:hover {
                        background: #e8e8e8;
                    }
                    
                    .work-exp-date-group {
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 8px;
                    }
                    
                    .work-exp-buttons {
                        display: flex;
                        gap: 10px;
                        margin-top: 16px;
                    }
                    
                    .work-exp-btn {
                        flex: 1;
                        padding: 8px;
                        border: none;
                        border-radius: 10px;
                        font-size: 12px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                    }
                    
                    .work-exp-btn-primary {
                        background: #667eea;
                        color: white;
                    }
                    
                    .work-exp-btn-primary:hover:not(:disabled) {
                        background: #5568d3;
                        transform: translateY(-1px);
                    }
                    
                    .work-exp-btn-primary:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                    }
                    
                    .work-exp-btn-secondary {
                        background: white;
                        color: #667eea;
                        border: 2px solid #667eea;
                    }
                    
                    .work-exp-btn-secondary:hover {
                        background: #f8f8fc;
                    }
                </style>
                
                <div class="work-exp-header">Work Experience</div>
                
                <!-- List of added experiences -->
                <div class="work-exp-list" id="work-exp-list"></div>
                
                <!-- Form for adding new experience -->
                <div class="work-exp-form" id="work-exp-form">
                    <div class="work-exp-form-heading" id="work-exp-form-heading">Most Recent</div>
                    <div class="work-exp-input-group">
                        <label class="work-exp-label">Company Name</label>
                        <div class="work-exp-input-wrapper">
                            <input 
                                type="text" 
                                id="work-exp-company" 
                                class="work-exp-input" 
                                placeholder="e.g., McDonald's"
                            />
                            <button class="work-exp-voice-btn" id="work-exp-voice-company" title="Voice input">
                                <i class="fa fa-microphone"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="work-exp-input-group">
                        <label class="work-exp-label">Role</label>
                        <select id="work-exp-role" class="work-exp-select">
                            <option value="">Select role</option>
                            ${this.jobRoles.map(role => `<option value="${role}">${role}</option>`).join('')}
                        </select>
                    </div>
                    
                    <div class="work-exp-date-group">
                        <div class="work-exp-input-group">
                            <label class="work-exp-label">Start Date</label>
                            <input 
                                type="month" 
                                id="work-exp-start-date" 
                                class="work-exp-input"
                            />
                        </div>
                        
                        <div class="work-exp-input-group">
                            <label class="work-exp-label">End Date</label>
                            <input 
                                type="month" 
                                id="work-exp-end-date" 
                                class="work-exp-input"
                            />
                        </div>
                    </div>
                    
                    <div class="work-exp-buttons">
                        <button class="work-exp-btn work-exp-btn-primary" id="work-exp-add-btn" disabled>
                            ✓ Add Job
                        </button>
                    </div>
                </div>
                
                <!-- Action buttons (shown after at least one job added) -->
                <div class="work-exp-buttons" id="work-exp-actions" style="display: none;">
                    <button class="work-exp-btn work-exp-btn-secondary" id="work-exp-add-another-btn">
                        + Additional Work Experience
                    </button>
                    <button class="work-exp-btn work-exp-btn-primary" id="work-exp-done-btn">
                        Continue →
                    </button>
                </div>
            `;
            
            return container;
        },
        
        renderExperienceList() {
            const listDiv = document.getElementById('work-exp-list');
            if (!listDiv) return;
            
            if (this.experiences.length === 0) {
                listDiv.innerHTML = '';
                return;
            }
            
            listDiv.innerHTML = this.experiences.map((exp, index) => {
                const initial = exp.company.charAt(0).toUpperCase();
                const heading = index === 0 ? '<div class="work-exp-subheading">Most Recent</div>' : '';
                return `
                    ${heading}
                    <div class="work-exp-card">
                        <div class="work-exp-avatar">${initial}</div>
                        <div class="work-exp-details">
                            <div class="work-exp-role">${exp.role}</div>
                            <div class="work-exp-company">${exp.company}</div>
                            <div class="work-exp-dates">${exp.startDate} to ${exp.endDate}</div>
                        </div>
                        <button class="work-exp-edit-btn" data-index="${index}">
                            <i class="fa fa-edit"></i>
                        </button>
                    </div>
                `;
            }).join('');

            // Add edit button event listeners
            listDiv.querySelectorAll('.work-exp-edit-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const index = parseInt(btn.getAttribute('data-index'));
                    this.editExperience(index);
                });
            });
        
        },
        
        attachEventListeners() {
            const companyInput = document.getElementById('work-exp-company');
            const roleSelect = document.getElementById('work-exp-role');
            const startDateInput = document.getElementById('work-exp-start-date');
            const endDateInput = document.getElementById('work-exp-end-date');
            const addBtn = document.getElementById('work-exp-add-btn');
            const voiceBtn = document.getElementById('work-exp-voice-company');
            const addAnotherBtn = document.getElementById('work-exp-add-another-btn');
            const doneBtn = document.getElementById('work-exp-done-btn');
            
            // Validate form as user types
            const validateForm = () => {
                const isValid = 
                    companyInput.value.trim() !== '' &&
                    roleSelect.value !== '' &&
                    startDateInput.value !== '' &&
                    endDateInput.value !== '';
                
                addBtn.disabled = !isValid;
            };
            
            companyInput.addEventListener('input', validateForm);
            roleSelect.addEventListener('change', validateForm);
            startDateInput.addEventListener('change', validateForm);
            endDateInput.addEventListener('change', validateForm);
            
            // Voice input for company name
            voiceBtn.addEventListener('click', () => {
                if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                    const recognition = new SpeechRecognition();
                    
                    recognition.onresult = (event) => {
                        const transcript = event.results[0][0].transcript;
                        companyInput.value = transcript;
                        validateForm();
                    };
                    
                    recognition.start();
                } else {
                    alert('Voice input not supported in this browser');
                }
            });
            
            // Add job button
            addBtn.addEventListener('click', () => {
                this.addExperience();
            });
            
            // Add another job button
            if (addAnotherBtn) {
                addAnotherBtn.addEventListener('click', () => {
                    this.showForm();
                });
            }
            
            // Done button
            if (doneBtn) {
                doneBtn.addEventListener('click', () => {
                    this.submitAllExperiences();
                });
            }
        },
        
        addExperience() {
            const company = document.getElementById('work-exp-company').value.trim();
            const role = document.getElementById('work-exp-role').value;
            const startDate = document.getElementById('work-exp-start-date').value;
            const endDate = document.getElementById('work-exp-end-date').value;
            
            if (!company || !role || !startDate || !endDate) {
                return;
            }
            
            // Add to experiences array
            this.experiences.push({
                company: company,
                role: role,
                startDate: startDate,
                endDate: endDate
            });
            
            console.log('[WorkExperienceUI] Added experience:', this.experiences[this.experiences.length - 1]);
            
            // Update the list
            this.renderExperienceList();
            
            // Clear form
            this.clearForm();
            
            // Hide form and show action buttons
            this.hideForm();
            this.showActionButtons();
        },
        
        clearForm() {
            document.getElementById('work-exp-company').value = '';
            document.getElementById('work-exp-role').value = '';
            document.getElementById('work-exp-start-date').value = '';
            document.getElementById('work-exp-end-date').value = '';
            document.getElementById('work-exp-add-btn').disabled = true;
        },
        
        showForm() {
            const form = document.getElementById('work-exp-form');
            const heading = document.getElementById('work-exp-form-heading');
            
            if (form) {
                form.style.display = 'block';
            }
            
            // Update heading based on number of experiences
            if (heading) {
                heading.textContent = this.experiences.length === 0 ? 'Most Recent' : 'Additional Job Experience';
                heading.style.color = '#333';  // Add this line to reset color
            }
        },
        
        hideForm() {
            const form = document.getElementById('work-exp-form');
            if (form) {
                form.style.display = 'none';
            }
        },

        editExperience(index) {
            const self = this;
            
            // Get the experience to edit
            const exp = this.experiences[index];
            
            // Remove from array (will be re-added when user clicks "Add Job")
            this.experiences.splice(index, 1);
            
            // Re-render the list (updates the cards)
            this.renderExperienceList();
            
            // Hide action buttons
            this.hideActionButtons();
            
            // Show the form FIRST (before populating)
            const form = document.getElementById('work-exp-form');
            if (form) {
                form.style.display = 'block';
            }
            
            // Small delay to ensure form is rendered, then populate
            setTimeout(() => {
                const companyInput = document.getElementById('work-exp-company');
                const roleInput = document.getElementById('work-exp-role');
                const startInput = document.getElementById('work-exp-start-date');
                const endInput = document.getElementById('work-exp-end-date');
                const heading = document.getElementById('work-exp-form-heading');
                
                if (companyInput) companyInput.value = exp.company;
                if (roleInput) roleInput.value = exp.role;
                if (startInput) startInput.value = exp.startDate;
                if (endInput) endInput.value = exp.endDate;
                
                // Update heading
                if (heading) {
                    heading.textContent = 'Edit Job Experience';
                    heading.style.color = '#667eea';
                }
                
                // Focus on company field
                if (companyInput) companyInput.focus();
                
            }, 50);  // Small delay ensures DOM is updated
        },
        
        showActionButtons() {
            const actions = document.getElementById('work-exp-actions');
            if (actions) {
                actions.style.display = 'flex';
            }
        },

        hideActionButtons() {
            const actions = document.getElementById('work-exp-actions');
            if (actions) {
                actions.style.display = 'none';
            }
        },
        
        submitAllExperiences() {
            if (this.experiences.length === 0) {
                console.error('[WorkExperienceUI] No experiences to submit');
                return;
            }

            console.log('[WorkExperienceUI] Submitting all experiences:', this.experiences);

            const summary = this.experiences.map(exp =>
                `${exp.role} at ${exp.company} (${exp.startDate} to ${exp.endDate})`
            ).join(', ');

            window.CleoChatbot.addMessage(`My experience: ${summary}`, false, 'body');
            window.CleoChatbot.showTypingIndicator();   // ← add this

            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'work_experience_data',
                    data: this.experiences
                }));
            }

            this.hide();   // ← move hide() to after send
        },
        
        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();
            
            // Scroll halfway to show UI without going to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollTop + (messagesDiv.clientHeight / 2),
                behavior: 'smooth'
            });
            
            // Disable normal input
            window.CleoChatbot.disableInput();
        },
        
        hide() {
            const ui = document.getElementById('work-experience-ui');
            if (ui) {
                ui.style.display = 'none';
                setTimeout(() => {
                    ui.remove();
                }, 100);
            }
            
            // Reset data
            this.experiences = [];
            this.currentData = {
                company: '',
                role: '',
                startDate: '',
                endDate: ''
            };
        }
    };
    
    // ─────────────────────────────────────────────────────────────────────────
    //  Education Level Checkbox UI Component
    // ─────────────────────────────────────────────────────────────────────────

    const EducationUI = {

        educationOptions: [
            'Less than high school',
            'High school or GED',
            'College degree',
            'Trade or certificate',
            'Prefer not to say'
        ],

        selectedOption: null,
        selectedYear: null,

        render() {
            const currentYear = new Date().getFullYear();
            const years = [];
            for (let y = currentYear; y >= 1960; y--) years.push(y);

            const container = document.createElement('div');
            container.id = 'education-ui';
            container.className = 'education-container';

            container.innerHTML = `
                <style>
                    .education-container {
                        background: #f0f0f5;
                        border-radius: 16px;
                        padding: 12px;
                        margin: 8px 0;
                        animation: slideDown 0.3s ease-out;
                    }
                    @keyframes slideDown {
                        from { opacity: 0; transform: translateY(-20px); }
                        to   { opacity: 1; transform: translateY(0); }
                    }
                    .edu-option {
                        background: white;
                        border-radius: 10px;
                        padding: 8px 12px;
                        margin-bottom: 6px;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        cursor: pointer;
                        transition: all 0.2s ease;
                        border: 2px solid transparent;
                        user-select: none;
                    }
                    .edu-option:hover {
                        background: #f8f8fc;
                        transform: translateX(4px);
                    }
                    .edu-option.selected {
                        background: #e8eaff;
                        border-color: #667eea;
                    }
                    .edu-checkbox {
                        width: 20px;
                        height: 16px;
                        border: 2px solid #999;
                        border-radius: 4px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-shrink: 0;
                        transition: all 0.2s ease;
                    }
                    .edu-option.selected .edu-checkbox {
                        background: #667eea;
                        border-color: #667eea;
                    }
                    .edu-checkbox-icon {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        display: none;
                    }
                    .edu-option.selected .edu-checkbox-icon {
                        display: block;
                    }
                    .edu-label {
                        flex: 1;
                        font-size: 13px;
                        color: #333;
                    }
                    .edu-year-section {
                        background: white;
                        border-radius: 12px;
                        padding: 14px 16px;
                        margin-top: 4px;
                        margin-bottom: 4px;
                        display: none;
                        animation: slideDown 0.2s ease-out;
                    }
                    .edu-year-section.visible {
                        display: block;
                    }
                    .edu-year-label {
                        font-size: 13px;
                        font-weight: 600;
                        color: #555;
                        margin-bottom: 10px;
                    }
                    .edu-year-select {
                        width: 100%;
                        padding: 10px 14px;
                        border: 2px solid #e0e0e0;
                        border-radius: 10px;
                        font-size: 14px;
                        color: #333;
                        background: #fafafa;
                        appearance: none;
                        cursor: pointer;
                        transition: border-color 0.2s ease;
                        outline: none;
                    }
                    .edu-year-select:focus {
                        border-color: #667eea;
                        background: white;
                    }
                    .edu-confirm-btn {
                        width: 40px;
                        height: 32px;
                        background: #667eea;
                        color: white;
                        border: none;
                        border-radius: 50%;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 10px auto 0;
                        font-size: 16px;
                        transition: all 0.2s ease;
                    }
                    .edu-confirm-btn:hover:not(:disabled) {
                        background: #5568d3;
                        transform: scale(1.1);
                    }
                    .edu-confirm-btn:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                        transform: scale(1);
                    }
                </style>

                <div class="edu-options-list" id="edu-options-list">
                    ${this.educationOptions.map(option => `
                        <div class="edu-option" data-value="${option}">
                            <div class="edu-checkbox">
                                <span class="edu-checkbox-icon">✓</span>
                            </div>
                            <div class="edu-label">${option}</div>
                        </div>
                    `).join('')}
                </div>

                <!-- Year picker — shown after selecting an option -->
                <div class="edu-year-section" id="edu-year-section">
                    <div class="edu-year-label">📅 Approximately when did you complete this?</div>
                    <select class="edu-year-select" id="edu-year-select">
                        <option value="">— Select year —</option>
                        ${years.map(y => `<option value="${y}">${y}</option>`).join('')}
                        <option value="Prefer not to say">Prefer not to say</option>
                    </select>
                </div>

                <button class="edu-confirm-btn" id="edu-confirm-btn" disabled>✓</button>
            `;

            return container;
        },

        attachEventListeners() {
            const self = this;

            const optionsList = document.getElementById('edu-options-list');
            const confirmBtn  = document.getElementById('edu-confirm-btn');
            const yearSection = document.getElementById('edu-year-section');
            const yearSelect  = document.getElementById('edu-year-select');

            if (!optionsList || !confirmBtn) {
                console.error('[EducationUI] Elements not found!');
                return;
            }

            // Select education level
            optionsList.addEventListener('click', function(e) {
                const option = e.target.closest('.edu-option');
                if (!option) return;

                const value = option.getAttribute('data-value');

                // Unselect all, select clicked
                optionsList.querySelectorAll('.edu-option').forEach(o => o.classList.remove('selected'));
                option.classList.add('selected');

                self.selectedOption = value;
                self.selectedYear   = null;

                // Show year picker (hide for "Prefer not to say")
                if (value === 'Prefer not to say') {
                    yearSection.classList.remove('visible');
                    self.selectedYear = 'Not specified';
                    confirmBtn.disabled = false;
                } else {
                    yearSection.classList.add('visible');
                    yearSelect.value    = '';
                    confirmBtn.disabled = true;  // wait for year
                }

                console.log('[EducationUI] Selected:', value);
            });

            // Year selection enables confirm
            yearSelect.addEventListener('change', function() {
                self.selectedYear   = this.value;
                confirmBtn.disabled = !this.value;
                console.log('[EducationUI] Year selected:', self.selectedYear);
            });

            confirmBtn.addEventListener('click', function() {
                self.submitEducation();
            });
        },

        submitEducation() {
        if (!this.selectedOption) {
            console.error('[EducationUI] No education selected!');
            return;
        }

        const submittedValue = this.selectedYear && this.selectedYear !== 'Not specified'
            ? `${this.selectedOption}, ${this.selectedYear}`
            : this.selectedOption;

        console.log('[EducationUI] Submitting:', submittedValue);

        this.hide();

        if (window.CleoChatbot && window.CleoChatbot.ws && window.CleoChatbot.ws.readyState === WebSocket.OPEN) {
            window.CleoChatbot.addMessage(submittedValue, false, 'body');
            window.CleoChatbot.showTypingIndicator();          // ← add this

            window.CleoChatbot.ws.send(JSON.stringify({
                type: 'user_message',
                content: submittedValue
            }));
        } else {
            console.error('[EducationUI] WebSocket not ready!');
            window.CleoChatbot.enableInput();
        }
    },

        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            if (!messagesDiv) return;

            const ui = this.render();
            messagesDiv.appendChild(ui);

            this.selectedOption = null;
            this.selectedYear   = null;

            this.attachEventListeners();

            // Scroll halfway to show UI without going to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollTop + (messagesDiv.clientHeight / 2),
                behavior: 'smooth'
            });

            if (window.CleoChatbot) window.CleoChatbot.disableInput();
        },

        hide() {
            const ui = document.getElementById('education-ui');
            if (ui) {
                ui.style.display = 'none';
                setTimeout(() => ui.remove(), 100);
            }
            this.selectedOption = null;
            this.selectedYear   = null;
        }
    };

    // ─────────────────────────────────────────────────────────────────────────
    // AddressUI — Google Places Autocomplete
    // ─────────────────────────────────────────────────────────────────────────

    const AddressUI = {

        selectedAddress: null,
        sessionToken: null,
        debounceTimer: null,

        generateSessionToken() {
            // Simple UUID v4 for Places API session billing
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                const r = Math.random() * 16 | 0;
                return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
            });
        },

        render() {
            this.sessionToken = this.generateSessionToken();

            const container = document.createElement('div');
            container.id = 'address-ui';
            container.innerHTML = `
                <style>
                    .address-container {
                        background: #f0f0f5;
                        border-radius: 16px;
                        padding: 12px;
                        margin: 8px 0;
                        animation: slideDown 0.3s ease-out;
                    }

                    .address-input-wrapper {
                        position: relative;
                    }

                    .address-input {
                        width: 100%;
                        padding: 8px 12px;
                        border: 2px solid #ddd;
                        border-radius: 12px;
                        font-size: 13px;
                        font-family: inherit;
                        box-sizing: border-box;
                        transition: border-color 0.2s;
                        background: white;
                    }

                    .address-input:focus {
                        outline: none;
                        border-color: #667eea;
                    }

                    .address-suggestions {
                        position: absolute;
                        top: calc(100% + 4px);
                        left: 0;
                        right: 0;
                        background: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
                        z-index: 9999;
                        max-height: 160px;
                        overflow-y: auto;
                    }

                    .address-suggestion-item {
                        padding: 8px 12px;
                        cursor: pointer;
                        font-size: 12px;
                        color: #333;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        border-bottom: 1px solid #f5f5f5;
                        transition: background 0.15s;
                    }

                    .address-suggestion-item:last-child {
                        border-bottom: none;
                    }

                    .address-suggestion-item:hover {
                        background: #f0f0f8;
                    }

                    .address-pin-icon {
                        color: #667eea;
                        font-size: 13px;
                        flex-shrink: 0;
                    }

                    .address-confirm-btn {
                        width: 100%;
                        margin-top: 14px;
                        padding: 9px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 12px;
                        font-size: 15px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s;
                        font-family: inherit;
                    }

                    .address-confirm-btn:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                    }

                    .address-confirm-btn:hover:not(:disabled) {
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(102,126,234,0.4);
                    }

                    .address-selected-badge {
                        margin-top: 10px;
                        padding: 10px 14px;
                        background: #e8f5e9;
                        border: 1px solid #a5d6a7;
                        border-radius: 10px;
                        font-size: 13px;
                        color: #2e7d32;
                        display: none;
                    }
                </style>

                <div class="address-container">
                    <div class="address-input-wrapper">
                        <input
                            type="text"
                            id="address-input"
                            class="address-input"
                            placeholder="Start typing your address..."
                            autocomplete="off"
                        />
                        <div class="address-suggestions" id="address-suggestions" style="display:none;"></div>
                    </div>

                    <div class="address-selected-badge" id="address-selected-badge">
                        <i class="fa fa-check-circle"></i> <span id="address-selected-text"></span>
                    </div>

                    <button class="address-confirm-btn" id="address-confirm-btn" disabled>
                        Confirm Address
                    </button>
                </div>
            `;

            return container;
        },

        attachEventListeners() {
            const input = document.getElementById('address-input');
            const suggestionsDiv = document.getElementById('address-suggestions');
            const confirmBtn = document.getElementById('address-confirm-btn');
            const badge = document.getElementById('address-selected-badge');
            const badgeText = document.getElementById('address-selected-text');

            // Debounced autocomplete fetch
            input.addEventListener('input', () => {
                clearTimeout(this.debounceTimer);
                this.selectedAddress = null;
                confirmBtn.disabled = true;
                badge.style.display = 'none';

                const value = input.value.trim();
                if (value.length < 3) {
                    suggestionsDiv.style.display = 'none';
                    return;
                }

                this.debounceTimer = setTimeout(() => this.fetchSuggestions(value), 300);
            });

            // Hide suggestions when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('#address-ui')) {
                    suggestionsDiv.style.display = 'none';
                }
            });

            confirmBtn.addEventListener('click', () => this.submitAddress());
        },

        async fetchSuggestions(query) {
            try {
                const apiUrl = window.CleoChatbot.config.apiUrl;
                const res = await fetch(
                    `${apiUrl}/places/autocomplete?input=${encodeURIComponent(query)}&session_token=${this.sessionToken}`
                );
                const data = await res.json();

                this.renderSuggestions(data.predictions || []);
            } catch (err) {
                console.error('[AddressUI] Autocomplete fetch error:', err);
            }
        },

        renderSuggestions(predictions) {
            const suggestionsDiv = document.getElementById('address-suggestions');

            if (!predictions.length) {
                suggestionsDiv.style.display = 'none';
                return;
            }

            suggestionsDiv.innerHTML = predictions.map(p => `
                <div class="address-suggestion-item" data-place-id="${p.place_id}">
                    <i class="fa fa-map-marker-alt address-pin-icon"></i>
                    <span>${p.description}</span>
                </div>
            `).join('');

            suggestionsDiv.style.display = 'block';

            // Click handler for each suggestion
            suggestionsDiv.querySelectorAll('.address-suggestion-item').forEach(item => {
                item.addEventListener('click', async () => {
                    const placeId = item.getAttribute('data-place-id');
                    const description = item.querySelector('span').textContent;

                    suggestionsDiv.style.display = 'none';

                    // Fetch structured address details
                    await this.selectAddress(placeId, description);
                });
            });
        },

        async selectAddress(placeId, description) {
            try {
                const input = document.getElementById('address-input');
                const confirmBtn = document.getElementById('address-confirm-btn');
                const badge = document.getElementById('address-selected-badge');
                const badgeText = document.getElementById('address-selected-text');

                input.value = description;

                // Fetch structured address from backend
                const apiUrl = window.CleoChatbot.config.apiUrl;
                const res = await fetch(`${apiUrl}/places/details?place_id=${placeId}`);
                const details = await res.json();

                this.selectedAddress = details;

                console.log('[AddressUI] Selected address details:', details);

                // Show green badge
                badge.style.display = 'block';
                badgeText.textContent = details.full || description;

                // Enable confirm button
                confirmBtn.disabled = false;

            } catch (err) {
                console.error('[AddressUI] Error fetching place details:', err);
                // Fallback to plain text
                this.selectedAddress = { full: document.getElementById('address-input').value };
                document.getElementById('address-confirm-btn').disabled = false;
            }
        },

        submitAddress() {
            if (!this.selectedAddress) return;

            console.log('[AddressUI] Submitting address:', this.selectedAddress);

            // Show user's address as a chat message
            window.CleoChatbot.addMessage(
                this.selectedAddress.full || 'Address provided',
                false,
                'body'
            );

            // Send to backend via WebSocket
            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'address_data',
                    data: this.selectedAddress
                }));
            }

            window.CleoChatbot.showTypingIndicator();
            this.hide();
        },

        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();

            messagesDiv.scrollTo({ top: messagesDiv.scrollHeight, behavior: 'smooth' });
            window.CleoChatbot.disableInput();
        },

        hide() {
            const ui = document.getElementById('address-ui');
            if (ui) {
                ui.style.display = 'none';
                setTimeout(() => ui.remove(), 100);
            }
            this.selectedAddress = null;
        }
    };


    // ─────────────────────────────────────────────────────────────────────────
    // LocationVerificationUI — GPS Share Button
    // ─────────────────────────────────────────────────────────────────────────

    const LocationVerificationUI = {

        render() {
            const container = document.createElement('div');
            container.id = 'location-verification-ui';
            container.innerHTML = `
                <style>
                    .location-verify-container {
                        background: #f0f0f5;
                        border-radius: 16px;
                        padding: 20px;
                        margin: 16px 0;
                        text-align: center;
                        animation: slideDown 0.3s ease-out;
                    }

                    .location-icon-circle {
                        width: 64px;
                        height: 64px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 16px;
                        font-size: 28px;
                        color: white;
                    }

                    .location-verify-title {
                        font-size: 16px;
                        font-weight: 600;
                        color: #333;
                        margin-bottom: 6px;
                    }

                    .location-verify-subtitle {
                        font-size: 13px;
                        color: #888;
                        margin-bottom: 20px;
                        line-height: 1.4;
                    }

                    .location-share-btn {
                        width: 100%;
                        padding: 14px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 12px;
                        font-size: 15px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.2s;
                        font-family: inherit;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 8px;
                        margin-bottom: 10px;
                    }

                    .location-share-btn:hover:not(:disabled) {
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(102,126,234,0.4);
                    }

                    .location-share-btn:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                        transform: none;
                    }

                    .location-skip-btn {
                        width: 100%;
                        padding: 11px;
                        background: transparent;
                        color: #888;
                        border: 1px solid #ddd;
                        border-radius: 12px;
                        font-size: 14px;
                        cursor: pointer;
                        font-family: inherit;
                        transition: all 0.2s;
                    }

                    .location-skip-btn:hover {
                        background: #f5f5f5;
                        color: #555;
                    }

                    .location-status {
                        margin-top: 14px;
                        padding: 10px 14px;
                        border-radius: 10px;
                        font-size: 13px;
                        display: none;
                    }

                    .location-status.loading {
                        background: #e3f2fd;
                        color: #1565c0;
                        display: block;
                    }

                    .location-status.success {
                        background: #e8f5e9;
                        color: #2e7d32;
                        display: block;
                    }

                    .location-status.error {
                        background: #fce4ec;
                        color: #c62828;
                        display: block;
                    }
                </style>

                <div class="location-verify-container">
                    <div class="location-icon-circle">
                        <i class="fa fa-map-marker-alt"></i>
                    </div>
                    <div class="location-verify-title">Location Verification</div>
                    <div class="location-verify-subtitle">
                        This helps confirm your proximity to our location.<br>
                        Your GPS data is only used for this verification.
                    </div>

                    <button class="location-share-btn" id="location-share-btn">
                        <i class="fa fa-crosshairs"></i>
                        Share My Location
                    </button>

                    <button class="location-skip-btn" id="location-skip-btn">
                        Skip for now
                    </button>

                    <div class="location-status" id="location-status"></div>
                </div>
            `;
            return container;
        },

        attachEventListeners() {
            const shareBtn = document.getElementById('location-share-btn');
            const skipBtn = document.getElementById('location-skip-btn');
            const status = document.getElementById('location-status');

            shareBtn.addEventListener('click', () => {
                if (!navigator.geolocation) {
                    this.showStatus('error', 'Geolocation is not supported by your browser.');
                    return;
                }

                shareBtn.disabled = true;
                this.showStatus('loading', '📍 Getting your location...');

                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;

                        console.log('[LocationVerificationUI] GPS obtained:', { lat, lng });

                        this.showStatus('success', '✓ Location captured successfully!');

                        setTimeout(() => this.submitGPS(lat, lng), 800);
                    },
                    (error) => {
                        shareBtn.disabled = false;
                        const messages = {
                            1: 'Location permission denied. Please allow location access and try again.',
                            2: 'Could not determine your location. Please try again.',
                            3: 'Location request timed out. Please try again.'
                        };
                        this.showStatus('error', messages[error.code] || 'Location error. Please try again.');
                    },
                    { timeout: 10000, enableHighAccuracy: true }
                );
            });

            skipBtn.addEventListener('click', () => {
                console.log('[LocationVerificationUI] User skipped GPS verification');
                this.submitGPS(null, null, true);   // skipped = true
            });
        },

        showStatus(type, message) {
            const status = document.getElementById('location-status');
            status.className = `location-status ${type}`;
            status.textContent = message;
        },

        async submitGPS(lat, lng, skipped = false) {
            let displayMsg;

            if (skipped) {
                displayMsg = 'Location sharing skipped';
            } else {
                // Get place name from reverse geocoding
                const placeName = await this.getPlaceName(lat, lng);
                
                displayMsg = `📍 Location Shared\nPlace: ${placeName}\nCoords: ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
            }

            window.CleoChatbot.addMessage(displayMsg, false, 'body');

            // Send to backend
            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'gps_data',
                    data: {
                        lat: lat,
                        lng: lng,
                        skipped: skipped
                    }
                }));
            }

            window.CleoChatbot.showTypingIndicator();
            this.hide();
        },

        async getPlaceName(lat, lng) {
            try {
                const apiUrl = window.CleoChatbot.config.apiUrl;
                const res = await fetch(
                    `${apiUrl}/places/reverse-geocode?lat=${lat}&lng=${lng}`
                );
                const data = await res.json();

                // Extract meaningful place name from formatted_address
                // "123 Main St, Plainville, CT 06062, USA" → "Plainville, CT"
                const components = data.components || {};
                const city = components.city || '';
                const state = components.state || '';

                if (city && state) {
                    return `${city}, ${state}`;
                } else {
                    // Fallback: use first part of formatted address
                    const parts = data.formatted_address?.split(',') || [];
                    return parts.slice(0, 2).join(',').trim() || 'Unknown Location';
                }
            } catch (err) {
                console.error('[LocationVerificationUI] Reverse geocode error:', err);
                return 'Unknown Location';
            }
        },

        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();

            // Scroll halfway to show UI without going to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollTop + (messagesDiv.clientHeight / 2),
                behavior: 'smooth'
            });
            window.CleoChatbot.disableInput();
        },

        hide() {
            const ui = document.getElementById('location-verification-ui');
            if (ui) {
                ui.style.display = 'none';
                setTimeout(() => ui.remove(), 100);
            }
        }
    };

    // ─────────────────────────────────────────────────────────────────────────
    // IdVerificationUI — ID Verification Component (Card + Modal)
    // ─────────────────────────────────────────────────────────────────────────

    const IdVerificationUI = {

        verifyLink: "",

        // ── Card rendered in chat ─────────────────────────────────────────────
        render() {
            const card = document.createElement("div");
            card.id = "id-verification-ui";
            card.style.cssText = `
                margin: 12px 0;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
            `;

            card.innerHTML = `
                <style>
                    #id-verification-ui .idv-card {
                        background: #ffffff;
                        border: 1.5px solid #e2e8f0;
                        border-radius: 16px;
                        padding: 20px;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                        max-width: 340px;
                    }
                    #id-verification-ui .idv-header {
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        margin-bottom: 16px;
                    }
                    #id-verification-ui .idv-shield {
                        width: 42px;
                        height: 42px;
                        background: linear-gradient(135deg, #1a73e8, #0d47a1);
                        border-radius: 10px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 20px;
                        flex-shrink: 0;
                        box-shadow: 0 2px 8px rgba(26,115,232,0.35);
                    }
                    #id-verification-ui .idv-title {
                        font-size: 15px;
                        font-weight: 700;
                        color: #1a1a2e;
                        line-height: 1.2;
                    }
                    #id-verification-ui .idv-subtitle {
                        font-size: 11px;
                        color: #94a3b8;
                        margin-top: 2px;
                    }
                    #id-verification-ui .idv-divider {
                        height: 1px;
                        background: #f1f5f9;
                        margin: 14px 0;
                    }
                    #id-verification-ui .idv-steps-label {
                        font-size: 12px;
                        font-weight: 600;
                        color: #64748b;
                        text-transform: uppercase;
                        letter-spacing: 0.06em;
                        margin-bottom: 10px;
                    }
                    #id-verification-ui .idv-step {
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        margin-bottom: 8px;
                    }
                    #id-verification-ui .idv-step-icon {
                        width: 30px;
                        height: 30px;
                        background: #eff6ff;
                        border-radius: 8px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 14px;
                        flex-shrink: 0;
                    }
                    #id-verification-ui .idv-step-text {
                        font-size: 13px;
                        color: #334155;
                        font-weight: 500;
                    }
                    #id-verification-ui .idv-btn-primary {
                        width: 100%;
                        padding: 13px;
                        background: linear-gradient(135deg, #1a73e8, #1557b0);
                        color: #ffffff;
                        border: none;
                        border-radius: 10px;
                        font-size: 13px;
                        font-weight: 700;
                        letter-spacing: 0.04em;
                        cursor: pointer;
                        margin-top: 16px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 8px;
                        transition: transform 0.15s ease, box-shadow 0.15s ease;
                        box-shadow: 0 3px 12px rgba(26,115,232,0.4);
                    }
                    #id-verification-ui .idv-btn-primary:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 5px 18px rgba(26,115,232,0.5);
                    }
                    #id-verification-ui .idv-btn-primary:active {
                        transform: translateY(0);
                    }
                    #id-verification-ui .idv-disclaimer {
                        font-size: 10.5px;
                        color: #94a3b8;
                        text-align: center;
                        margin-top: 12px;
                        line-height: 1.5;
                    }
                    #id-verification-ui .idv-footer-links {
                        font-size: 11px;
                        color: #94a3b8;
                        text-align: center;
                        margin-top: 8px;
                    }
                    #id-verification-ui .idv-footer-links a {
                        color: #1a73e8;
                        text-decoration: none;
                        font-weight: 500;
                    }
                    #id-verification-ui .idv-footer-links a:hover {
                        text-decoration: underline;
                    }

                    /* ── Modal styles ── */
                    #idv-modal-overlay {
                        display: none;
                        position: fixed;
                        inset: 0;
                        background: rgba(0,0,0,0.6);
                        z-index: 9999999;
                        align-items: center;
                        justify-content: center;
                    }
                    #idv-modal-overlay.active {
                        display: flex;
                    }
                    #idv-modal {
                        background: #ffffff;
                        border-radius: 16px;
                        width: 90%;
                        max-width: 480px;
                        max-height: 90vh;
                        display: flex;
                        flex-direction: column;
                        overflow: hidden;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        animation: idvModalIn 0.25s ease-out;
                    }
                    @keyframes idvModalIn {
                        from { opacity: 0; transform: scale(0.95) translateY(10px); }
                        to   { opacity: 1; transform: scale(1) translateY(0); }
                    }
                    #idv-modal-header {
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        padding: 16px 20px;
                        border-bottom: 1px solid #e2e8f0;
                        flex-shrink: 0;
                    }
                    #idv-modal-header-left {
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }
                    #idv-modal-title {
                        font-size: 15px;
                        font-weight: 700;
                        color: #1a1a2e;
                    }
                    #idv-modal-close {
                        width: 32px;
                        height: 32px;
                        border: none;
                        background: #f1f5f9;
                        border-radius: 8px;
                        font-size: 18px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: #64748b;
                        transition: background 0.15s;
                    }
                    #idv-modal-close:hover {
                        background: #e2e8f0;
                        color: #1a1a2e;
                    }
                    #idv-modal-iframe {
                        flex: 1;
                        border: none;
                        width: 100%;
                        min-height: 500px;
                    }
                    #idv-modal-status {
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        padding: 12px 20px;
                        border-top: 1px solid #f1f5f9;
                        flex-shrink: 0;
                    }
                    #idv-modal-status-text {
                        font-size: 12px;
                        color: #64748b;
                    }
                    #idv-modal-status-badge {
                        font-size: 11px;
                        font-weight: 600;
                        color: #f59e0b;
                        background: #fef3c7;
                        padding: 3px 10px;
                        border-radius: 20px;
                        transition: all 0.3s ease;
                    }
                    #idv-modal-status-badge.success {
                        color: #16a34a;
                        background: #dcfce7;
                    }
                    #idv-modal-status-badge.failed {
                        color: #dc2626;
                        background: #fee2e2;
                    }
                </style>

                <!-- ── Chat card ── -->
                <div class="idv-card">
                    <div class="idv-header">
                        <div class="idv-shield">🛡️</div>
                        <div>
                            <div class="idv-title">Identity Verification</div>
                            <div class="idv-subtitle">Securely powered by Simplici</div>
                        </div>
                    </div>

                    <div class="idv-divider"></div>

                    <div class="idv-steps-label">Steps:</div>
                    <div class="idv-step">
                        <div class="idv-step-icon">📷</div>
                        <div class="idv-step-text">1. Snap a photo of ID (Front &amp; Back)</div>
                    </div>
                    <div class="idv-step">
                        <div class="idv-step-icon">🤳</div>
                        <div class="idv-step-text">2. Take a quick 3D liveness selfie</div>
                    </div>

                    <button id="idv-start-btn" class="idv-btn-primary">
                        START SECURE VERIFICATION 🔒
                    </button>

                    <p class="idv-disclaimer">
                        By clicking, you agree to our secure identity verification process.<br>
                        We do not store your raw biometric data.
                    </p>

                    <div class="idv-footer-links">
                        Stuck?
                        <a href="#" id="idv-refresh-link">Click here to refresh</a>
                        or
                        <a href="mailto:support@scanandhire.com">Contact Support</a>
                    </div>
                </div>

                <!-- ── Modal overlay (appended to body, not card) ── -->
            `;

            return card;
        },

        // ── Create and inject modal into document.body ────────────────────────
        createModal() {
            // Remove any existing modal first
            const existing = document.getElementById("idv-modal-overlay");
            if (existing) existing.remove();

            const overlay = document.createElement("div");
            overlay.id = "idv-modal-overlay";
            overlay.innerHTML = `
                <div id="idv-modal">
                    <div id="idv-modal-header">
                        <div id="idv-modal-header-left">
                            <span style="font-size:18px;">🛡️</span>
                            <span id="idv-modal-title">Identity Verification</span>
                        </div>
                        <button id="idv-modal-close" title="Close">✕</button>
                    </div>
                    <iframe
                        id="idv-modal-iframe"
                        src="${this.verifyLink}"
                        allow="camera; microphone"
                        allowfullscreen
                    ></iframe>
                    <div id="idv-modal-status">
                        <span id="idv-modal-status-text">Status</span>
                        <span id="idv-modal-status-badge">⏳ Verification in progress...</span>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            // Close button
            document.getElementById("idv-modal-close").addEventListener("click", () => {
                this.closeModal();
            });

            // Click outside modal to close
            overlay.addEventListener("click", (e) => {
                if (e.target === overlay) this.closeModal();
            });
        },

        openModal() {
            this.createModal();
            document.getElementById("idv-modal-overlay").classList.add("active");
        },

        closeModal() {
            const overlay = document.getElementById("idv-modal-overlay");
            if (overlay) {
                overlay.style.opacity = "0";
                overlay.style.transition = "opacity 0.2s ease";
                setTimeout(() => overlay.remove(), 200);
            }
        },

        attachEventListeners() {
            const startBtn  = document.getElementById("idv-start-btn");
            const refreshLk = document.getElementById("idv-refresh-link");

            // Open modal on START button click
            startBtn.addEventListener("click", () => {
                this.openModal();
            });

            // Refresh link — re-open modal
            refreshLk.addEventListener("click", (e) => {
                e.preventDefault();
                this.openModal();
            });
        },

        // Called by webhook push via handleMessage → auto-closes modal
        showWebhookResult(verified) {
            const badge = document.getElementById("idv-modal-status-badge");

            if (badge) {
                if (verified) {
                    badge.textContent = "✅ Verified! Closing...";
                    badge.classList.add("success");
                } else {
                    badge.textContent = "⚠️ Needs manual review. Closing...";
                    badge.classList.add("failed");
                }
            }
        },

        show(verifyLink) {
            this.verifyLink = verifyLink || "";

            const messagesDiv = document.getElementById("chatbot-messages");
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();

            // Scroll halfway to show UI without going to bottom
            messagesDiv.scrollTo({
                top: messagesDiv.scrollTop + (messagesDiv.clientHeight / 2),
                behavior: 'smooth'
            });
            
            window.CleoChatbot.disableInput();
        },

        hide() {
            const ui = document.getElementById("id-verification-ui");
            if (ui) {
                ui.style.display = "none";
                setTimeout(() => ui.remove(), 100);
            }
            this.closeModal();
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
                         document.querySelector('[data-job-type]') || document.querySelector('[data-mode="passport"]');

        if (!container) {
            console.error('CleoChatbot: Container element with data-job-type attribute not found');
            return;
        }

        // const jobType = container.dataset.jobType;
    
        // Read Values from data attribute
        const mode = container.getAttribute('data-mode') || 'job';
        const jobLocation = container.getAttribute('data-job-location') ||'unknown';
        const jobType = container.getAttribute('data-job-type') || 'Position';

        const jobTemplateID = container.getAttribute('data-job-templates-id') || '456';
        const jobID = container.getAttribute('data-job-id') || '123';
        const companyID = container.getAttribute('data-company-id') || '987';
        const isLive = container.getAttribute('data-isLive') === 'true';
        const brandName = container.getAttribute('data-brand-name') || "";
        const jobShift  = container.getAttribute('data-job-shift')  || "";
        const verificationRequired = container.getAttribute('data-verification-required') || 'false';
        const singleCompany = container.getAttribute('data-single-company') === 'true';
       
        console.log('CleoChatbot: jobType from data attribute:', container.getAttribute('data-job-type'));
        console.log('CleoChatbot: jobTemplateID from data attribute:', jobTemplateID);
        console.log('CleoChatbot: jobLocation from data attribute:', container.getAttribute('data-job-location'));
        console.log('CleoChatbot: jobID from data attribute:', container.getAttribute('data-job-id'));
        console.log('CleoChatbot: companyID from data attribute:', container.getAttribute('data-company-id'));
        console.log('CleoChatbot: isLive from data attribute:', isLive);
        console.log('CleoChatbot: jobShift from data attribute:', jobShift);
        console.log('CleoChatbot: brandName from data attribute:', brandName);
        console.log('CleoChatbot: verificationRequired from data attribute:', verificationRequired);
        console.log('CleoChatbot: singleCompany from data attribute:', singleCompany);
        if (!jobType) {
            console.error('CleoChatbot: job_type is required to initialize the chatbot');
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
                mode: mode,
                jobType: jobType,  // Use jobType from data attribute
                jobTemplateID: jobTemplateID, // Pass jobTemplate
                jobLocation: jobLocation,
                jobID: jobID,
                companyID: companyID,
                isLive: isLive,
                jobShift: jobShift,
                brandName: brandName,
                verificationRequired: verificationRequired,
                singleCompany: singleCompany,
                apiKey: config.apiKey,
                apiUrl: CHATBOT_CONFIG.apiBaseUrl,
                wsUrl: CHATBOT_CONFIG.wsBaseUrl
            });

            console.log('CleoChatbot initialized successfully for job type:', jobType);
            console.log('CleoChatbot: jobTemplateID initialized:', jobTemplateID);

        } catch (error) {
            console.error('CleoChatbot initialization failed:', error.message);
            // Optionally show error to user
            alert(`Failed to load chatbot: ${error.message}`);
        }
    }

    // Initialize when DOM is ready
    function tryInit() {
        const container = document.getElementById('cleo-chatbot') || document.querySelector('[data-job-type]' ) || document.querySelector('[data-mode="passport"]');
        if (container && (container.getAttribute('data-job-id') || container.getAttribute('data-mode') === 'passport')) {
            // Attributes already set — init immediately
            autoInitChatbot();
        } 
        else {
            // Wait for job_details.html to finish setting attributes
            document.addEventListener('cleoJobReady', autoInitChatbot, { once: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', tryInit);
    } 
    else {
        tryInit();
    }
    
})(window);