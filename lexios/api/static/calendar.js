document.addEventListener('DOMContentLoaded', function () {
  var calendarAccess = document.getElementById('calendar-access');

  if (calendarAccess) {
    calendarAccess.addEventListener('click', function (event) {
      event.preventDefault();

      // Get the CSRF token value from the hidden input
      var csrfToken = document.querySelector('input[name="csrf_token"]').value;

      // Make a POST request to the server
      fetch('/open_calendar', {
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

      // Open the Google Calendar URL in a new tab outside the fetch block
      window.open('https://calendar.google.com/', '_blank');
    });
  } else {
    console.error("Element with id 'calendar-access' not found.");
  }
});
