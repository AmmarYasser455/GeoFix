/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                brand: {
                    orange: '#fe9000',
                    pink: '#f0abef',
                    dark: '#050505',
                    gray: '#111111',
                }
            },
            fontFamily: {
                sans: ['Outfit', 'sans-serif'],
            }
        },
    },
    plugins: [],
}
