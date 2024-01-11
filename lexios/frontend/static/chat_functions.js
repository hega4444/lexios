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

async function addMessageToChat(messageText = null, images = null, source, type, spell = false, metadata = null, time = null) {
    const chatMessages = document.querySelector(".msg-body ul");
    const messageScrollArea = document.getElementById("modal-body-messages");
    
    if (source === "system" && messageText) {
        // Replace newline characters with line break elements to preserve formatting
        messageText = messageText.replace(/\n/g, '<br>');
        // Replace ** with bold HTML tags
        messageText = messageText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    }

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


        if (type === "sys_notif") {
            // Add custom styling for system notification messages
            newMessage.classList.add("notification-message", "sender"); // Add both classes
            newMessage.style.backgroundColor = "rgba(76, 21, 127, 0.689)";
            newMessage.style.color = "rgba(230, 227, 235, 0.885)";

            if (metadata && metadata.attachment) {
                // Check if "attachment" has a "file_path" property
                if (metadata.attachment.link) {
                    // Create a link element
                    const link = document.createElement("a");
                    link.href = metadata.attachment.link; // Set the link target
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

    if (images && Object.keys(images).length > 0) {
        const thumbnailsContainer = document.createElement("div");
        thumbnailsContainer.className = "thumbnails";
    
        // Iterate over the images and create thumbnails
        for (const [filename, filepath] of Object.entries(images)) {
            const thumbnail = document.createElement("img");
            // Construct the URL for the thumbnail
            thumbnail.src = filepath;
            thumbnail.alt = filename;
    
            // Apply styles to make thumbnails smaller with fixed height
            thumbnail.style.width = "auto"; // Automatically adjust width to maintain aspect ratio
            thumbnail.style.height = "210px"; // Adjust the height as needed
    
            // Add an event listener to open the full-size image on click
            thumbnail.addEventListener("click", () => {
                // Open a new tab or window with the full-size image
                window.open(filepath, "_blank");
            });
    
            // Append the thumbnail to the container
            thumbnailsContainer.appendChild(thumbnail);
        }

        // Apply styles to the thumbnails container for arrangement
        thumbnailsContainer.style.display = "flex";
        thumbnailsContainer.style.flexWrap = "wrap";
        thumbnailsContainer.style.gap = "5px"; // Adjust the gap between thumbnails as needed

        // Append the thumbnails container to the message container
        newMessageContainer.appendChild(thumbnailsContainer);

    }

    // Append the message container to the chat messages
    chatMessages.appendChild(newMessageContainer);

    // Link wildcards
    // Regular expression to match URLs
    const urlRegex = /(https?|ftp):\/\/[^\s/$.?#].[^\s]*/gi;

    if (messageText) {
        // Check if the messageText contains a URL
        const urls = messageText.match(urlRegex);

        if (urls) {
            // Fetch link previews for the URLs concurrently
            const previews = await Promise.all(urls.map(url => previewLink(url)));
        
            // Use a for...of loop to iterate over the previews array
            for (const [index, preview] of previews.entries()) {
                const url = urls[index];
                processPreview(preview, url, newMessageContainer);
            }
        }
    }
    // Scroll to the bottom of the chat box to show the new message
    scrollToBottom(messageScrollArea);

    // Return the newMessageContainer object
    return newMessageContainer;

}

// Function to scroll to the bottom of the chat container
function scrollToBottom(container) {
    container.scrollTop = container.scrollHeight;
}

// Function to format user_id as a 5-digit string
function formatUserId(user_id) {
    return String(user_id).padStart(5, '0');
}

// Async function to fetch link previews
async function previewLink(url) {
    try {
        const response = await fetch(`/url/${encodeURIComponent(url)}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching link preview:", error);
        return null;
    }
}


// Function to open a link in a new tab
function openLinkInNewTab(url) {
    window.open(url, "_blank");
}


function processPreview(preview, link_url, messageContainer) {
    const { icon_url, title } = preview;

    // Create a thumbnail container
    const containerElement = document.createElement("div");
    containerElement.className = "link_thumbnail";

    const thumbnailContainer = document.createElement("div");

    // Create an image element for the thumbnail
    const thumbnailImage = document.createElement("img");
    thumbnailImage.src = icon_url;
    thumbnailImage.alt = title;
    thumbnailImage.style.width = "70px"; // Adjust the width as needed
    thumbnailImage.style.cursor = "pointer"; // Change cursor on hover
    thumbnailImage.title = "Click to open"; // Tooltip on hover

    // Create a container for the title
    const titleContainer = document.createElement("div");
    titleContainer.style.display = "flex";
    titleContainer.style.alignItems = "center"; // Align items vertically at the center

    // Create a paragraph element for the title (in bold)
    const titleParagraph = document.createElement("p");
    titleParagraph.textContent = title;
    titleParagraph.style.fontWeight = "bold"; // Set the text to bold
    titleParagraph.style.cursor = "pointer"; // Change cursor on hover
    titleParagraph.title = "Click to open"; // Tooltip on hover

    // Append the thumbnail image to the thumbnail container
    thumbnailContainer.appendChild(thumbnailImage);

    // Append the title paragraph to the title container
    titleContainer.appendChild(titleParagraph);

    // Append the thumbnail container and title container to the main container element
    containerElement.appendChild(thumbnailContainer);
    containerElement.appendChild(titleContainer);

    // Add click event listeners to the image and the paragraph
    thumbnailImage.addEventListener("click", () => openLinkInNewTab(link_url));
    titleParagraph.addEventListener("click", () => openLinkInNewTab(link_url));

    messageContainer.appendChild(containerElement);
}

// Flag to check if the consent was submitted
let consentSubmitted = false;

async function createConsentScreen(title, metadata) {
    // Creates the consent screen dialog

    const consentToken = metadata.token;
    const expiresAt = metadata.timer;

    const chatMessages = document.querySelector(".msg-body ul");

    // Create container div
    const container = document.createElement("div");
    container.className = "consent_screen";

    // Create a container for the title
    const titleContainer = document.createElement("div");
    titleContainer.style.display = "flex";
    titleContainer.style.alignItems = "center"; // Align items vertically at the center

    // Create a paragraph element for the title (in bold)
    const titleParagraph = document.createElement("p");
    titleParagraph.style.fontSize = "14px"; // Adjust the font size as needed
    titleParagraph.textContent = title;

    // Append titleParagraph to the titleContainer
    titleContainer.appendChild(titleParagraph);

    // Append titleContainer to the container
    container.appendChild(titleContainer);

    // Create a list for user actions
    const actionList = document.createElement("ul");

    // Create checkbox items for each action in the metadata
    metadata.scopes.forEach((scope, index) => {
        const actionItem = document.createElement("li");

        // Create checkbox input
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true; // Mark the checkbox as checked by default
        checkbox.id = scope.id;
        checkbox.style.marginRight = "4px"; // Adjust the margin as needed

        // Create label for the checkbox
        const label = document.createElement("label");
        label.style.fontSize = "12px";
        label.textContent = scope.text;

        // Append checkbox and label to the actionItem
        actionItem.appendChild(checkbox);
        actionItem.appendChild(label);

        // Append actionItem to the actionList
        actionList.appendChild(actionItem);
    });

    // Append actionList to the container
    container.appendChild(actionList);

    // Create confirm_box div
    const confirm_box = document.createElement("div");
    confirm_box.style.display = "flex"; // Use flexbox to arrange items horizontally
    confirm_box.style.alignItems = "center"; // Align items vertically at the center
    confirm_box.style.justifyContent = "left"; // Align content to left horizontally
    confirm_box.style.padding = "5px"; // Add padding for spacing inside the confirm_box

    // Create a confirmation group
    const confirmGroup = document.createElement("div");

    // Create a confirmation icon
    const confirmationIcon = document.createElement("img");
    confirmationIcon.src = "static/images/confirm-button.png";
    confirmationIcon.alt = "Confirm";
    confirmationIcon.style.width = "15px";
    confirmationIcon.style.height = "15px";
    confirmationIcon.style.cursor = "pointer";
    confirmationIcon.title = "Click to confirm";
    confirmationIcon.classList.add("white-icon"); // Add the white-icon class to make it white
    confirmationIcon.style.marginRight = "4px"; // Adjust the margin as needed

    // Create a label for the confirmation icon
    const confirmLabel = document.createElement("span");
    confirmLabel.style.fontSize = "14px";
    confirmLabel.style.marginRight ="10px";
    confirmLabel.textContent = "Confirm choices";

    // Append elements to the confirmation group
    confirmGroup.appendChild(confirmationIcon);
    confirmGroup.appendChild(confirmLabel);

    // Create a cancel group
    const cancelGroup = document.createElement("div");

    // Create a cancel icon
    const cancelIcon = document.createElement("img");
    cancelIcon.src = "static/images/cancel.png"; // Set the path to your cancel icon
    cancelIcon.alt = "Cancel";
    cancelIcon.style.width = "16px";
    cancelIcon.style.height = "16px";
    cancelIcon.style.cursor = "pointer";
    cancelIcon.title = "Cancel";
    cancelIcon.classList.add("white-icon"); // Add the white-icon class to make it white
    cancelIcon.style.marginRight = "4px"; // Adjust the margin as needed

    // Create a label for the cancel icon
    const cancelLabel = document.createElement("span");
    cancelLabel.style.fontSize = "14px";
    cancelLabel.textContent = "Cancel";

    // Append elements to the cancel group
    cancelGroup.appendChild(cancelIcon);
    cancelGroup.appendChild(cancelLabel);

    // Append confirmation and cancel groups to the confirm_box
    confirm_box.appendChild(confirmGroup);
    confirm_box.appendChild(cancelGroup);

    // Append confirm_box to the container
    container.appendChild(confirm_box);

    // Append the container to the chatMessages
    chatMessages.appendChild(container);

    // Set the flag to false
    consentSubmitted = false;


    // Add event listener to confirm group
    confirmGroup.addEventListener("click", async () => {
        // Add logic to handle confirmation (e.g., submit the selected checkboxes)

        const choicesConfirmed = Array.from(container.querySelectorAll('input[type="checkbox"]')).map((checkbox) => ({
            id: checkbox.id,
            checked: checkbox.checked,
        }));

        // Call the submitConsent function
        await submitConsent(choicesConfirmed, consentToken, "submitted");

        // Close consent dialog
        container.remove();

    });

    // Add event listener to cancel group
    cancelGroup.addEventListener("click", async () => {
        // Send all IDs as false for cancellation
        const choicesCancelled = Array.from(container.querySelectorAll('input[type="checkbox"]')).map((checkbox) => ({
            id: checkbox.id,
            checked: false,
        }));

        // Call the submitConsent function for cancellation
        await submitConsent(choicesCancelled, consentToken, "cancelled");
        
        // Close consent dialog
        container.remove();
    });

    // Set up a timer to automatically submit the consent as expired
    setTimeout(async () => {
        // Check if the consent was not already submitted
        if (!consentSubmitted) {
            const choicesExpired = Array.from(container.querySelectorAll('input[type="checkbox"]')).map((checkbox) => ({
                id: checkbox.id,
                checked: false,
            }));

            // Call the submitConsent function for expiration
            await submitConsent(choicesExpired, consentToken, "expired");

            // Close consent dialog
            container.remove();
        }
    }, expiresAt * 1000); // Convert seconds to milliseconds

}

// Function to submit consent
async function submitConsent(choicesConfirmed, consentToken, status) {
    const formData = new FormData();
    const csrfToken = document.querySelector('input[name="csrf_token"]').value; // Get CSRF token from the form

    const choicesConfirmedStr = JSON.stringify(choicesConfirmed);
    formData.append('choices', choicesConfirmedStr);

    formData.append('consent_token', consentToken);
    formData.append('status', status)

    // Make a POST request to the "confirm_consent_screen" endpoint
    try {
        const response = await fetch("/confirm_consent_screen", {
            method: "POST",
            headers: {
                'X-CSRF-Token': csrfToken,
            },
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        console.log("Confirmation result:", result);
    } catch (error) {
        console.error("Error during confirmation:", error);
    }

    console.log("Selected actions:", choicesConfirmed);

    if (status === "submitted") {
        consent_msg = "Your choices have been submitted."
    }
    else if (status === "cancelled") {
        consent_msg = "Consent request was cancelled."
    }
    else if (status === "expired") {
        consent_msg = "Consent request has expired."
    }

    await addMessageToChat(consent_msg, null, "system", "text", false, null, null)

    // Set the flag to true
    consentSubmitted = true;

}


