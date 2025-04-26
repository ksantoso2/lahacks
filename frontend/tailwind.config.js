/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        blue: {
          600: '#2563eb',
          700: '#1d4ed8',
        },
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          600: '#4b5563',
          700: '#374151',
          900: '#111827',
        },
        red: {
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
        },
        green: {
          100: '#dcfce7',
        },
      },
    },
  },
  plugins: [],
}
