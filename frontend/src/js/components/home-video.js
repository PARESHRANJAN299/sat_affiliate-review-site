(function () {
  'use strict';
  // The hero video is decoration: skip it for people who asked for less motion or are saving data.
  var video = document.querySelector('.home-hero-video');
  if (!video) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var saveData = navigator.connection && navigator.connection.saveData;
  if (reduce || saveData) {
    video.removeAttribute('autoplay');
    video.pause();
    video.style.display = 'none';
  }
})();
