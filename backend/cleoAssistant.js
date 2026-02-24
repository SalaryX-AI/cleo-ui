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
                    // this.showTypingIndicator();
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
                // Show address autocomplete UI
                else if (data.show_address_ui) 
                {
                    AddressUI.show();
                }
                // Show GPS verification button
                else if (data.show_gps_ui) 
                {
                    LocationVerificationUI.show();
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

    // ─────────────────────────────────────────────────────────────────────────
    //  Work Experience UI Component - Multiple Jobs Support
    // ─────────────────────────────────────────────────────────────────────────
    const WorkExperienceUI = {
        
        jobRoles: [
            'Assistant Manager', 'Assistant Store Manager', 'Barista', 'Cashier',
            'Coffee Specialist', 'Cook', 'Crew Member', 'Customer Support',
            'Dining Room', 'Dishwasher', 'Drive Thru', 'Grill Cook',
            'Guest Experience', 'Host', 'Kitchen Staff', 'Maintenance',
            'Overnight Crew', 'Prep Cook', 'Prep Team', 'Shift Coordinator',
            'Shift Lead', 'Shift Leader', 'Shift Manager', 'Shift Supervisor',
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
                        padding: 20px;
                        margin: 16px 0;
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
                        border-radius: 12px;
                        padding: 12px;
                        margin-bottom: 10px;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        border: 1px solid #e0e0e0;
                    }
                    
                    .work-exp-logo {
                        width: 40px;
                        height: 40px;
                        background: #667eea;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-weight: bold;
                        font-size: 18px;
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
                        border-radius: 12px;
                        padding: 16px;
                        margin-bottom: 16px;
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
                        font-size: 13px;
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
                        padding: 10px 12px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        font-size: 14px;
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
                        height: 36px;
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
                        gap: 12px;
                    }
                    
                    .work-exp-buttons {
                        display: flex;
                        gap: 10px;
                        margin-top: 16px;
                    }
                    
                    .work-exp-btn {
                        flex: 1;
                        padding: 12px;
                        border: none;
                        border-radius: 10px;
                        font-size: 14px;
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
                heading.textContent = this.experiences.length === 0 ? 'Most Recent' : 'Previous Job Experience';
            }
        },
        
        hideForm() {
            const form = document.getElementById('work-exp-form');
            if (form) {
                form.style.display = 'none';
            }
        },

        editExperience(index) {
            // Get the experience to edit
            const exp = this.experiences[index];
            
            // Remove from array FIRST (will be re-added when user clicks "Add Job")
            this.experiences.splice(index, 1);
            
            // Re-render the list SECOND (updates the cards)
            this.renderExperienceList();
            
            // Hide action buttons THIRD
            this.hideActionButtons();
            
            // Populate the form FOURTH
            document.getElementById('work-exp-company').value = exp.company;
            document.getElementById('work-exp-role').value = exp.role;
            document.getElementById('work-exp-start').value = exp.startDate;
            document.getElementById('work-exp-end').value = exp.endDate;
            
            // Update the heading FIFTH
            const heading = document.getElementById('work-exp-form-heading');
            if (heading) {
                heading.textContent = 'Edit Job Experience';
                heading.style.color = '#667eea';
            }
            
            // Show the form LAST (this ensures it's visible)
            this.showForm();
        },
        
        showActionButtons() {
            const actions = document.getElementById('work-exp-actions');
            if (actions) {
                actions.style.display = 'flex';
            }
        },
        
        submitAllExperiences() {
            if (this.experiences.length === 0) {
                console.error('[WorkExperienceUI] No experiences to submit');
                return;
            }
            
            console.log('[WorkExperienceUI] Submitting all experiences:', this.experiences);
            
            // Show confirmation message
            const summary = this.experiences.map(exp => 
                `${exp.role} at ${exp.company} (${exp.startDate} to ${exp.endDate})`
            ).join(', ');
            
            window.CleoChatbot.addMessage(
                `My experience: ${summary}`,
                false,
                'body'
            );
            
            // Send all experiences via WebSocket
            if (window.CleoChatbot && window.CleoChatbot.ws) {
                window.CleoChatbot.ws.send(JSON.stringify({
                    type: 'work_experience_data',
                    data: this.experiences  // Send array of all experiences
                }));
            }

            // Hide UI
            this.hide();
        },
        
        show() {
            const messagesDiv = document.getElementById('chatbot-messages');
            const ui = this.render();
            messagesDiv.appendChild(ui);
            this.attachEventListeners();
            
            // Scroll to show UI
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
                        padding: 20px;
                        margin: 16px 0;
                        animation: slideDown 0.3s ease-out;
                    }

                    .address-input-wrapper {
                        position: relative;
                    }

                    .address-input {
                        width: 100%;
                        padding: 12px 16px;
                        border: 2px solid #ddd;
                        border-radius: 12px;
                        font-size: 15px;
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
                        max-height: 220px;
                        overflow-y: auto;
                    }

                    .address-suggestion-item {
                        padding: 12px 16px;
                        cursor: pointer;
                        font-size: 14px;
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
                        font-size: 16px;
                        flex-shrink: 0;
                    }

                    .address-confirm-btn {
                        width: 100%;
                        margin-top: 14px;
                        padding: 13px;
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

            messagesDiv.scrollTo({ top: messagesDiv.scrollHeight, behavior: 'smooth' });
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