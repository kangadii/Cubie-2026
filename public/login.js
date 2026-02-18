/**
 * CubieHelp Login Page JavaScript
 * Handles form submission, authentication, and dark mode
 */

document.addEventListener('DOMContentLoaded', function () {
    // Get DOM elements
    const loginForm = document.getElementById('login-form');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginBtn = document.getElementById('login-btn');
    const btnText = loginBtn.querySelector('.btn-text');
    const btnLoader = loginBtn.querySelector('.btn-loader');
    const errorMessage = document.getElementById('error-message');
    const toggleDarkBtn = document.getElementById('toggle-dark');

    // Dark mode functionality
    const savedTheme = localStorage.getItem('cubie-theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        toggleDarkBtn.textContent = '☀️';
    }

    toggleDarkBtn.addEventListener('click', function () {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        toggleDarkBtn.textContent = isDark ? '☀️' : '🌙';
        localStorage.setItem('cubie-theme', isDark ? 'dark' : 'light');
    });

    // Form submission
    loginForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        // Get credentials
        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        // Validate
        if (!username || !password) {
            showError('Please enter both username and password');
            return;
        }

        // Hide previous errors
        hideError();

        // Show loading state
        setLoading(true);

        try {
            // Send login request
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Login successful!
                console.log('Login successful:', data.user);

                // Redirect to chat interface
                window.location.href = '/';
            } else {
                // Login failed
                showError(data.error || 'Invalid username or password');
                setLoading(false);
            }

        } catch (error) {
            console.error('Login error:', error);
            showError('Connection error. Please try again.');
            setLoading(false);
        }
    });

    // Helper function to show error
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    // Helper function to hide error
    function hideError() {
        errorMessage.classList.add('hidden');
    }

    // Helper function to set loading state
    function setLoading(isLoading) {
        if (isLoading) {
            loginBtn.disabled = true;
            btnText.style.display = 'none';
            btnLoader.classList.remove('hidden');
            btnLoader.classList.add('show');
        } else {
            loginBtn.disabled = false;
            btnText.style.display = 'inline-block';
            btnLoader.classList.add('hidden');
            btnLoader.classList.remove('show');
        }
    }

    // Clear error on input
    usernameInput.addEventListener('input', hideError);
    passwordInput.addEventListener('input', hideError);
});
