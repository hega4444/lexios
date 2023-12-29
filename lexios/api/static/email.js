document.addEventListener('DOMContentLoaded', function () {
  var gmailAccess = document.getElementById('email-access');

  if (gmailAccess) {
    gmailAccess.addEventListener('click', function (event) {
      event.preventDefault();

      // Get the CSRF token value from the hidden input
      var csrfToken = document.querySelector('input[name="csrf_token"]').value;

      // Make a POST request to the server
      fetch('/open_gmail', {
        method: 'POST',
        headers: {
          'X-CSRF-TOKEN': csrfToken,
        },
      })
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to notify the server');
        }
        return response.json(); // Parse the response as JSON if needed
      })
      .then(data => {
        // Optionally, you can process the response data here
      })
      .catch(error => {
        console.error('Error:', error.message);
      });

      // Open the Gmail URL in a new tab outside the fetch block
      window.open('https://mail.google.com/', '_blank');
    });
  } else {
    console.error("Element with id 'gmail-access' not found.");
  }
});
