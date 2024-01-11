document.addEventListener('DOMContentLoaded', function () {
  var gmailAccess = document.getElementById('email-access');

  if (gmailAccess) {
    gmailAccess.addEventListener('click', function (event) {
      event.preventDefault();

      // Open the Gmail URL in a new tab outside the fetch block
      window.open('https://mail.google.com/', '_blank');
    });
  } else {
    console.error("Element with id 'gmail-access' not found.");
  }
});
