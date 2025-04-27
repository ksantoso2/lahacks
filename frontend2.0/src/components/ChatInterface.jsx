import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios'; // Import axios for API calls
import ReactMarkdown from 'react-markdown'; // Import ReactMarkdown
import stylesModule from './ChatInterface.module.css'; // Import CSS Module

// Accept props, specifically backendUrl
function ChatInterface({ backendUrl }) {
  const [messages, setMessages] = useState([
    { id: Date.now(), sender: 'agent', text: 'Hello! How can I help you with your Google Drive files today?' },
  ]);
  
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false); // State for loading indicator
  const [confirmationPendingMsgId, setConfirmationPendingMsgId] = useState(null); // Track which message needs confirmation
  const [confirmationType, setConfirmationType] = useState(null); // 'preview_gen' or 'doc_create'
  const [allowRegenerate, setAllowRegenerate] = useState(false); // Track if regenerate is allowed
  const messagesEndRef = useRef(null); // Ref for scrolling to bottom

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Add useEffect to load initial messages or context if needed
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const response = await axios.get(`${backendUrl}/api/initial-context`, { withCredentials: true });
        // Process initial data
      } catch (error) {
        console.error("Error fetching initial data:", error);
      }
    };
    fetchInitialData();
  }, [backendUrl]);

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const sendMessage = async (payload) => {
    const messageToSend = payload?.message ?? inputValue; // Use payload message if provided, else use input
    const confirmationToSend = payload?.confirmation; // Use payload confirmation if provided
    const regenerateToSend = payload?.regenerate;     // Use payload regenerate if provided

    // Don't send empty messages unless it's a confirmation/action click
    if (!messageToSend && confirmationToSend === undefined && regenerateToSend === undefined) return;

    setIsLoading(true); // Show loading indicator
    setConfirmationPendingMsgId(null); // Clear pending confirmation when sending new message or confirmation
    setConfirmationType(null);
    setAllowRegenerate(false);

    try {
      // Construct payload, including confirmation or regenerate flag
      const response = await axios.post(`${backendUrl}/api/ask`, {
        message: messageToSend, 
        confirmation: confirmationToSend, // Send the confirmation value
        regenerate: regenerateToSend,     // Send regenerate flag
      }, {
        withCredentials: true, // Send cookies with the request
      });

      const agentMessage = { 
        id: Date.now(), // Assign unique ID
        sender: 'agent', 
        text: response.data.message || "Sorry, I couldn't process that.",
        needsConfirmation: response.data.needsConfirmation || false, // Store confirmation flag
        confirmationType: response.data.confirmationType || null, // Store confirmation type
        allowRegenerate: response.data.allowRegenerate || false // Store regenerate flag
      };
      setMessages((prev) => [...prev, agentMessage]);

      // If this message needs confirmation, store its ID and type
      if (agentMessage.needsConfirmation) {
        setConfirmationPendingMsgId(agentMessage.id);
        setConfirmationType(agentMessage.confirmationType);
        setAllowRegenerate(agentMessage.allowRegenerate);
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
      sendMessage({ message: inputValue });
    }
  };

  const handleConfirmation = async (choice) => {
    if (!confirmationPendingMsgId) return;

    const payload = {
      confirmation: choice,
    };

    // Send the confirmation choice
    await sendMessage(payload);

    // Clear confirmation state after sending
    setConfirmationPendingMsgId(null);
    setConfirmationType(null);
    setAllowRegenerate(false);
  };

  return (
    <div className={stylesModule.chatContainer}>
      <div className={stylesModule.chatHistory}>
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
            {/* Render buttons only if this message ID is the one pending confirmation */} 
            {msg.id === confirmationPendingMsgId && (
              <div className={stylesModule.confirmationButtons}>
                {/* Buttons for Preview Generation Confirmation */} 
                {confirmationType === 'preview_gen' && (
                  <>
                    <button onClick={() => handleConfirmation(true)} className={stylesModule.confirmButtonYes}>Yes, Generate Preview</button>
                    <button onClick={() => handleConfirmation(false)} className={stylesModule.confirmButtonNo}>No, Cancel</button>
                  </>
                )}
                
                {/* Buttons for Document Creation Confirmation */} 
                {confirmationType === 'doc_create' && (
                  <>
                    <button onClick={() => handleConfirmation(true)} className={stylesModule.confirmButtonYes}>Yes, Create</button>
                    <button onClick={() => handleConfirmation(false)} className={stylesModule.confirmButtonNo}>No, Cancel</button>
                    {/* Show Regenerate button only if allowed */} 
                    {allowRegenerate && (
                      <button onClick={() => sendMessage({ regenerate: true })} className={stylesModule.confirmButtonRegen}>Regenerate Preview</button>
                    )}
                  </>
                )}
                
                {/* Buttons for Move Document Confirmation */} 
                {confirmationType === 'moveDoc' && (
                  <>
                    <button onClick={() => handleConfirmation(true)} className={stylesModule.confirmButtonYes}>Yes</button>
                    <button onClick={() => handleConfirmation(false)} className={stylesModule.confirmButtonNo}>No</button>
                  </>
                )}
              </div>
            )}
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
          onClick={() => sendMessage({ message: inputValue })}
          disabled={isLoading}
        >
          {isLoading ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default ChatInterface;
