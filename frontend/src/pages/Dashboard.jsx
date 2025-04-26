import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../utils/supabase';

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

  // Check for authentication and redirect if not authenticated
  useEffect(() => {
    const getUserSession = async () => {
      try {
        const { data, error } = await supabase.auth.getSession();
        
        if (error) {
          throw error;
        }
        
        if (!data.session) {
          navigate('/');
          return;
        }
        
        setSession(data.session);
        setUser(data.session.user);
      } catch (error) {
        console.error('Error getting session:', error);
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    
    getUserSession();
    
    // Set up auth state listener
    const { data: authListener } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (event === 'SIGNED_OUT') {
          navigate('/');
        }
        
        if (session) {
          setUser(session.user);
          setSession(session);
        }
      }
    );
    
    return () => {
      if (authListener && authListener.subscription) {
        authListener.subscription.unsubscribe();
      }
    };
  }, [navigate]);

  const handleSignOut = async () => {
    try {
      await supabase.auth.signOut();
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
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !sessionData.session) {
        console.error('Error getting session or no session found:', sessionError);
        // Optionally navigate to login or show an error message
        setGeneratingStudyGuide(false);
        return;
      }

      const token = sessionData.session.access_token;

      const response = await fetch('http://localhost:5001/api/generate-study-guide', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        // body: JSON.stringify({ startTime: studyStartTime, endTime: studyEndTime }) // Optional: send study times
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
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !sessionData.session) {
        console.error('Error getting session or no session found:', sessionError);
        setGeneratingQuiz(false);
        return;
      }

      const token = sessionData.session.access_token;

      const response = await fetch('http://localhost:5001/api/generate-quiz', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        // body: JSON.stringify({ studyGuideContent: studyGuide?.content }) // Optional: send context
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
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-xl">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">[Name In Progress]</h1>
          {user && (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">{user.email}</span>
              <button 
                onClick={handleSignOut}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Sign Out
              </button>
            </div>
          )}
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white shadow-md rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Study Session</h2>
          
          {!isStudying ? (
            <div>
              {studyEndTime && (
                <div className="mb-4 p-3 bg-green-100 rounded">
                  <p>Last study session ended: {studyEndTime.toLocaleString()}</p>
                  <p>Duration: {Math.round((studyEndTime - studyStartTime) / 60000)} minutes</p>
                </div>
              )}
              
              <button 
                onClick={startStudySession}
                className="btn-primary"
              >
                Start Study Session
              </button>
              
              {studyEndTime && (
                <div className="mt-8 space-y-4">
                  <button 
                    onClick={generateStudyGuide}
                    className="btn-primary mr-4"
                    disabled={generatingStudyGuide}
                  >
                    {generatingStudyGuide ? 'Generating...' : 'Generate Study Guide'}
                  </button>
                  
                  <button 
                    onClick={generateQuiz}
                    className="btn-primary"
                    disabled={generatingQuiz}
                  >
                    {generatingQuiz ? 'Generating...' : 'Generate Quiz'}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center">
              <p className="text-lg mb-4">Study session in progress...</p>
              <p className="mb-4">Started at: {studyStartTime.toLocaleString()}</p>
              <p className="mb-8">Time elapsed: {Math.round((new Date() - studyStartTime) / 60000)} minutes</p>
              
              <button 
                onClick={stopStudySession}
                className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 transition-colors duration-300"
              >
                Stop Study Session
              </button>
            </div>
          )}
        </div>
        
        {studyGuide && (
          <div className="bg-white shadow-md rounded-lg p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">{studyGuide.title}</h2>
            <div className="prose max-w-none">
              <p>{studyGuide.content}</p>
            </div>
          </div>
        )}
        
        {quiz && (
          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">{quiz.title}</h2>
            <div className="space-y-6">
              {quiz.questions.map((q, index) => (
                <div key={index} className="p-4 border border-gray-200 rounded">
                  <p className="font-medium mb-3">{q.question}</p>
                  <div className="space-y-2">
                    {q.options.map((option, optionIndex) => (
                      <div key={optionIndex} className="flex items-center">
                        <input 
                          type="radio" 
                          name={`question-${index}`} 
                          id={`question-${index}-option-${optionIndex}`}
                          className="mr-2"
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
