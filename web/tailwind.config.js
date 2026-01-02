/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Terminal dark theme
        background: '#0a0a0a',
        foreground: '#fafafa',
        card: '#111111',
        border: '#1f1f1f',
        muted: '#888888',
        // Trading colors
        profit: '#10b981',  // Green
        loss: '#ef4444',    // Red
        warning: '#f59e0b', // Amber
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'Monaco', 'monospace'],
      },
    },
  },
  plugins: [],
}
