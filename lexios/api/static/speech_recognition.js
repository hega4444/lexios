let speech_recognition_mode = false;
let speak_mode = false;
let recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)(); // Iniatiate recognition;
let canStartRecognition = true; // Flag to control recognition start
let ready_to_start_listening = true


// Function to start recognition
function startRecognition() {
    
    const form = document.getElementById('message-form');
    const fileInput = document.getElementById("file-upload-input");
    const messageInput = document.getElementById('message-input');

    let transcript = ''; // Store recognized speech
    let typingTimer; // Timer for detecting typing pause
    const typingInterval = 2000; // 2 seconds (adjust as needed)

    recognition.continuous = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
        if (speech_recognition_mode) {
            for (let i = event.resultIndex; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    transcript += event.results[i][0].transcript;
                } else {
                    transcript += event.results[i][0].transcript + ' ';
                    messageInput.value = transcript;
                }
        
            }
        }else {
            recognition.stop()
            ready_to_start_listening = true
        }

        // Update the messageInput area with the transcript
        messageInput.value = transcript;

        // Clear the typing timer if it's already running
        clearTimeout(typingTimer);

        // Set a timer to wait for 2 seconds of typing pause before submitting the form
        typingTimer = setTimeout(() => {
            if (transcript.trim() !== "" && speech_recognition_mode == true) {
                submitForm(form.getAttribute("action"), messageInput, fileInput);
                transcript = ''; // Clear transcript after submission
            }
        }, typingInterval);
    };

    recognition.onerror = (event) => {
        //console.error('Recognition error:', event.error);
        if (speech_recognition_mode == true && canStartRecognition) {
            startRecognition();
        }
    };

    if (canStartRecognition && ready_to_start_listening) {
        recognition.start()
        ready_to_start_listening = false
    }

    recognition.onend = () => {
        // Restart recognition when it ends if allowed
        if (speech_recognition_mode == true && canStartRecognition) {
            startRecognition();
        }
    };
}

// Function to convert text to speech
function speakText(text) {
    // First pause the active listening
    if (speech_recognition_mode) {
        if (recognition){
            recognition.stop();
        }
        canStartRecognition = false; // Prevent immediate restart
        ready_to_start_listening = true
    }

    // Remove the first word "Lexi:" if it exists
    const textToSpeak = text.replace(/^Lexi:/, '').trim();

    // Create a SpeechSynthesisUtterance object
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    // Customize the voice
    utterance.voice = speechSynthesis.getVoices().find(voice => voice.name === 'Google UK English Female');

    // Speak the text
    utterance.onend = () => {
        // Resume speech recognition after a delay
        setTimeout(() => {
            canStartRecognition = true;
            startRecognition();
            console.log("Speech recognition resumed.")
        }, 1000); // Resume recognition after 1 second
    };

    // Start speaking
    speechSynthesis.speak(utterance);


}
