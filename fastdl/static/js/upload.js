$(function () {
  'use strict';

  $('form').on('submit', function (event) {
    var input = $('#map')[0];
    var progress_bar;
    var cancel;
    var card;
    var percent;
    var file;

    event.preventDefault();
    event.stopPropagation();

    if (input.files.length !== 1) {
      return;
    }
    file = input.files[0];

    input.value = "";

    progress_bar = document.createElement('progress');
    progress_bar.classList.add('w-100');
    progress_bar.value = 0;
    percent = $('<small>0.0%</small>');
    card = $('<div class="card mb-3"><div class="card-body"><h5 class="card-title"><span></span></h5><p></p><button class="btn btn-danger">Cancel</button></div></div>');
    card.find('h5').append(percent).find('span').text(file.name + ' ');
    card.find('p').append(progress_bar);
    cancel = card.find('button');

    new Promise(function (resolve, reject) {
      var reader = new FileReader();
      var magic_number = "VBSP";
      if (!file.name || file.name.slice(-4).toLowerCase() !== '.bsp') {
        return reject('This does not appear to be a valid BSP.');
      }
      reader.addEventListener('load', function () {
        var array = new Uint8Array(reader.result);
        var xhr = new XMLHttpRequest();
        var form_data = new FormData();
        var i;
        var l;
        for (i = 0, l = magic_number.length; i < l; i += 1) {
          if (array[i] !== magic_number.charCodeAt(i)) {
            return reject('This does not appear to be a valid BSP.');
          }
        }

        cancel.on('click', function () {
          xhr.abort();
          reject('Cancelled');
        });

        form_data.set('map', file, file.name);
        form_data.set('csrf_token', $('#csrf_token').val());

        xhr.responseType = 'json';
        xhr.open('POST', window.location.href);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.addEventListener('load', function () {
          if (xhr.response.success) {
            resolve(xhr.response.name);
          } else {
            reject(xhr.response.error);
          }
        });
        xhr.addEventListener('error', function (e) {
          reject(e);
        });
        xhr.upload.addEventListener('progress', function (e) {
          if (e.lengthComputable) {
            progress_bar.max = e.total;
            progress_bar.value = e.loaded;
            percent.text(
              String(Math.round((e.loaded / e.total) * 1000) / 10)
              + '%'
            );
          } else {
            progress_bar.removeAttribute('value');
          }
        });
        xhr.send(form_data);
      });
      reader.addEventListener('error', function () {
        reject('This does not appear to be a valid BSP.');
      });
      reader.readAsArrayBuffer(file.slice(0, magic_number.length));
    }).then(function (map_name) {
      card.find('p').text('Uploaded successfully');
      card.addClass('bg-success');
    }).catch(function (error) {
      card.find('p').text(error);
      card.addClass('bg-danger');
    }).finally(function () {
      card.addClass('text-white');
      percent.remove();
      cancel.removeClass('btn-danger');
      cancel.addClass('btn-light');
      cancel.text('Close');
      cancel.off();
      cancel.on('click', function () {
        cancel.off();
        card.remove();
      });
    });

    $('main').append(card);
  });
});
