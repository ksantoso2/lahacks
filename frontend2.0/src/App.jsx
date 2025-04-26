import React, { useState, useEffect } from 'react';
import axios from 'axios'; 
import ChatInterface from './components/ChatInterface';
import './App.css';

function App() {
  const [authToken, setAuthToken] = useState(null);
  // Keep track if we're still checking the URL hash
  const [isLoadingToken, setIsLoadingToken] = useState(true);
  const [authError, setAuthError] = useState(null); // General auth error state

  const backendUrl = 'http://localhost:8000'; // Your backend URL

  // Check URL fragment for token on component mount
  useEffect(() => {
    const hash = window.location.hash;
    let token = null;
    let error = null;

    if (hash.startsWith('#id_token=')) {
      token = hash.substring('#id_token='.length);
      console.log("ID Token found in URL fragment (first 10 chars):", token.substring(0, 10) + "...");
      
      // Optional: Decode token locally to show user info (requires jwt-decode library)
      // try {
      //   const decoded = jwtDecode(token);
      //   console.log("Decoded user info:", decoded);
      // } catch (e) { console.error("Failed to decode token", e); }

      // Clean the URL fragment
      window.location.hash = ''; 
      // Or use history API for cleaner removal without page jump:
      // if (history.pushState) {
      //   history.pushState("", document.title, window.location.pathname + window.location.search);
      // } else {
      //   window.location.hash = ''; // Fallback
      // }
      
      setAuthToken(token);
    } else if (hash.startsWith('#error=')) {
        // Handle potential errors passed in the fragment (less common)
        error = decodeURIComponent(hash.substring('#error='.length));
        console.error("Error received in URL fragment:", error);
        setAuthError(`Login failed: ${error}`);
        window.location.hash = ''; // Clear error hash
    }
    
    // Finished checking the hash
    setIsLoadingToken(false);

  }, []); // Run only once on mount

  // Function to initiate the local login flow
  const handleLocalLogin = () => {
    window.location.href = `${backendUrl}/local-login`; 
  };

  // Logout function (optional for local dev - simply clears the token)
  const handleLocalLogout = () => {
      setAuthToken(null);
      // Optionally redirect or clear state further
  };

  if (isLoadingToken) {
    return <div>Checking authentication...</div>;
  }

  // Render based on whether we have a token
  return (
    <div className="App">
      <h1>Google Drive AI Agent (Local Dev)</h1>
      
      {authToken ? (
        <>
         {/* Optional: Display user info if decoded */} 
         <div style={{ marginBottom: '10px', textAlign: 'right', paddingRight: '20px' }}>
           {/* Placeholder - decode token to show email */} 
           <span>Logged In (Token Acquired)</span>
           <button onClick={handleLocalLogout} style={{ marginLeft: '10px' }}>Logout (Local)</button>
         </div>
         <ChatInterface backendUrl={backendUrl} authToken={authToken} />
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
