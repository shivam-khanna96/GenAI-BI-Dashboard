/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'fs-bg': '#f7f9fb',           // Light background
        'fs-surface': '#ffffff',      // Card/console background
        'fs-primary': '#1a2a6c',      // Brand blue
        'fs-accent': '#f40082',       // Accent magenta
        'fs-orange': '#ff6600',       // Accent orange
        'fs-border': '#e5e7eb',       // Light border
        'fs-muted': '#6b7280',        // Muted text
        'accent-cyan': '#00e5ff',
      },
      // Define the subtle background grid pattern
      backgroundImage: {
        'grid-pattern': `linear-gradient(to right, rgba(43, 56, 112, 0.2) 1px, transparent 1px),
                         linear-gradient(to bottom, rgba(43, 56, 112, 0.2) 1px, transparent 1px)`,
      },
      // Define background size for the pattern
      backgroundSize: {
        'grid-size': '2rem 2rem',
      },
      // Add custom animations
      animation: {
        'aurora': 'aurora 60s linear infinite',
      },
      // Add keyframes for the animation
      keyframes: {
        aurora: {
          from: {
            'background-position': '0% 50%',
          },
          to: {
            'background-position': '200% 50%',
          },
        },
      },
      boxShadow: {
        'soft': '0 2px 8px 0 rgba(16,30,54,0.06)',
      },
      borderRadius: {
        'xl': '1rem',
      },
    },
  },
  plugins: [],
}
