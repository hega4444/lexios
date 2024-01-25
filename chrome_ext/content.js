// content.js

function changeColors() {
    // Your code to change the background color goes here
    document.body.style.backgroundColor = '#C4660E60'; // Change this color to your desired background color
  
    // Example: Change the background color of elements with class .eh5oYe
    var eh5oYeElements = document.querySelectorAll('.eh5oYe');
    eh5oYeElements.forEach(function (eh5oYeElement) {
      eh5oYeElement.style.backgroundColor = '#C4660E60'; // Change this color to your desired background color
    });
  
    // Example: Change the background color of elements with class .JE11kf
    var je11kfElements = document.querySelectorAll('.JE11kf');
    je11kfElements.forEach(function (je11kfElement) {
      je11kfElement.style.backgroundColor = '#C4660E90'; // Change this color to your desired background color
    });
  
    // Example: Change the background color of elements with class .gb_od
    var je11kfElements = document.querySelectorAll('.gb_od');
    je11kfElements.forEach(function (je11kfElement) {
        je11kfElement.style.backgroundColor = '#C4660E30'; // Change this color to your desired background color
    });

    // Example: Change the background color of elements with class .gb_od
    var je11kfElements = document.querySelectorAll('.s4ZaLd ');
    je11kfElements.forEach(function (je11kfElement) {
        je11kfElement.style.backgroundColor = '#C4660E50'; // Change this color to your desired background color
    });
        

}
  
    // Call the function when the content script is injected
    changeColors();

    // Call the function again after 50 milliseconds
    setTimeout(function() {
    changeColors();
    }, 50);

  // Call the function on DOMContentLoaded event
  document.addEventListener('DOMContentLoaded', changeColors);
  
  // Call the function on user interactions (e.g., click, scroll)
  document.addEventListener('click', changeColors);
  document.addEventListener('scroll', changeColors);
  // Add more event listeners as needed

  