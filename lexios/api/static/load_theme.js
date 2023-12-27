// Create a global object to store variables
const globalSettings = {
    textColor: '#000000',   // Default text color is black
    backgroundColor: '#FFFFFF'  // Default background color is white
  };
  
  // Function to update styles based on global settings
  function updateStyles() {
    const textElements = document.querySelectorAll('.text-element');
    const backgroundElements = document.querySelectorAll('.background-element');
  
    // Update text color
    textElements.forEach(element => {
        element.style.setProperty('color', globalSettings.textColor, 'important');
    });

    // Update background color
    backgroundElements.forEach(element => {
        element.style.backgroundColor = `rgba(${hexToRgb(globalSettings.backgroundColor)}, 0.78)`;
    });

    const navLink = document.querySelectorAll('.navbar-light .navbar-nav .nav-link');
    if (navLink) {
        // Update text color
        navLink.forEach(element => {
            element.style.color = `rgba(${hexToRgb(globalSettings.textColor)}, 0.8)`; // Adjust the alpha value as needed
        });
    }

    // Update text color for elements with class 'add-apoint'
    const addApointElements = document.querySelectorAll('.add-apoint a');
    addApointElements.forEach(element => {
    element.style.setProperty('color', globalSettings.textColor, 'important');
    });
}
  
  // Function to fetch theme data and update global settings
  function fetchThemeData() {
    // Make a GET request to get theme colors
    fetch('/get_theme_user_colors')
      .then(response => response.json())
      .then(themeData => {
        // Update global settings with theme data
        globalSettings.textColor = themeData.textColor;
        globalSettings.backgroundColor = themeData.backgroundColor;
  
        // Call the function to apply the styles
        updateStyles();
      })
      .catch(error => console.error('Error fetching theme data:', error));
  }
  
  // Call the function to fetch theme data when the page loads
  window.addEventListener('load', fetchThemeData);
  
  // Example of how to use the global variables for changes
  // globalSettings.textColor = '#FF0000'; // Set new text color
  // globalSettings.backgroundColor = '#00FF00'; // Set new background color
  
  // Call the function to apply the styles
  // updateStyles();
  
  function hexToRgb(hex) {
    // Remove the hash if it exists
    hex = hex.replace(/^#/, '');
  
    // Parse the hex value into RGB components
    const bigint = parseInt(hex, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
  
    // Return the RGB values as a string
    return `${r}, ${g}, ${b}`;
  }