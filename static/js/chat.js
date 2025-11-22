class ChatManager {
    constructor(conversationData) {
        this.conversationId = conversationData.id;
        this.getMessagesUrl = conversationData.getMessagesUrl;
        this.sendMessageUrl = conversationData.sendMessageUrl;
        this.initialMessagesCount = conversationData.initialMessagesCount;
        this.autoRefresh = true;

        this.initializeElements();
        this.initializeEventListeners();
        this.scrollToBottom();
        this.startAutoRefresh();
    }

    initializeElements() {
        this.messageInput = document.getElementById('messageInput');
        this.chatMessages = document.getElementById('chatMessages');
        this.sendButton = document.querySelector('.chat-input .btn');
    }

    initializeEventListeners() {
        // Enter key handling for message input
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });

        // Scroll detection
        if (this.chatMessages) {
            this.chatMessages.addEventListener('scroll', () => {
                this.checkScrollPosition();
            });
        }

        // Page visibility changes
        document.addEventListener('visibilitychange', () => {
            this.autoRefresh = !document.hidden;
            if (!document.hidden) {
                this.checkForNewMessages();
            }
        });
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 150) + 'px';
    }

    async sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content) return;

        const originalButtonText = this.sendButton.innerHTML;
        this.sendButton.disabled = true;
        this.sendButton.innerHTML = 'Sending...';

        try {
            const response = await fetch(this.sendMessageUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    conversation_id: this.conversationId,
                    content: content
                })
            });

            const data = await response.json();

            if (data.success) {
                this.messageInput.value = '';
                this.autoResizeTextarea();

                // Refresh messages after sending
                setTimeout(() => {
                    this.checkForNewMessages();
                }, 500);
            } else {
                throw new Error(data.error || 'Failed to send message');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            alert('Error sending message: ' + error.message);
        } finally {
            this.sendButton.disabled = false;
            this.sendButton.innerHTML = originalButtonText;
        }
    }

    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    checkScrollPosition() {
        // You can implement scroll position tracking here if needed
    }

    async checkForNewMessages() {
        if (!this.autoRefresh) return;

        try {
            const response = await fetch(this.getMessagesUrl);
            const messages = await response.json();

            if (messages.length !== this.initialMessagesCount) {
                // Reload the page to show new messages
                location.reload();
            }
        } catch (error) {
            console.error('Error checking messages:', error);
        }
    }

    startAutoRefresh() {
        // Check for new messages every 3 seconds
        setInterval(() => {
            this.checkForNewMessages();
        }, 3000);
    }
}

// Global functions
function sendMessage() {
    // This will be called by the onclick handler
    const chatManager = new ChatManager(window.conversationData);
    chatManager.sendMessage();
}

function initializeChat(conversationData) {
    // Store conversation data globally for sendMessage function
    window.conversationData = conversationData;

    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new ChatManager(conversationData);
        });
    } else {
        new ChatManager(conversationData);
    }
}

// Make functions available globally
window.sendMessage = sendMessage;
window.initializeChat = initializeChat;