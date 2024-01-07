document.addEventListener('DOMContentLoaded', function () {
  var calendarAccess = document.getElementById('calendar-access');

  if (calendarAccess) {
    calendarAccess.addEventListener('click', function (event) {
      event.preventDefault();

      // Open the Google Calendar URL in a new tab outside the fetch block
      window.open('https://calendar.google.com/', '_blank');
    });
  } else {
    console.error("Element with id 'calendar-access' not found.");
  }
});
