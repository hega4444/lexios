document.addEventListener('DOMContentLoaded', function () {

    // Function to load user settings from the server
    function loadUserSettings() {
            // Make a GET request to retrieve user settings
            fetch('/get_user_settings', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
                .then(response => response.json())
                .then(data => {
                    // Populate form fields with the retrieved settings
                    document.getElementById('firstName').value = data.name_first || '';
                    document.getElementById('lastName').value = data.name_last || '';
                    document.getElementById('location').value = data.location || '';
                    document.getElementById('google_id').value = data.google_id || '';
                    document.getElementById('bingSearchCheckbox').checked = data.bing_searches || false;
                    document.getElementById('lexiLearnCheckbox').checked = data.lexi_learns || false;
                    document.getElementById('gmailCheckbox').checked = data.gmail_access || false;
                    document.getElementById('calendarCheckbox').checked = data.google_calendar_access || false;
                    document.getElementById('themeSelection').value = data.theme_selection || 'lexi_default';
                    document.getElementById('backgroundColor').value = data.background_color || '#C4660E';
                    document.getElementById('textColor').value = data.text_color || '#FDFDF6';
                })
                .catch(error => console.error('Error loading user settings:', error));
        
    }

    // Function to update user settings on the server
    function updateUserSettings() {
        // Create a new FormData object
        const formData = new FormData();

        // Append form fields to the FormData object
        formData.append('name_first', document.getElementById('firstName').value);
        formData.append('name_last', document.getElementById('lastName').value);
        formData.append('location', document.getElementById('location').value);
        formData.append('google_id', document.getElementById('google_id').value);
        formData.append('bing_searches', document.getElementById('bingSearchCheckbox').checked);
        formData.append('lexi_learns', document.getElementById('lexiLearnCheckbox').checked);
        formData.append('gmail_access', document.getElementById('gmailCheckbox').checked);
        formData.append('google_calendar_access', document.getElementById('calendarCheckbox').checked);
        formData.append('theme_selection', document.getElementById('themeSelection').value);
        formData.append('background_color', document.getElementById('backgroundColor').value);
        formData.append('text_color', document.getElementById('textColor').value);

        // Include CSRF token in the headers
        const csrfToken = document.getElementById('csrf_token').value;

        // Make a POST request to update user settings
        fetch('/update_user_settings', {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrfToken,
            },
            body: formData,
        })
            .then(response => response.json())
            .then(data => {
                // Optionally handle the response
                console.log('User settings updated successfully:', data);
            })
            .catch(error => console.error('Error updating user settings:', error));
    }

    // Load user settings when the page loads
    loadUserSettings();

    // Attach event listener to form to trigger update
    const form = document.getElementById('settingsForm');
    form.addEventListener('change', function (event) {
        const fieldId = event.target.id;

        // Check if the changed field is a theme-related field
        const isThemeField = ['backgroundColor', 'textColor', 'themeSelection'].includes(fieldId);

        if (!isThemeField) {
            // Update general settings for non-theme fields
            updateUserSettings();
        }
    });

    // Function to handle theme-related actions
    function handleThemeChange(themeName) {
        // Set manualChange to true before making the change
        
        // Make a GET request to get theme colors
        fetch(`/get_theme_colors?theme=${themeName}`)

            .then(response => response.json())
            .then(themeColors => {
                // Update color pickers with theme colors
                document.getElementById('backgroundColor').value = themeColors.background;
                document.getElementById('textColor').value = themeColors.text;

                // Set the theme selection to "user custom"
                document.getElementById('themeSelection').value = themeName;

                // Update globalSettings with user theme colors
                globalSettings.textColor = themeColors.text;
                globalSettings.backgroundColor = themeColors.background;
                updateStyles();
            })
            .catch(error => console.error('Error getting theme colors:', error));

    }

    // Attach event listener to form fields to trigger update when they change
    const themeFormFields = document.querySelectorAll('#textColor, #backgroundColor, #themeSelection');

    themeFormFields.forEach(field => {
        field.addEventListener('change', function () {

            // If the changed field is the theme selection, handle theme change
            if (field.id === 'themeSelection') {
                handleThemeChange(field.value);
                updateUserSettings()
            } else {

                // If the user manually adjusts a color, set the theme selection to "user custom"
                document.getElementById('themeSelection').value = 'user_custom';
                // Update user settings
                updateUserSettings();

                // Update globalSettings with user theme colors
                globalSettings.textColor = document.getElementById('textColor').value;
                globalSettings.backgroundColor = document.getElementById('backgroundColor').value;
                updateStyles();
            }
        });
    });

    // Fetch user id
    const fetchSessionID = async () => {
        try {
            const response = await fetch('/get_session_id');
            const data = await response.json();
            return data.session_id;
        } catch (error) {
            console.error('Error fetching user ID:', error);
            return null;
        }
    };

    // Wrap code in an async function
    const connectToWebSocket = async () => {
        // Fetch the session id
        const session_id = await fetchSessionID();

        // Determine the protocol (http or https)
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';

        // Construct the WebSocket URL
        const webSocketUrl = `${protocol}//${document.domain}:${location.port}/ws/${session_id}`;

        // Create a new WebSocket instance
        const socket = new WebSocket(webSocketUrl);

        socket.addEventListener('open', () => {
            console.log("Connected to server");
        });
    };

    // Call the async function
    connectToWebSocket();

});
