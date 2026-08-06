/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        page: '#F6F6F4',
        surface: '#FFFFFF',
        surfacealt: '#F1F1EE',
        ink: '#141514',
        ink2: '#5C5C58',
        brand: { DEFAULT: '#1A2F24', hover: '#112119' },
        clay: '#C06E52',
        moss: '#4A5D4E',
        sand: '#E6E2D6',
        agborder: '#E5E4E0',
        ok: '#4A5D4E',
        warn: '#D99530',
        bad: '#9B3922',
      },
      borderRadius: {
        sm: '4px',
      },
    },
  },
  plugins: [],
};
