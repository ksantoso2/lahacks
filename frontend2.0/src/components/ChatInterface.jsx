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
  const [allowSkip, setAllowSkip] = useState(false); // Track if skip preview is allowed
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
    const messageToSend = payload?.message ?? inputValue;
    const confirmationToSend = payload?.confirmation;
    const regenerateToSend = payload?.regenerate;
    const skipToSend = payload?.skip_preview;

    if (!messageToSend && confirmationToSend === undefined && regenerateToSend === undefined && skipToSend === undefined) return;

    // --- Add USER message FIRST if it's not a button click ---
    if (confirmationToSend === undefined && regenerateToSend === undefined && skipToSend === undefined) {
      const newUserMessage = { id: Date.now(), sender: 'user', text: messageToSend };
      console.log("*** Adding user message ***");
      console.log("Messages BEFORE user add:", messages);
      console.log("User message object:", newUserMessage);
      setMessages(prev => [...prev, newUserMessage]); // Add user message immediately
      // Log might still be batched by React
      console.log("Messages AFTER user add (call scheduled):", messages);
      setInputValue(''); // Clear input immediately
      // Clear any previous confirmation state when user types new message
      setConfirmationPendingMsgId(null);
      setConfirmationType(null);
      setAllowRegenerate(false);
      setAllowSkip(false);
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${backendUrl}/api/ask`, {
        message: messageToSend, // Send original text even for buttons
        confirmation: confirmationToSend,
        regenerate: regenerateToSend,
        skip_preview: skipToSend,
      }, { withCredentials: true });

      const agentMessage = { // Construct agent message object
        id: response.data.messageId || `agent_${Date.now()}`,
        sender: 'agent',
        text: response.data.message || "Sorry, I couldn't process that.",
        needsConfirmation: response.data.needsConfirmation || false,
        confirmationType: response.data.confirmationType || null,
        allowRegenerate: response.data.allowRegenerate || false,
        allowSkip: response.data.allowSkip || false
      };
      
      // --- Add AGENT message ---
      setMessages((prev) => [...prev, agentMessage]); // Add agent message
      console.log("Added agent message:", agentMessage);

      // --- Update confirmation state based on agent response ---
      if (agentMessage.needsConfirmation) {
        console.log(`Setting confirmation pending for Msg ID: ${agentMessage.id}, Type: ${agentMessage.confirmationType}, Regen: ${agentMessage.allowRegenerate}, Skip: ${agentMessage.allowSkip}`);
        setConfirmationPendingMsgId(agentMessage.id);
        setConfirmationType(agentMessage.confirmationType);
        setAllowRegenerate(agentMessage.allowRegenerate);
        setAllowSkip(agentMessage.allowSkip);
      } else {
        // If the agent's response doesn't require confirmation, clear any previous pending state
        console.log("Clearing confirmation state as agent response does not need it.");
        setConfirmationPendingMsgId(null);
        setConfirmationType(null);
        setAllowRegenerate(false);
        setAllowSkip(false);
      }

    } catch (error) {
      console.error("Error sending message:", error);
      const errorMsg = { id: `agent_${Date.now()}`, sender: 'agent', text: "⚠️ Error connecting to the backend." };
      setMessages((prev) => [...prev, errorMsg]);
      // Clear confirmation state on error too
      setConfirmationPendingMsgId(null);
      setConfirmationType(null);
      setAllowRegenerate(false);
      setAllowSkip(false);
    } finally {
      setIsLoading(false);
    }
    // User message addition and input clearing moved BEFORE the try block
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault(); // Prevent newline on Enter
      sendMessage({ message: inputValue });
    }
  };

  const handleConfirmation = async (choice) => {
    if (!confirmationPendingMsgId) return;

    console.log(`Handling confirmation: ${choice}, Pending Msg ID before send: ${confirmationPendingMsgId}`);

    // Send the confirmation choice
    await sendMessage({ confirmation: choice });
  };

  // Function to handle regeneration request
  const handleRegenerate = async () => {
    await sendMessage({ regenerate: true });
  };

  // Function to handle skipping preview
  const handleSkipPreview = async () => {
    await sendMessage({ skip_preview: true });
  };

  return (
    <div className={stylesModule.chatContainer}>
      <div className={stylesModule.chatHistory}>
        {messages.map((msg, index) => {
          // --- Enhanced Render Logging --- 
          console.log(
            `Render Check: index=${index}, totalMsgs=${messages.length}, ` +
            `msgId=${msg.id}, needsConfirm=${msg.needsConfirmation}, ` +
            `confirmType=${msg.confirmationType}, allowRegen=${msg.allowRegenerate}, ` +
            `allowSkip=${msg.allowSkip}`
          );
          return (
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
              {/* Render buttons only if this message is the LAST message AND needs confirmation */}
              {index === messages.length - 1 && msg.needsConfirmation && (
                <div className={stylesModule.confirmationButtons}>
                  {/* Buttons for Preview Generation Confirmation */}
                  {msg.confirmationType === 'preview_gen' && (
                    <>
                      <button onClick={() => handleConfirmation(true)} className={stylesModule.confirmButtonYes}>Yes, Generate Preview</button>
                      <button onClick={() => handleConfirmation(false)} className={stylesModule.confirmButtonNo}>No, Cancel</button>
                    </>
                  )}
                  
                  {/* Buttons for Document Creation Confirmation */}
                  {msg.confirmationType === 'doc_create' && (
                    <>
                      <button onClick={() => handleConfirmation(true)} className={stylesModule.confirmButtonYes}>Yes, Create</button>
                      <button onClick={() => handleConfirmation(false)} className={stylesModule.confirmButtonNo}>No, Cancel</button>
                      {/* Show Regenerate button only if allowed */}
                      {msg.allowRegenerate && (
                        <button onClick={handleRegenerate} className={stylesModule.confirmButtonRegen}>Regenerate Preview</button>
                      )}
                      {/* Show Skip Preview button only if allowed */}
                      {msg.allowSkip && (
                        <button onClick={handleSkipPreview} className={stylesModule.confirmButtonSkip}>Skip Preview & Create</button>
                      )}
                    </>
                  )}
                  
                  {/* Buttons for Move Document Confirmation */}
                  {msg.confirmationType === 'moveDoc' && (
                    <>
                      <button onClick={() => handleConfirmation(true)} className={stylesModule.confirmButtonYes}>Yes</button>
                      <button onClick={() => handleConfirmation(false)} className={stylesModule.confirmButtonNo}>No</button>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
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
