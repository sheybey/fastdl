$(function () {
  'use strict';
  $("#search").on('input', function (e) {
    var pattern = $(this).val().trim().toLowerCase();
    $('tbody tr').each(function (ignore, elem) {
      var row = $(elem);
      if (
        pattern === '' ||
        row.find('td:first-child').text().toLowerCase().indexOf(pattern) !== -1
      ) {
        row.show();
      } else {
        row.hide();
      }
    })
  });
});