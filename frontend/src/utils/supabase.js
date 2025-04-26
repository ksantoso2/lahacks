import { createClient } from '@supabase/supabase-js';

// Initialize the Supabase client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'public-anon-key';

// Log for debugging
console.log('Supabase initialization with:', { 
  urlProvided: !!import.meta.env.VITE_SUPABASE_URL,
  keyProvided: !!import.meta.env.VITE_SUPABASE_ANON_KEY
});

if (!import.meta.env.VITE_SUPABASE_URL || !import.meta.env.VITE_SUPABASE_ANON_KEY) {
  console.warn('⚠️ Using placeholder Supabase credentials. Authentication will not work.');
  console.warn('Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env file.');
}

// Create client with placeholder values if needed
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

