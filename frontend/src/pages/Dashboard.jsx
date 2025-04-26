import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [isStudying, setIsStudying] = useState(false);
  const [studyStartTime, setStudyStartTime] = useState(null);
  const [studyEndTime, setStudyEndTime] = useState(null);
  const [generatingStudyGuide, setGeneratingStudyGuide] = useState(false);
  const [generatingQuiz, setGeneratingQuiz] = useState(false);
  const [studyGuide, setStudyGuide] = useState(null);
  const [quiz, setQuiz] = useState(null);

  // Check for authentication via the backend
  useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        // Check if we were redirected from a successful login
        // For now, assume we're logged in if we reached the dashboard page
        // In a production app, we would check with the backend if the session is valid
        
        // Simulate a user for now
        setUser({
          email: 'user@example.com',
          id: '123456'
        });
        setLoading(false);
        
        // In the future, you could validate the session with the backend:
        // const response = await fetch('http://localhost:8000/check-auth', {
        //   credentials: 'include' // This sends the session cookie
        // });
        // const data = await response.json();
        // if (!data.authenticated) navigate('/');
        // else setUser(data.user);
      } catch (error) {
        console.error('Error checking authentication:', error);
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    
    checkAuthStatus();
  }, [navigate]);

  const handleSignOut = async () => {
    try {
      // Call the backend to sign out
      await fetch('http://localhost:8000/logout', {
        method: 'POST',
        credentials: 'include' // Send session cookie
      });
      navigate('/');
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const startStudySession = () => {
    setIsStudying(true);
    setStudyStartTime(new Date());
    setStudyGuide(null);
    setQuiz(null);
  };

  const stopStudySession = () => {
    setIsStudying(false);
    setStudyEndTime(new Date());
  };

  const generateStudyGuide = async () => {
    setGeneratingStudyGuide(true);
    setStudyGuide(null); // Clear previous guide
    
    try {
      // In our new approach, we're using browser cookies for session management
      // The backend will use the session cookie to authenticate requests
      // No need to manually pass a token

      const response = await fetch('http://localhost:8000/api/generate-study-guide', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include', // Send session cookie for authentication
        body: JSON.stringify({ startTime: studyStartTime?.toISOString(), endTime: studyEndTime?.toISOString() })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setStudyGuide(data);
    } catch (error) {
      console.error('Error generating study guide:', error);
      // Display error to user?
      setStudyGuide({ title: "Error", content: `Failed to generate study guide: ${error.message}` });
    } finally {
      setGeneratingStudyGuide(false);
    }
  };

  const generateQuiz = async () => {
    setGeneratingQuiz(true);
    setQuiz(null); // Clear previous quiz
    
    try {
      // Authentication is handled via browser cookies with the FastAPI backend

      const response = await fetch('http://localhost:8000/api/generate-quiz', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include', // Send session cookie for authentication
        body: JSON.stringify({ studyGuideContent: studyGuide?.content })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setQuiz(data);
    } catch (error) {
      console.error('Error generating quiz:', error);
      setQuiz({ title: "Error", questions: [{ question: `Failed to generate quiz: ${error.message}`, options: [], answer: -1 }]});
    } finally {
      setGeneratingQuiz(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: '1.25rem' }}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f3f4f6' }}>
      <header style={{ backgroundColor: 'white', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#111827' }}>[Name In Progress]</h1>
          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span style={{ fontSize: '0.875rem', color: '#4b5563' }}>{user.email}</span>
              <button 
                onClick={handleSignOut}
                style={{ fontSize: '0.875rem', color: '#dc2626', cursor: 'pointer' }}
                onMouseEnter={(e) => e.target.style.color = '#b91c1c'}
                onMouseLeave={(e) => e.target.style.color = '#dc2626'}
              >
                Sign Out
              </button>
            </div>
          )}
        </div>
      </header>
      
      <main style={{ maxWidth: '80rem', margin: '0 auto', padding: '2rem 1rem' }}>
        <div style={{ backgroundColor: 'white', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', borderRadius: '0.5rem', padding: '1.5rem', marginBottom: '2rem' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>Study Session</h2>
          
          {!isStudying ? (
            <div>
              {studyEndTime && (
                <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#dcfce7', borderRadius: '0.25rem' }}>
                  <p>Last study session ended: {studyEndTime.toLocaleString()}</p>
                  <p>Duration: {Math.round((studyEndTime - studyStartTime) / 60000)} minutes</p>
                </div>
              )}
              
              <button 
                onClick={startStudySession}
                style={{ backgroundColor: '#4285f4', color: 'white', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' }}
              >
                Start Study Session
              </button>
              
              {studyEndTime && (
                <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <button 
                    onClick={generateStudyGuide}
                    style={{ backgroundColor: '#4285f4', color: 'white', padding: '8px 16px', borderRadius: '4px', marginRight: '1rem', cursor: generatingStudyGuide ? 'not-allowed' : 'pointer', opacity: generatingStudyGuide ? 0.7 : 1 }}
                    disabled={generatingStudyGuide}
                  >
                    {generatingStudyGuide ? 'Generating...' : 'Generate Study Guide'}
                  </button>
                  
                  <button 
                    onClick={generateQuiz}
                    style={{ backgroundColor: '#4285f4', color: 'white', padding: '8px 16px', borderRadius: '4px', cursor: generatingQuiz ? 'not-allowed' : 'pointer', opacity: generatingQuiz ? 0.7 : 1 }}
                    disabled={generatingQuiz}
                  >
                    {generatingQuiz ? 'Generating...' : 'Generate Quiz'}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <p style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>Study session in progress...</p>
              <p style={{ marginBottom: '1rem' }}>Started at: {studyStartTime.toLocaleString()}</p>
              <p style={{ marginBottom: '2rem' }}>Time elapsed: {Math.round((new Date() - studyStartTime) / 60000)} minutes</p>
              
              <button 
                onClick={stopStudySession}
                style={{ backgroundColor: '#dc2626', color: 'white', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' }}
              >
                Stop Study Session
              </button>
            </div>
          )}
        </div>
        
        {studyGuide && (
          <div style={{ backgroundColor: 'white', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', borderRadius: '0.5rem', padding: '1.5rem', marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>{studyGuide.title}</h2>
            <div style={{ maxWidth: 'none' }}>
              <p>{studyGuide.content}</p>
            </div>
          </div>
        )}
        
        {quiz && (
          <div style={{ backgroundColor: 'white', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', borderRadius: '0.5rem', padding: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>{quiz.title}</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {quiz.questions.map((q, index) => (
                <div key={index} style={{ padding: '1rem', border: '1px solid #e5e7eb', borderRadius: '0.25rem' }}>
                  <p style={{ fontWeight: '500', marginBottom: '0.75rem' }}>{q.question}</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {q.options.map((option, optionIndex) => (
                      <div key={optionIndex} style={{ display: 'flex', alignItems: 'center' }}>
                        <input 
                          type="radio" 
                          name={`question-${index}`} 
                          id={`question-${index}-option-${optionIndex}`}
                          style={{ marginRight: '0.5rem' }}
                        />
                        <label htmlFor={`question-${index}-option-${optionIndex}`}>
                          {option}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
