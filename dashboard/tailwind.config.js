/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: '#070b14' },
        panel: { DEFAULT: '#0d1320', alt: '#111827' },
        border: { DEFAULT: '#1c2537' },
        'text-primary': '#f8fafc',
        'text-secondary': '#94a3b8',
        accent: { DEFAULT: '#635bff', hover: '#7c75ff' },
        success: { DEFAULT: '#22c55e' },
        warning: { DEFAULT: '#f59e0b' },
        danger: { DEFAULT: '#ef4444' },
        whatsapp: { DEFAULT: '#25d366' },
        telegram: { DEFAULT: '#229ed9' },
        signal: { DEFAULT: '#3a76f0' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
