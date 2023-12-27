$(document).ready(function () {
    // Handle form submission
    $("#login-button").click(function () {
        
        // Get the values of email and password input fields
        var email = $("#login_email").val();
        var password = $("#login_password").val();
        // Fetch the token
        const csrfToken = document.querySelector('input[name="csrf_token"]').value; // Get CSRF token from the form

        // Send a POST request to your Flask server
        $.ajax({
            type: "POST",
            url: "/submit_login/", // Update the URL to match your Flask route
            data: {
                email: email,
                password: password,
            },
            headers: {
                "X-CSRF-Token": csrfToken // Include the CSRF token in the headers
            },
            success: function (response) {
                // Construct the redirect URL with session_id
                var redirectUrl = "/dashboard#" + response.session_id; // Assuming the server returns session_id
                window.location.href = redirectUrl;
            },
            error: function () {
                // Handle errors (e.g., display an error message)
                alert("Login failed. Please check your email and password.");
            }
        });
    });
});
