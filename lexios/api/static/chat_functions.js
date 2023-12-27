// Here all the functions related to creating new chat messages

function typeMessage(message, element, callback) {
    let index = 0;
    const messageLength = message.length;
    const minTypingSpeed = 3; // Minimum typing time in milliseconds per character
    const maxTypingSpeed = 20; // Maximum typing time in milliseconds per character

    // Function to add the next character to the element
    function typeCharacter() {
        if (index < message.length) {
            // Check if the next character is an HTML tag
            if (message.charAt(index) === "<") {
                // Find the closing ">" to extract the entire tag
                const endIndex = message.indexOf(">", index);
                if (endIndex !== -1) {
                    const htmlTag = message.substring(index, endIndex + 1);
                    element.innerHTML += htmlTag;
                    index = endIndex + 1;
                }
            } else {
                // If not an HTML tag, add the next character
                element.innerHTML += message.charAt(index);
                index++;
            }

            // Calculate typing speed based on message length
            const typingSpeed = Math.max(
                minTypingSpeed,
                Math.min(maxTypingSpeed, 1000 / messageLength)
            );

            setTimeout(typeCharacter, typingSpeed);
        } else {
            // Call the callback function after typing is complete
            if (typeof callback === "function") {
                callback();
            }
        }
    }

    // Start typing
    typeCharacter();
}

function addMessageToChat(messageText, source, type, spell = false, metadata = null, time = null) {
    const chatMessages = document.querySelector(".msg-body ul");
    const messageScrollArea = document.getElementById("modal-body-messages");

    // Create a new list item
    const newMessageContainer = document.createElement("li");

    // Create a new paragraph element for the message text
    const newMessage = document.createElement("p");

    // Create a span element for the timestamp
    const timestampSpan = document.createElement("span");
    timestampSpan.className = "time";

    // Set the timestamp text content to the provided time (formatted string)
    timestampSpan.textContent = time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Customize styling based on source and type
    if (source === "user") {
        newMessageContainer.classList.add("repaly");
        newMessage.innerHTML = messageText;

    } else if (source === "system") {
        newMessageContainer.classList.add("sender");
        newMessage.innerHTML = ""; // Clear the text content

    /*
        // Remove the 'processing...' animation

        const textDotsGIFContainer = chatMessages.querySelector(".typing-animation-container");
        if (textDotsGIFContainer) {
            textDotsGIFContainer.remove();
        }
    */

        if (type === "sys_notif") {
            // Add custom styling for system notification messages
            newMessage.classList.add("notification-message", "sender"); // Add both classes
            newMessage.style.backgroundColor = "rgba(76, 21, 127, 0.689)";
            newMessage.style.color = "rgba(230, 227, 235, 0.885)";

            if (metadata && metadata.attachment) {
                // Check if "attachment" has a "file_path" property
                if (metadata.attachment.file_path) {
                    // Create a link element
                    const link = document.createElement("a");
                    link.href = metadata.attachment.file_path; // Set the link target
                    link.textContent = messageText; // Use the message text as link text
                    newMessage.appendChild(link); // Append the link to the message
                } 
                else  {
                    // For non-system messages, preserve the text content
                    newMessage.innerHTML = messageText
                }
            } else {
                // For non-system messages, preserve the text content
                newMessage.innerHTML = messageText
            }
        } else {  // Call typeMessage with appropriate arguments

                if (speak_mode == true) {
                    speakText(messageText)
                }
                if (spell === true){
                    typeMessage(messageText, newMessage, () => {
                    // Callback function to be executed after typing is complete
                    // This function can be empty or contain additional logic
                    // Scroll to the bottom of the chat box to show the new message
                    scrollToBottom(messageScrollArea);
                    
                    });
                }
                else {
                    // Add the message directly
                    newMessage.innerHTML = messageText
                }
        }
    }

    // Append the message to the message container
    newMessageContainer.appendChild(newMessage);
    // Append the timestamp to the list item
    newMessageContainer.appendChild(timestampSpan);

    // Append the message container to the chat messages
    chatMessages.appendChild(newMessageContainer);

/*
    // Customize styling based on source and type
    if (source === "user" && !time) {
        // Create a new div element for the GIF
        const gifContainer = document.createElement("div");
        gifContainer.classList.add("typing-animation-container"); // Add a class for styling

        // Check if you have a GIF file path
        const gifFileName = "loading.gif"; // replace this with the actual file name
        const gifFilePath = `/static/images/${gifFileName}`;

        // Create an img element for the GIF
        const gifImage = document.createElement("img");
        gifImage.src = gifFilePath;
        gifImage.alt = "Typing Animation";

        // Adjust the size of the GIF
        gifImage.style.width = "50px"; // Set the width in pixels
        gifImage.style.height = "50px"; // Set the height in pixels
        gifContainer.style.display = "flex";
        gifContainer.style.justifyContent = "center";
        gifContainer.style.alignItems = "center";

        // Append the GIF element to the gifContainer
        gifContainer.appendChild(gifImage);

        // Append the gifContainer to the newMessageContainer
        chatMessages.appendChild(gifContainer);
    }*/
    
    // Scroll to the bottom of the chat box to show the new message
    scrollToBottom(messageScrollArea);

    // Return the newMessageContainer object
    return newMessageContainer;
}


// Function to scroll to the bottom of the chat container
function scrollToBottom(container) {
    container.scrollTop = container.scrollHeight;
}


