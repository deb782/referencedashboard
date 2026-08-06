/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Cormorant Garamond', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        page: '#faf8f5',
        surface: '#ffffff',
        surfacealt: '#f4f2ea',
        ink: '#1a1a1a',
        ink2: '#4a5568',
        brand: { DEFAULT: '#5a6b10', hover: '#3d4a0a', light: '#7a8e1a' },
        accent: '#8fa832',
        clay: '#a8763f',
        moss: '#7a8e1a',
        sand: '#e8e0d0',
        beige: '#d4c8b0',
        agborder: '#e8e0d0',
        ok: '#5a6b10',
        warn: '#c8912f',
        bad: '#a33b28',
      },
      boxShadow: {
        subtle: '0 4px 30px rgba(90, 107, 16, 0.08)',
        medium: '0 15px 50px rgba(90, 107, 16, 0.12)',
        strong: '0 24px 70px rgba(90, 107, 16, 0.18)',
      },
    },
  },
  plugins: [],
};
