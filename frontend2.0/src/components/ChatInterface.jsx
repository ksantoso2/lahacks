import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios'; // Import axios for API calls
import stylesModule from './ChatInterface.module.css'; // Import CSS Module

// Basic styling - can be expanded or moved to CSS file
const styles = {
  chatContainer: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh', // Use viewport height to fill sidebar
    boxSizing: 'border-box',
    padding: '10px',
    // Use a modern system font stack for better appearance
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"',
    fontSize: '14px',
  },
  messagesContainer: {
    flexGrow: 1,
    overflowY: 'auto',
    marginBottom: '10px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    padding: '8px',
    backgroundColor: '#f9f9f9',
  },
  message: {
    marginBottom: '8px',
    padding: '6px 10px',
    borderRadius: '15px',
    maxWidth: '80%',
    color: '#333', // Add default dark text color
    textAlign: 'left', // Ensure text inside bubble is left-aligned
  },
  userMessage: {
    backgroundColor: '#d1eaff',
    alignSelf: 'flex-end',
    marginLeft: 'auto',
    // Removed textAlign: 'right' - bubbles align right, text inside aligns left
  },
  agentMessage: {
    backgroundColor: '#e0e0e0',
    alignSelf: 'flex-start',
    marginRight: 'auto',
  },
  inputContainer: {
    display: 'flex',
    alignItems: 'center', // Align items vertically in the center
  },
};

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
    <div style={styles.chatContainer}>
      <div style={styles.messagesContainer}>
        {messages.map((msg, index) => (
          <div
            key={index}
            style={{
              ...styles.message,
              ...(msg.sender === 'user' ? styles.userMessage : styles.agentMessage),
            }}
          >
            {msg.text}
          </div>
        ))}
        <div ref={messagesEndRef} /> {/* Anchor for scrolling */}
      </div>
      <div style={styles.inputContainer}>
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
