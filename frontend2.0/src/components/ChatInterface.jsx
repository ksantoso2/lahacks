import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios'; // Import axios for API calls
import stylesModule from './ChatInterface.module.css'; // Import CSS Module

// Accept props, specifically backendUrl and authToken
function ChatInterface({ backendUrl, authToken }) {
  const [messages, setMessages] = useState([
    { sender: 'agent', text: 'Hello! How can I help you with your Google Drive files today?' },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const handleSendMessage = async () => {
    const userMessage = inputValue.trim();
    if (!userMessage || isLoading) return;
  
    setMessages((prevMessages) => [
      ...prevMessages,
      { sender: 'user', text: userMessage },
    ]);
    setInputValue('');
    setIsLoading(true);
  
    try {
      const chatApiUrl = `${backendUrl}/api/ask`;
  
      // Add confirmation logic here
      const lowerMessage = userMessage.toLowerCase();
      const confirmationYes = ['yes', 'y', 'sure', 'ok', 'okay'];
      const confirmationNo = ['no', 'n', 'cancel'];
  
      const confirmation = confirmationYes.includes(lowerMessage)
        ? true
        : confirmationNo.includes(lowerMessage)
        ? false
        : null;
  
      console.log('Sending to backend:', { message: userMessage, confirmation });
      
      const response = await axios.post(
        chatApiUrl,
        {
          message: userMessage,    // Always send message
          confirmation: confirmation,  // Send confirmation if detected
        },
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        }
      );

      if (response.data && response.data.message) {
        setMessages((prevMessages) => [
          ...prevMessages,
          { sender: 'agent', text: response.data.message },
        ]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prevMessages) => [
        ...prevMessages,
        {
          sender: 'agent',
          text: `Sorry, I encountered an error. ${error.response?.data?.detail || error.message}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };      

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault(); // Prevent newline on Enter
      handleSendMessage();
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
            {msg.text}
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
          onClick={handleSendMessage}
          disabled={isLoading}
        >
          {isLoading ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default ChatInterface;
