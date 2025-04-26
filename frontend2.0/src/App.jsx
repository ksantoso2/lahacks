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

  useEffect(() => {
    const hash = window.location.hash.substring(1); // Remove leading '#'
    const params = new URLSearchParams(hash);
  
    const accessToken = params.get('access_token');
    const idToken = params.get('id_token');
  
    if (accessToken) {
      console.log("✅ Access Token found:", accessToken.substring(0, 10) + "...");
      setAuthToken(accessToken);  // ✅ Now backend will get access token, not ID token
    } else if (idToken) {
      console.warn("⚠️ Only ID token found, no access token.");
      setAuthToken(idToken); // Fallback (optional)
    } else {
      console.error("❌ No tokens found in URL fragment.");
    }
  
    // OPTIONAL: Clear URL fragment after parsing
    window.history.replaceState(null, "", window.location.pathname);
  
    setIsLoadingToken(false);
  }, []);
  

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
