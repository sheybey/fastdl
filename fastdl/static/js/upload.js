document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const container = document.querySelector('main');
  const input = document.querySelector('#map');
  const csrf = document.querySelector('#csrf_token');
  document.querySelector('form').addEventListener('submit', (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (input.files.length !== 1) {
      return;
    }
    const file = input.files[0];
    input.value = '';

    let cancel;

    const card = document.createElement('div');
    card.className = 'card mb-3';

    const cardBody = document.createElement('div');
    cardBody.className = 'card-body';
    card.appendChild(cardBody);

    const cardTitle = document.createElement('h5');
    cardTitle.className = 'card-title';
    cardTitle.innerText = file.name + ' ';
    cardBody.appendChild(cardTitle);

    const percent = document.createElement('small');
    percent.innerText = '0.0%';
    cardTitle.appendChild(percent);

    const status = document.createElement('p');
    cardBody.appendChild(status);

    const progressBar = document.createElement('progress');
    progressBar.className = 'w-100';
    progressBar.value = 0;
    status.append(progressBar);

    const cancelButton = document.createElement('button');
    cancelButton.className = 'btn btn-danger';
    cancelButton.type = 'button';
    cancelButton.innerText = 'Cancel';
    cardBody.appendChild(cancelButton);

    new Promise((resolve, reject) => {
      const reader = new FileReader();
      const magicNumber = "VBSP";
      if (!file.name || file.name.slice(-4).toLowerCase() !== '.bsp') {
        return reject('This does not appear to be a valid BSP.');
      }

      reader.addEventListener('load', function () {
        const array = new Uint8Array(reader.result);
        for (let i = 0; i < magicNumber.length; i += 1) {
          if (array[i] !== magicNumber.charCodeAt(i)) {
            return reject('This does not appear to be a valid BSP.');
          }
        }
        resolve(file);
      });

      reader.addEventListener('error', function () {
        reject('This does not appear to be a valid BSP.');
      });
      reader.readAsArrayBuffer(file.slice(0, magicNumber.length));
    }).then((file) => new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      cancel = () => {
        xhr.abort();
        reject('Cancelled');
      }

      const form_data = new FormData();
      form_data.set('map', file, file.name);
      form_data.set('csrf_token', csrf.value);

      cancelButton.addEventListener('click', cancel);
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
      xhr.addEventListener('error', reject);
      xhr.upload.addEventListener('progress', function (e) {
        if (e.lengthComputable) {
          progressBar.max = e.total;
          progressBar.value = e.loaded;
          percent.innerText = `${Math.round((e.loaded/e.total)*1000)/10}%`;
        } else {
          progressBar.removeAttribute('value');
        }
      });
      xhr.send(form_data);
    })).then(() => {
      status.innerText = 'Uploaded successfully';
      card.classList.add('bg-success');
    }).catch((error) => {
      status.innerText = error;
      card.classList.add('bg-danger');
    }).finally(() => {
      card.classList.add('text-white');
      cancelButton.classList.remove('btn-danger');
      cancelButton.classList.add('btn-light');
      cancelButton.innerText = 'Close';
      cancelButton.removeEventListener('click', cancel);

      const remove = () => {
        cancelButton.removeEventListener('click', remove);
        card.parentNode.removeChild(card);
      };
      cancelButton.addEventListener('click', remove);
    });

    container.appendChild(card);
  });
});
