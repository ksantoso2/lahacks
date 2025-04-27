import React, { useState, useEffect } from 'react';
import axios from 'axios'; 
import ChatInterface from './components/ChatInterface';
import './App.css';

function App() {
  const [authToken, setAuthToken] = useState(null);
  // Keep track if we're still checking the URL hash
  const [isLoadingAuth, setIsLoadingAuth] = useState(true); // Check initial auth status
  const [authError, setAuthError] = useState(null); // General auth error state
  const [isLoggedIn, setIsLoggedIn] = useState(false); // Track login status

  // Read backend URL from environment variable (Vite exposes VITE_ prefixed vars)
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'; // Fallback for safety

  useEffect(() => {
    // Check session status on initial load
    const checkSession = async () => {
      try {
        // Make a simple request to an authenticated endpoint (e.g., userinfo)
        // If it succeeds, the session is valid.
        const response = await axios.get(`${backendUrl}/api/userinfo`, {
          withCredentials: true, // Crucial for sending session cookies
        });
        console.log("✅ Session valid:", response.data);
        setIsLoggedIn(true);
      } catch (error) {
        // If it fails (e.g., 401), the session is invalid or expired
        console.log("❌ Session invalid or expired:", error.response?.data?.detail || error.message);
        setIsLoggedIn(false);
      }
      setIsLoadingAuth(false);
    };

    const hash = window.location.hash.substring(1); // Remove leading '#'
    const params = new URLSearchParams(hash);
  
    const loginSuccess = params.get('login_success');
    const loginError = params.get('error');
    const errorDescription = params.get('error_description');

    if (loginSuccess === 'true') {
      console.log("✅ Login successful (session established).");
      setIsLoggedIn(true); 
      setIsLoadingAuth(false);
      // Clear hash only on success
      window.history.replaceState(null, "", window.location.pathname);
    } else if (loginError) {
      console.error(`❌ Login failed: ${loginError} - ${errorDescription}`);
      setAuthError(`Login failed: ${errorDescription || loginError}`);
      setIsLoggedIn(false);
      setIsLoadingAuth(false);
      // Clear hash even on error
      window.history.replaceState(null, "", window.location.pathname);
    } else {
      // No login redirect params, check existing session
      checkSession();
    }
  }, []);
  

  // Function to initiate the local login flow
  const handleLocalLogin = () => {
    window.location.href = `${backendUrl}/auth/local-login`; // Add /auth prefix
  };

  // Logout function (optional for local dev - simply clears the token)
  const handleLocalLogout = () => {
    // TODO: Implement backend logout endpoint to clear session
    setIsLoggedIn(false);
    // request.session.destroy() // something like this on backend
    // Optionally redirect or clear state further
  };

  // --- Core Send Message Logic --- 
  const sendMessageLogic = async (message, confirmation = null, regenerate = false, skipPreview = false) => {
    console.log(`Sending message: confirm=${confirmation}, regen=${regenerate}, skip=${skipPreview}`);
    if (isLoading || !message.trim() && !confirmation && !regenerate && !skipPreview) return; // Allow sending flags without message text

    setIsLoading(true);
    // Optimistically add user message ONLY if it's an actual message, not just a button click
    if (message && !confirmation && !regenerate && !skipPreview) {
        const newUserMessage = { role: 'user', parts: [message] };
        setMessages(prev => [...prev, newUserMessage]);
    }
    // Clear input immediately for user messages
    // setInput(''); // Assuming setInput is managed by ChatInterface

    // Clear confirmation buttons optimistically if a confirmation/regenerate/skip action is taken
    if (confirmation !== null || regenerate || skipPreview) {
      setActionRequired(null);
      setPreviewDetails(null);
    }

    try {
      const response = await axios.post(`${backendUrl}/api/ask`, 
        { 
            message: message, 
            confirmation: confirmation,
            regenerate: regenerate,
            skip_preview: skipPreview
        },
        {
            headers: {
                'Content-Type': 'application/json',
            },
            withCredentials: true // Add this line to send cookies
        }
      );

      const data = response.data;
      console.log("✅ Backend Response:", data);
      const newModelMessage = { role: 'model', parts: [data.message] };
      setMessages(prev => [...prev, newModelMessage]);

      // Handle action required from backend
      if (data.action_required === 'confirm_create') {
        setActionRequired('confirm_create');
        setPreviewDetails({ file_name: data.file_name, preview: data.preview });
      } else {
        // Ensure buttons are cleared if backend confirms action is done
        setActionRequired(null);
        setPreviewDetails(null);
      }

    } catch (error) {
        console.error("❌ Error sending message:", error.response?.data?.detail || error.message);
        const errorMessageText = `Error: ${error.response?.data?.detail || error.message}`;
        const errorMessage = { role: 'model', parts: [errorMessageText] };
        setMessages(prev => [...prev, errorMessage]);
        // Clear any pending actions on error too?
        setActionRequired(null);
        setPreviewDetails(null);
    } finally {
        setIsLoading(false);
    }
  };

  // --- Handler for Skip Button Click --- 
  const handleSkipPreview = () => {
    console.log("Triggering skip preview action...");
    // Use the core logic, passing the skip flag
    // Pass null message because this is just a button action
    sendMessageLogic(null, null, false, true); 
  };

  if (isLoadingAuth) {
    return <div>Checking authentication...</div>;
  }

  // Render based on login status
  return (
    <div className="App">
      <h1>Google Drive AI Agent (Local Dev)</h1>
      
      {isLoggedIn ? (
        <>
         {/* Optional: Display user info if decoded */} 
         <div style={{ marginBottom: '10px', textAlign: 'right', paddingRight: '20px' }}>
           {/* Placeholder - decode token to show email */} 
           <span>Logged In</span>
           <button onClick={handleLocalLogout} style={{ marginLeft: '10px' }}>Logout (Local)</button>
         </div>
         <ChatInterface 
           backendUrl={backendUrl} 
           handleSkipPreview={handleSkipPreview} // Pass the function defined above
           sendMessage={sendMessageLogic} // Pass the function defined above
         /> {/* Remove authToken prop */}
        </>
      ) : (
        <div style={{ textAlign: 'center', marginTop: '50px' }}>
          {authError && <p style={{ color: 'red' }}>{authError}</p>}
          <p>Click to login with Google for local development.</p>
          {/* Use a standard button or the Google button style */}
          <button onClick={handleLocalLogin} className="btn-google" style={{ padding: '10px 20px', fontSize: '16px'}}> 
            Login for Local Dev
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
