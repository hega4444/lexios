// chat.js manages the connection with the server and messages exchangek-remember

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

// Store the original height of the textarea when the page loads

document.addEventListener('DOMContentLoaded', function () {
    const messageInput = document.getElementById('message-input');
    messageInput.setAttribute('data-original-height', messageInput.clientHeight);
}); 

// Submit request to Lexi

async function submitForm(url, messageInput, fileInput) {
    try {
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        const originalHeight = messageInput.getAttribute('data-original-height');
        
        // Construct the form data to include session_id
        const session_id = await fetchSessionID();

        const formData = new FormData();
        formData.append('csrf_token', csrfToken);
        formData.append('session_id', session_id);

        const userMessage = messageInput.value;

        if (userMessage.trim() !== "" || fileInput.files[0]) {

            // Set the animation mode to "think"
            setAnimationMode('think');

            if (userMessage.trim() !== "") {
                formData.append('user_input', userMessage);
                let messageInnerHTML = userMessage.replace(/\n/g, '<br>');
                addMessageToChat(messageInnerHTML, null, "user", "text");
            }

            if (fileInput.files[0]) {
                formData.append('file_upload', fileInput.files[0]);
                const fileName = fileInput.files[0].name;
                addMessageToChat(`Uploading file "${fileName}"`, null,  "system", "sys_notif", false, true);
            }

            // AJAX request to the Flask backend
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRF-Token': csrfToken,
                },
                body: formData
            });

            // Clear the input field
            messageInput.value = "";
            fileInput.value = "";
            messageInput.style.height = originalHeight + 'px';
        }

    } catch (error) {
        console.error('Error:', error);
        }
}

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("message-form");
    const messageInput = document.getElementById("message-input");
    const fileInput = document.getElementById("file-upload-input");
    const maxHeight = 200; // Set the maximum height (adjust as needed)
    
    const chatMessages = document.querySelector(".msg-body ul");


    // Chat dropdown list buttons
    const reloadButton = document.getElementById("reload-button");
    const speechRecognitionButton= document.getElementById("speech-recognition-button"); "speak-button"
    const speakModeButton= document.getElementById("speak-button");
    const settingsButton = document.getElementById("settings-button");

    // Remove the disconnect event listener, as plain WebSockets don't have it.

    (async () => {
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
    
        if (session_id !== null) {
            // Listen and update messages:
            socket.addEventListener('message', async (event) => {
                // Handle incoming Lexi messages
                let data = JSON.parse(event.data)
                let message = data.content || "" ;
                const isSpell = data.spell; // Check the 'spell' property
                const msg_type = data.msg_type; // Check the msg_type
                const metadata = data.metadata || null // Retrieve the metadata
                const images = data.images || null; // Retrieve images
                const conversation_id = data.conversation_id // Conversation_id 

                console.log("New Lexi message:", message);

                try {
                    // Check which is the current conversation_id_focus
                    const response = await fetch('/get_conversation_id_focus');
                    const fetchedData = await response.json();
                    const conversation_id_focus = fetchedData.conversation_id_focus;

                    // Title update
                    if (msg_type === "title_update"){
                        autogeneratedTitle(conversation_id, message)
                    }

                    // Show message on screen if it belongs to the active conversation only
                    else if (conversation_id === conversation_id_focus) {
                        // Sanitize and process the message as before
                        // no longer needed message = escapeHTML(message);

                        // Consent screen creation
                        if (msg_type === "consent_screen") {
                            
                            // Verify with user on screen
                            const user_response = await createConsentScreen(message, metadata);   
                        }
                        // Add prompt for Lexi
                        else if (msg_type === "text") {
                            message = "Lexi: " + message;
                        
                            // Use the new function to add the message to the chat
                            await addMessageToChat(message, images, "system", msg_type, isSpell, metadata);

                            // Example: Set the animation mode to "breath"
                            setAnimationMode('breath');
                        }
                    }
                } catch (error) {
                    console.error('Error:', error);
                }
            });
        }
    })();

    

    // Add a keydown event listener to the textarea
    document.getElementById('message-input').addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && event.shiftKey) {
            // If Shift+Enter is pressed, insert a newline character
            const textarea = event.target;
            const currentCursorPosition = textarea.selectionStart;
            const textareaValue = textarea.value;
            const newValue = textareaValue.substring(0, currentCursorPosition) + '\n' + textareaValue.substring(currentCursorPosition);
            textarea.value = newValue;
            textarea.selectionStart = textarea.selectionEnd = currentCursorPosition + 1;
            event.preventDefault(); // Prevent a new line in the textarea
        } else if (event.key === 'Enter' && !event.getModifierState('Shift')) {
            // If Enter is pressed without Shift, manually trigger the form submission
            event.preventDefault();
            const submitEvent = new Event('submit', {
                bubbles: true,
                cancelable: true,
            });

            form.dispatchEvent(submitEvent);
        }
    });

    messageInput.addEventListener('input', function () {
        this.style.height = 'auto'; // Reset the height
        const newHeight = Math.min(this.scrollHeight, maxHeight);
        this.style.height = newHeight + 'px'; // Adjust the height based on content
    });

    // Attach the submitForm function to the form submit event
    form.addEventListener("submit", async function (event) {
        event.preventDefault(); // Prevent the default form submission behavior 
        try {
            await submitForm(form.getAttribute("action"), messageInput, fileInput);
        } catch (error) {
            console.error('Error submitting form:', error);
        }
    });

    // Function to get the CSRF token from cookies (you can include this function)
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                
                // Search for the CSRF cookie by name
                if (cookie.startsWith(name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Event listener for the Reload button
    reloadButton.addEventListener("click", async function (event) {
        event.preventDefault(); // Prevent the default link behavior

        try {
            // Get the user ID using the fetchUserID function
            const sessionId = await fetchSessionID();
            const csrfToken = document.querySelector('input[name="csrf_token"]').value; // Get CSRF token from the form

            if (sessionId) {
                // Make an HTTP POST request to the Flask route with the session_id parameter
                const response = await fetch("/reset_user_thread_request", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        'X-CSRF-Token': csrfToken // Include the CSRF token here
                    },
                    body: JSON.stringify({ session_id: sessionId }),
                });

                // Check the response status
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }

                // If needed, you can process the response further here
            }
        } catch (error) {
            console.error("Error:", error);
        }
    });

    // Event listener for the Speech Recognition button
    speechRecognitionButton.addEventListener("click", function (event) {
        event.preventDefault(); // Prevent the default link behavior
        // Add your logic for the Share button here
        console.log("Speech recognition button clicked");
        speech_recognition_mode = !speech_recognition_mode;
        if (speech_recognition_mode == true) {
            // activate speech recognition
            speechRecognitionButton.innerHTML = "Speech recognition Off.."
            ready_to_start_listening = true
            startRecognition()
        } else {
            speechRecognitionButton.innerHTML = "Speech recognition On.."
        }
    });

    // Event listener for the Speak button
    speakModeButton.addEventListener("click", function (event) {
        event.preventDefault(); // Prevent the default link behavior
        // Add your logic for the Share button here
        console.log("Speak mode button clicked");
        speak_mode = !speak_mode;
        if (speak_mode == true) {
            // activate speech recognition
            speakModeButton.innerHTML = "Speak Off.."
        } else {
            speakModeButton.innerHTML = "Speak On.."
        }
    });

    // Event listener for the Settings button
    settingsButton.addEventListener("click", function (event) {
        event.preventDefault(); // Prevent the default link behavior
        // Add your logic for the Settings button here
        console.log("Settings button clicked");
    });

});

// Function to set the animation mode
function setAnimationMode(mode) {
    var background = document.querySelector('.background-image');

    // Check the specified mode and apply the corresponding animation
    if (mode === 'think') {
        // Spinning Animation ("think" mode)
        background.style.animation = 'spinAnimation 40s linear, rotateCenter 40s infinite linear';
        background.style.transformOrigin = 'center';
        background.style.opacity = '0.1';
    }

    if (mode === 'breath') {
        // Zoom Animation ("breath" mode)
        background.style.animation = 'zoomAnimation 4s infinite alternate';
        background.style.transformOrigin = 'initial';
        background.style.opacity = '0.1';
    }
}
