import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios'; // Import axios for API calls

// Basic styling - can be expanded or moved to CSS file
const styles = {
  chatContainer: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh', // Use viewport height to fill sidebar
    boxSizing: 'border-box',
    padding: '10px',
    fontFamily: 'Arial, sans-serif',
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
  },
  userMessage: {
    backgroundColor: '#d1eaff',
    alignSelf: 'flex-end',
    marginLeft: 'auto',
    textAlign: 'right',
  },
  agentMessage: {
    backgroundColor: '#e0e0e0',
    alignSelf: 'flex-start',
    marginRight: 'auto',
  },
  inputContainer: {
    display: 'flex',
  },
  inputField: {
    flexGrow: 1,
    padding: '8px',
    border: '1px solid #ccc',
    borderRadius: '4px 0 0 4px',
    outline: 'none',
  },
  sendButton: {
    padding: '8px 15px',
    border: '1px solid #007bff',
    backgroundColor: '#007bff',
    color: 'white',
    borderRadius: '0 4px 4px 0',
    cursor: 'pointer',
    outline: 'none',
  },
  sendButtonDisabled: {
    backgroundColor: '#a0cfff',
    cursor: 'not-allowed',
    border: '1px solid #a0cfff',
  },
};

function ChatInterface() {
  const [messages, setMessages] = useState([
    { sender: 'agent', text: 'Hello! How can I help you with your Google Drive files today?' },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [scriptToken, setScriptToken] = useState(null);
  const messagesEndRef = useRef(null);

  // Extract scriptToken from URL on component mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('scriptToken');
    if (token) {
      setScriptToken(decodeURIComponent(token));
      console.log("Script Token Found (truncated):", token.substring(0, 10) + '...');
    }
  }, []);

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

    // Add user message to chat
    setMessages((prevMessages) => [
      ...prevMessages,
      { sender: 'user', text: userMessage },
    ]);
    setInputValue('');
    setIsLoading(true);

    try {
      // --- API Call to Backend ---
      // Replace with your actual backend URL
      const backendUrl = 'http://localhost:8000/api/chat'; 
      
      const response = await axios.post(backendUrl, {
        message: userMessage,
        scriptToken: scriptToken, // Send token if available
      });

      // Add agent response to chat
      if (response.data && response.data.response) {
        setMessages((prevMessages) => [
          ...prevMessages,
          { sender: 'agent', text: response.data.response },
        ]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message to chat
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
          style={styles.inputField}
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your files..."
          disabled={isLoading}
        />
        <button
          style={{
            ...styles.sendButton,
            ...(isLoading ? styles.sendButtonDisabled : {}),
          }}
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
