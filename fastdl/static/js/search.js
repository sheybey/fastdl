document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  document.querySelector('#search').addEventListener('input', (event) => {
    const pattern = event.target.value.trim().toLowerCase();
    document.querySelectorAll('tbody tr').forEach((row) => {
      const display = row.querySelector('.server-display');
      const description = row.querySelector('.server-description');
      if (
        pattern === '' ||
        display.innerText.toLowerCase().indexOf(pattern) !== -1 ||
        description.innerText.toLowerCase().indexOf(pattern) !== -1
      ) {
        row.style.visibility = '';
      } else {
        row.style.visibility = 'collapse';
      }
    });
  });
});