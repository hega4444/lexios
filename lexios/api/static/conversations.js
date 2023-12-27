// Function to update the conversation title with a POST request
function updateConversationTitle(conversation_id, new_title) {
    const csrfToken = document.querySelector('input[name="csrf_token"]').value; // Get CSRF token from the form
    const apiUrl = '/update_conversation_title';

    // Prepare the form data
    const formData = new FormData();
    formData.append('conversation_id', conversation_id);
    formData.append('new_title', new_title);

    // Prepare the request payload
    const requestBody = {
        method: 'POST',
        headers: {
            'X-CSRF-Token': csrfToken,
        },
        body: formData,
    };

    // Send the POST request
    fetch(apiUrl, requestBody)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Handle the response data if needed
            console.log('Conversation title updated successfully:', data);
        })
        .catch(error => {
            console.error('Error updating conversation title:', error);
        });
}



function createConversationElement(title) {
    const conversationElement = document.createElement('div');
    conversationElement.className = 'conversation-element';
    conversationElement.dataset.conversation_id = title[1]; // Store the ID in the dataset

    // Create the conversation title div with the custom or default title
    const titleElement = document.createElement('div');
    titleElement.className = 'conversation-title';
    titleElement.innerHTML = title[0]; // Use the custom title or "new chat" by default
    conversationElement.appendChild(titleElement);

    // Create the conversation buttons div
    const buttonsElement = document.createElement('div');
    buttonsElement.className = 'conversation-buttons';
    buttonsElement.innerHTML = `
        <button class="btn update-button" aria-label="Edit conversation"></button>
        <button class="btn delete-button" aria-label="Delete conversation"></button>
    `;
    
    // Store the original title
    const originalTitle = title[0];

    // Add a click event listener to the entire conversation element
    conversationElement.addEventListener('click', function(event) {
        // Prevent the event from bubbling up to the document level
        event.stopPropagation();
        
        // Check if the click is on the "edit" button
        if (event.target.classList.contains('update-button')) {
            titleElement.contentEditable = 'true';
            titleElement.classList.add('editable'); // Add the "editable" class
            titleElement.focus();
            
            // Select the text and position the cursor at the end
            const selection = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(titleElement);
            selection.removeAllRanges();
            selection.addRange(range);

        } else if (event.target.classList.contains('delete-button')) {
            // Confirm deletion when the "Delete conversation" button is clicked
            const conversation_id = conversationElement.dataset.conversation_id;
            confirmDeleteConversation(conversation_id);
        } else {
            // Trigger the GET request when the click is not on the "edit" or "delete" button
            const conversation_id = conversationElement.dataset.conversation_id;
            load_conversation_messages(conversation_id);

            // Move the conversation element to the top of the chat list
            moveConversationToTop(conversation_id);
        }
    });

    // Handle Enter key press or click outside to stop editing
    titleElement.addEventListener('keydown', function(event) {
        const conversation_id = conversationElement.dataset.conversation_id;

        if (event.key === 'Enter') {
            const newTitle = titleElement.textContent.trim();
            if (newTitle === '') {
                // If the new title is empty, revert to the original title
                titleElement.textContent = originalTitle;
            } else {
                // Send a POST request to update the conversation title
                updateConversationTitle(conversation_id, newTitle);
            }
            titleElement.contentEditable = 'false';
            titleElement.classList.remove('editable'); // Remove the "editable" class

            // Trigger the GET request when the title is updated
            load_conversation_messages(conversation_id);

            // Move the conversation element to the top of the chat list
            moveConversationToTop(conversation_id);
            
            event.preventDefault();
        }
    });

    titleElement.addEventListener('blur', function() {
        const newTitle = titleElement.textContent.trim();
        if (newTitle === '') {
            // If the new title is empty, revert to the original title
            titleElement.textContent = originalTitle;
        }
        titleElement.contentEditable = 'false';
        titleElement.classList.remove('editable'); // Remove the "editable" class
    });

    conversationElement.appendChild(buttonsElement);

    return conversationElement;
}

// Function to make a GET request for conversation details
function load_conversation_messages(conversationId) {
    const apiUrl = `/get_conversation_data?select_conversation_id=${conversationId}`;
    const chatMessages = document.querySelector(".msg-body ul");

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Clear messages first
            chatMessages.innerHTML = ""

            // Add messages
            const messages = data.messages;
            if (data.messages && data.messages.length > 0) {
                for (const message of data.messages) {
                    let text = message.message;
                    let source = message.type === "assistant" ? "system" : "user";
                    let time = message.time;
                    
                    // Format for html
                    text = text.replace(/\n/g, '<br>');

                    // Add messages to the main chatbox area
                    addMessageToChat(text, null, source, "text", false, null, time); // Adjust message parameters
                }
            }
        })
        .catch(error => {
            console.error('Error fetching conversation details:', error);
        });
}

// Function to show the custom modal
function showModal() {
    const modal = document.getElementById('confirmationModal');
    const overlay = document.getElementById('overlay');

    modal.style.display = 'block';

    // Add a class to modal content for custom flex properties
    const modalContent = modal.querySelector('.modal-content');
    modalContent.classList.add('custom-flex-style');

    // Overlay
    modal.style.display = 'block';
    overlay.style.display = 'block';
}

// Function to hide the custom modal
function hideModal() {
    const modal = document.getElementById('confirmationModal');
    const overlay = document.getElementById('overlay');

    modal.style.display = 'none';

    // Overlay
    modal.style.display = 'none';
    overlay.style.display = 'none';
}

// Function to handle conversation deletion confirmation
function confirmDeleteConversation(conversation_id) {
    // Show the confirmation modal
    showModal();

    // Event listener for the "Yes, delete" button in the confirmation modal
    document.getElementById('confirmDelete').addEventListener('click', function() {
        // Perform deletion logic here
        // Call the function to delete the conversation using the conversation_id
        deleteConversation(conversation_id);

        // Hide the confirmation modal
        hideModal();
    });

    // Event listener for the "Cancel" button in the confirmation modal
    document.getElementById('cancelDelete').addEventListener('click', function() {
        // Hide the confirmation modal without performing deletion
        hideModal();
    });
}

function deleteConversation(conversation_id) {
    // Find the conversation element with the given conversation_id
    const conversationElement = document.querySelector(`.conversations-list .conversation-element[data-conversation_id="${conversation_id}"]`);

    // Check if the conversation element exists before trying to remove it
    if (conversationElement) {
        // Remove the conversation element
        conversationElement.remove();

        // Find first element in the list and load conversation
        const firstConversationElement = document.querySelector('.conversations-list .conversation-element');
        load_conversation_messages(firstConversationElement.dataset.conversation_id);

        // Send a post request to the server for conversation deletion
        const csrfToken = document.querySelector('input[name="csrf_token"]').value; // Get CSRF token from the form
        const apiUrl = '/delete_conversation_id';

        // Prepare the form data
        const formData = new FormData();
        formData.append('conversation_id', conversation_id);

        // Prepare the request payload
        const requestBody = {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrfToken,
            },
            body: formData,
        };

        // Send the POST request
        fetch(apiUrl, requestBody)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Handle the response data if needed
                console.log('Conversation deleted successfully.', data);
            })
            .catch(error => {
                console.error('Error deleting conversation title:', error);
            });
    }
}

function moveConversationToTop(conversation_id) {
    // Find the conversation element with the given conversation_id
    const conversationElement = document.querySelector(`.conversations-list .conversation-element[data-conversation_id="${conversation_id}"]`);

    if (conversationElement) {
        // Remove the element from its current position
        conversationElement.remove();
        
        // Prepend the element to the conversations-list, making it the first child
        const conversationsList = document.querySelector('.conversations-list');
        conversationsList.prepend(conversationElement);
    } else {
        console.error(`Conversation element with ID ${conversation_id} not found.`);
    }
}



