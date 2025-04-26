import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios'; // Import axios for API calls
import ReactMarkdown from 'react-markdown'; // Import ReactMarkdown
import stylesModule from './ChatInterface.module.css'; // Import CSS Module

// Accept props, specifically backendUrl and authToken
function ChatInterface({ backendUrl, authToken }) {
  const [messages, setMessages] = useState([
    { id: Date.now(), sender: 'agent', text: 'Hello! How can I help you with your Google Drive files today?' },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false); // State for loading indicator
  const [confirmationPendingMsgId, setConfirmationPendingMsgId] = useState(null); // Track which message needs confirmation
  const messagesEndRef = useRef(null); // Ref for scrolling to bottom

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const sendMessage = async (text, confirmation = null) => {
    // Prevent sending empty messages unless it's a confirmation response
    const messageText = text.trim();
    if (!messageText && confirmation === null) return;

    // Add user message to state immediately
    // Only add user message if it's not just a confirmation click
    if (messageText) {
      setMessages((prev) => [...prev, { id: Date.now(), sender: 'user', text: messageText }]);
    }
    setInputValue(''); // Clear input field
    setIsLoading(true); // Show loading indicator
    setConfirmationPendingMsgId(null); // Clear pending confirmation when sending new message or confirmation

    try {
      // Construct payload, including confirmation if provided
      const payload = { message: messageText };
      if (confirmation !== null) {
        payload.confirmation = confirmation;
      }

      const response = await axios.post(`${backendUrl}/api/ask`, payload, {
        headers: {
          Authorization: `Bearer ${authToken}`, // Include auth token
        },
      });

      const agentMessage = { 
        id: Date.now(), // Assign unique ID
        sender: 'agent', 
        text: response.data.message || "Sorry, I couldn't process that.",
        needsConfirmation: response.data.needsConfirmation || false // Store confirmation flag
      };
      setMessages((prev) => [...prev, agentMessage]);

      // If this message needs confirmation, store its ID
      if (agentMessage.needsConfirmation) {
        setConfirmationPendingMsgId(agentMessage.id);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      const errorText = error.response?.data?.detail || 'An error occurred while connecting to the backend.';
      setMessages((prev) => [...prev, { id: Date.now(), sender: 'agent', text: `Error: ${errorText}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault(); // Prevent newline on Enter
      sendMessage(inputValue);
    }
  };

  return (
    <div className={stylesModule.chatContainer}>
      <div className={stylesModule.messagesContainer}>
        {messages.map((msg, index) => (
          <div
            key={index}
            // Combine base message class with specific user/agent class
            className={`${stylesModule.message} ${msg.sender === 'user' ? stylesModule.userMessage : stylesModule.agentMessage}`}
          >
            {/* Render agent messages as Markdown, user messages as plain text */}
            {msg.sender === 'agent' ? (
              <ReactMarkdown>{msg.text}</ReactMarkdown>
            ) : (
              msg.text
            )}
            {/* Check if this message is the one pending confirmation */} 
            {msg.id === confirmationPendingMsgId ? (
              <div className={stylesModule.confirmationButtons}>
                <button 
                  onClick={() => sendMessage('', true)} // Send confirmation=true
                  className={stylesModule.confirmButtonYes}
                >
                  Yes, Create
                </button>
                <button 
                  onClick={() => sendMessage('', false)} // Send confirmation=false
                  className={stylesModule.confirmButtonNo}
                >
                  No, Cancel
                </button>
              </div>
            ) : null}

          </div>
        ))}
        <div ref={messagesEndRef} /> {/* Anchor for scrolling */}
      </div>
      <div className={stylesModule.inputContainer}>
        <input
          type="text"
          className={stylesModule.inputField} // Use CSS Module class
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your files..."
          disabled={isLoading}
        />
        <button
          // Combine base class with disabled class conditionally
          className={`${stylesModule.sendButton} ${isLoading ? stylesModule.sendButtonDisabled : ''}`}
          onClick={() => sendMessage(inputValue)}
          disabled={isLoading}
        >
          {isLoading ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default ChatInterface;
