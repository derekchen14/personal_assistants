/** @type {import('tailwindcss').Config} */
import colors from 'tailwindcss/colors'

export default {
  content: [
    './app.html',
    './src/**/*.{html,svelte,js,ts}',
    './node_modules/flowbite-svelte/**/*.{svelte,js,ts}',
  ],
  theme: {
    extend: {
      typography: (theme) => ({
        DEFAULT: {
          css: {
            h1: {
              fontFamily: 'Merriweather Sans',
            },
            p1: {
              fontFamily: 'Roboto',
            }
          },
        },
      }),  // For landing page design
      colors: {
        primary: '#3490dc',
        secondary: '#00bfff',
        danger: '#e3342f',
        color_a: '#E48586',
        color_b: '#E48586',
        color_c: '#03C988',
        font: '#FFFFFF',
        nav_button: '#6495ED',
        nav_bg: '#FFFFFF',
        button_bg: '#FFFFFF',
        emerald: colors.emerald,
        orange: colors.orange,
        custom_green: '#01B8AD',
        custom_green_hover: '#04D8D5',
        ink: '#202232',
        ink_hover: '#2A2C44',
        ivory_light: '#FFFEFA',
        ivory: '#FFF5EE',
      },
      gradientColorStops: (theme) => ({
        ...theme('colors'),
        primary: '#4c788b',
        secondary: '#d1e59c',
        danger: '#e3342f',
        nav_button_bg: '#4c788b',
      }),
      maxWidth: {
        '1/5': '20%',
        '2/5': '40%',
        '3/5': '60%',
        '4/5': '80%',
      },
      fontFamily: {
        code: ['Fira Code', 'monospace'],
        'rem': ['REM', 'sans-serif'],
      },
      keyframes: {
        fadeUp: {
          '0%': { transform: 'translateY(30px)', opacity: '0' },
          '75%': { transform: 'translateY(-2px)' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        }
      },
      animation: {
        fadeUp: 'fadeUp .4s ease-out',
      }
    },
    screens: {
      sm: '640px',
      md: '768px',
      lg: '1280px',
      xl: '1792px',
    },
  },
  variants: {
    extend: {
      fontWeight: ['hover', 'focus'],
      textColor: ['hover'],
      backgroundColor: ['hover'],
      opacity: ['hover', 'focus', 'group-hover'],
      display: ['hover', 'focus', 'group-hover'],
    },
  },
  plugins: [require('flowbite/plugin'), require('@tailwindcss/typography')],
  darkMode: 'class',
};
