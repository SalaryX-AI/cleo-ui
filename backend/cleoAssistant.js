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
                height: 540px;
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
                    
                    /* Smooth transitions for message bubbles */
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


    /**
     * Work Experience Interactive UI Component
     */
    const WorkExperienceUI = {
        
        // 28 job roles from your configs
        jobRoles: [
            'Assistant Manager', 'Assistant Store Manager', 'Barista', 'Cashier',
            'Coffee Specialist', 'Cook', 'Crew Member', 'Customer Support',
            'Dining Room', 'Dishwasher', 'Drive Thru', 'Grill Cook',
            'Guest Experience', 'Host', 'Kitchen Staff', 'Maintenance',
            'Overnight Crew', 'Prep Cook', 'Prep Team', 'Shift Coordinator',
            'Shift Lead', 'Shift Leader', 'Shift Manager', 'Shift Supervisor',
            'Store Support', 'Team Lead', 'Team Member', 'Trainer'
        ],
        
        currentData: {
            company: '',
            role: '',
            startDate: '',
            endDate: ''
        },
        
        render() {
            const container = document.createElement('div');
            container.id = 'work-experience-ui';
            container.className = 'work-experience-container';
            
            container.innerHTML = `
                <style>
                    .work-experience-container {
                        background: #f0f0f5;
                        border-radius: 16px;
                        padding: 20px;
                        margin: 16px 0;
                        animation: slideDown 0.3s ease-out;
                    }
                    
                    @keyframes slideDown {
                        from {
                            opacity: 0;
                            transform: translateY(-20px);
                        }
                        to {
                            opacity: 1;
                            transform: translateY(0);
                        }
                    }
                    
                    .we-header {
                        font-size: 14px;
                        font-weight: 600;
                        color: #666;
                        margin-bottom: 16px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }
                    
                    .we-add-icon {
                        width: 24px;
                        height: 24px;
                        background: #667eea;
                        color: white;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 18px;
                    }
                    
                    .we-input-group {
                        background: white;
                        border-radius: 12px;
                        padding: 12px 16px;
                        margin-bottom: 12px;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }
                    
                    .we-input {
                        flex: 1;
                        border: none;
                        outline: none;
                        font-size: 15px;
                        color: #333;
                    }
                    
                    .we-input::placeholder {
                        color: #999;
                    }
                    
                    .we-voice-icon {
                        width: 20px;
                        height: 20px;
                        cursor: pointer;
                    }
                    
                    .we-card {
                        background: white;
                        border-radius: 12px;
                        padding: 16px;
                        margin-bottom: 12px;
                        display: none;
                    }
                    
                    .we-card.visible {
                        display: block;
                    }
                    
                    .we-card-header {
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        margin-bottom: 12px;
                    }
                    
                    .we-company-logo {
                        width: 40px;
                        height: 40px;
                        background: #00704a;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-weight: bold;
                        font-size: 18px;
                    }
                    
                    .we-company-name {
                        font-size: 16px;
                        font-weight: 600;
                        color: #333;
                    }
                    
                    .we-role-group {
                        margin-bottom: 12px;
                    }
                    
                    .we-label {
                        font-size: 13px;
                        color: #666;
                        margin-bottom: 6px;
                    }
                    
                    .we-select {
                        width: 100%;
                        padding: 10px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        font-size: 14px;
                        outline: none;
                    }
                    
                    .we-date-group {
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }
                    
                    .we-date-input {
                        flex: 1;
                        padding: 10px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        font-size: 14px;
                        outline: none;
                    }
                    
                    .we-date-separator {
                        color: #999;
                        font-weight: bold;
                    }
                    
                    .we-confirm-btn {
                        width: 40px;
                        height: 40px;
                        background: #667eea;
                        color: white;
                        border: none;
                        border-radius: 50%;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 16px auto 0;
                        font-size: 20px;
                        transition: all 0.2s ease;
                    }
                    
                    .we-confirm-btn:hover {
                        background: #5568d3;
                        transform: scale(1.1);
                    }
                    
                    .we-confirm-btn:disabled {
                        background: #ccc;
                        cursor: not-allowed;
                    }
                </style>
                
                <div class="we-header">
                    <div class="we-add-icon">+</div>
                    <span>Most Recent</span>
                </div>
                
                <div class="we-input-group">
                    <input 
                        type="text" 
                        class="we-input" 
                        id="we-company-input"
                        placeholder="Company name..."
                    />
                    <svg class="we-voice-icon" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clip-rule="evenodd"/>
                    </svg>
                </div>
                
                <div class="we-card" id="we-details-card">
                    <div class="we-card-header">
                        <div class="we-company-logo" id="we-company-logo">S</div>
                        <div class="we-company-name" id="we-company-display">Starbucks</div>
                    </div>
                    
                    <div class="we-role-group">
                        <div class="we-label">Your role:</div>
                        <select class="we-select" id="we-role-select">
                            <option value="">Select role...</option>
                            ${this.jobRoles.map(role => `<option value="${role}">${role}</option>`).join('')}
                        </select>
                    </div>
                    
                    <div class="we-role-group">
                        <div class="we-label">Dates (start - end):</div>
                        <div class="we-date-group">
                            <input type="date" class="we-date-input" id="we-start-date" />
                            <span class="we-date-separator">-</span>
                            <input type="date" class="we-date-input" id="we-end-date" />
                        </div>
                    </div>
                </div>
                
                <button class="we-confirm-btn" id="we-confirm-btn" disabled>✓</button>
            `;
            
            return container;
        },
        
        attachEventListeners() {
            const companyInput = document.getElementById('we-company-input');
            const roleSelect = document.getElementById('we-role-select');
            const startDate = document.getElementById('we-start-date');
            const endDate = document.getElementById('we-end-date');
            const confirmBtn = document.getElementById('we-confirm-btn');
            const detailsCard = document.getElementById('we-details-card');
            const companyDisplay = document.getElementById('we-company-display');
            const companyLogo = document.getElementById('we-company-logo');
            
            // Show card when company name is entered
            companyInput.addEventListener('input', (e) => {
                const value = e.target.value.trim();
                this.currentData.company = value;
                
                if (value) {
                    detailsCard.classList.add('visible');
                    companyDisplay.textContent = value;
                    companyLogo.textContent = value.charAt(0).toUpperCase();
                    this.validateForm();
                } else {
                    detailsCard.classList.remove('visible');
                }
            });
            
            roleSelect.addEventListener('change', (e) => {
                this.currentData.role = e.target.value;
                this.validateForm();
            });
            
            startDate.addEventListener('change', (e) => {
                this.currentData.startDate = e.target.value;
                this.validateForm();
            });
            
            endDate.addEventListener('change', (e) => {
                this.currentData.endDate = e.target.value;
                this.validateForm();
            });
            
            confirmBtn.addEventListener('click', () => {
                this.submitWorkExperience();
            });
        },
        
        validateForm() {
            const confirmBtn = document.getElementById('we-confirm-btn');
            const isValid = this.currentData.company && 
                        this.currentData.role && 
                        this.currentData.startDate && 
                        this.currentData.endDate;
            
            confirmBtn.disabled = !isValid;
        },
        
        submitWorkExperience() {
            // Send work experience data to backend
            const data = {
                company: this.currentData.company,
                role: this.currentData.role,
                start_date: this.currentData.startDate,
                end_date: this.currentData.endDate
            };

            // Hide the UI FIRST
            this.hide();
            
            // Send via WebSocket
            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'work_experience_data',
                    data: data
                }));
            }
            
            // Show confirmation message
            window.CleoChatbot.addMessage(
                `My experience: ${data.role} at ${data.company} (${data.start_date} to ${data.end_date})`,
                false,
                'body'
            );
            
            // Re-enable input for next question
            window.CleoChatbot.enableInput();
        },
        
        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();

            // Scroll to show Work UI
            messagesDiv.scrollTo({
                top: messagesDiv.scrollHeight,
                behavior: 'smooth'
            });
            
            // Disable normal input
            window.CleoChatbot.disableInput();
        },
        
        hide() {
            const ui = document.getElementById('work-experience-ui');
            if (ui) {
                ui.style.display = 'none';  // Hide immediately
                setTimeout(() => {
                    ui.remove();  // Remove from DOM after brief delay
                }, 100);
            }
            
            // Reset data
            this.currentData = {
                company: '',
                role: '',
                startDate: '',
                endDate: ''
            };
        }
    };
    
    /**
     * Education Level Checkbox UI Component
     */

    const EducationUI = {
        
        educationOptions: [
            'Less than high school',
            'High school or GED',
            'Some college',
            'College degree',
            'Trade or certificate',
            'Prefer not to say'
        ],
        
        selectedOption: null,
        
        render() {
            const container = document.createElement('div');
            container.id = 'education-ui';
            container.className = 'education-container';
            
            container.innerHTML = `
                <style>
                    .education-container {
                        background: #f0f0f5;
                        border-radius: 16px;
                        padding: 20px;
                        margin: 16px 0;
                        animation: slideDown 0.3s ease-out;
                    }
                    
                    @keyframes slideDown {
                        from { opacity: 0; transform: translateY(-20px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    
                    .edu-option {
                        background: white;
                        border-radius: 12px;
                        padding: 14px 16px;
                        margin-bottom: 10px;
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
                        height: 20px;
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
                        font-size: 14px;
                        font-weight: bold;
                        display: none;
                    }
                    
                    .edu-option.selected .edu-checkbox-icon {
                        display: block;
                    }
                    
                    .edu-label {
                        flex: 1;
                        font-size: 15px;
                        color: #333;
                    }
                    
                    .edu-confirm-btn {
                        width: 40px;
                        height: 40px;
                        background: #667eea;
                        color: white;
                        border: none;
                        border-radius: 50%;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 16px auto 0;
                        font-size: 20px;
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
                    ${this.educationOptions.map((option, index) => `
                        <div class="edu-option" data-value="${option}">
                            <div class="edu-checkbox">
                                <span class="edu-checkbox-icon">✓</span>
                            </div>
                            <div class="edu-label">${option}</div>
                        </div>
                    `).join('')}
                </div>
                
                <button class="edu-confirm-btn" id="edu-confirm-btn" disabled>✓</button>
            `;
            
            return container;
        },
        
        attachEventListeners() {
            // Store reference to self to avoid 'this' context issues
            const self = this;
            
            const optionsList = document.getElementById('edu-options-list');
            const confirmBtn = document.getElementById('edu-confirm-btn');
            
            if (!optionsList || !confirmBtn) {
                console.error('[EducationUI] Elements not found!');
                return;
            }
            
            // Use event delegation
            optionsList.addEventListener('click', function(e) {
                const option = e.target.closest('.edu-option');
                if (!option) return;
                
                // Get value from data attribute
                const value = option.getAttribute('data-value');
                
                console.log('[EducationUI] Option clicked:', value);
                
                // Unselect all
                const allOptions = optionsList.querySelectorAll('.edu-option');
                allOptions.forEach(opt => opt.classList.remove('selected'));
                
                // Select clicked option
                option.classList.add('selected');
                
                // Store in self to maintain reference
                self.selectedOption = value;
                
                console.log('[EducationUI] Selected option stored:', self.selectedOption);
                
                // Enable confirm button
                confirmBtn.disabled = false;
            });
            
            confirmBtn.addEventListener('click', function() {
                console.log('[EducationUI] Confirm button clicked');
                console.log('[EducationUI] Current selectedOption:', self.selectedOption);
                self.submitEducation();
            });
        },
        
        submitEducation() {
            console.log('[EducationUI] submitEducation called');
            console.log('[EducationUI] this.selectedOption:', this.selectedOption);
            
            if (!this.selectedOption) {
                console.error('[EducationUI] No education selected!');
                return;
            }
            
            const selectedValue = this.selectedOption;
            console.log('[EducationUI] Submitting:', selectedValue);
            
            // Hide UI first
            this.hide();
            
            // Send to backend
            if (window.CleoChatbot && window.CleoChatbot.ws && window.CleoChatbot.ws.readyState === WebSocket.OPEN) {
                // Show user's selection
                window.CleoChatbot.addMessage(selectedValue, false, 'body');
                
                // Create message object and log it
                const message = {
                    type: 'user_message',
                    content: selectedValue
                };
                
                console.log('[EducationUI] Sending message:', JSON.stringify(message));
                
                // Send via WebSocket
                window.CleoChatbot.ws.send(JSON.stringify(message));
                
                console.log('[EducationUI] Message sent to backend');
            } else {
                console.error('[EducationUI] WebSocket not ready!');
                console.error('[EducationUI] WebSocket state:', window.CleoChatbot?.ws?.readyState);
                window.CleoChatbot.enableInput();
            }
        },
        
        show() {
            console.log('[EducationUI] Showing UI');
            
            const messagesDiv = document.getElementById('chatbot-messages');
            if (!messagesDiv) {
                console.error('[EducationUI] Messages div not found!');
                return;
            }
            
            const ui = this.render();
            messagesDiv.appendChild(ui);
            
            // Reset selected option before showing
            this.selectedOption = null;
            
            this.attachEventListeners();
            
            // Scroll to show Education UI
            messagesDiv.scrollTo({
                top: messagesDiv.scrollHeight,
                behavior: 'smooth'
            });
            
            // Disable normal input
            if (window.CleoChatbot) {
                window.CleoChatbot.disableInput();
            }
        },
        
        hide() {
            console.log('[EducationUI] Hiding UI');
            
            const ui = document.getElementById('education-ui');
            if (ui) {
                ui.style.display = 'none';
                setTimeout(() => {
                    ui.remove();
                }, 100);
            }
            
            // Reset selection
            this.selectedOption = null;
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