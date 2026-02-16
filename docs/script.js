// LeanVibes - Progressive enhancement JS

(function () {
  'use strict';

  // 1. Sticky nav background on scroll
  var nav = document.getElementById('nav');
  if (nav) {
    window.addEventListener('scroll', function () {
      nav.classList.toggle('scrolled', window.scrollY > 50);
    }, { passive: true });
  }

  // 2. Mobile nav toggle
  var toggle = document.querySelector('.nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var isOpen = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', isOpen);
    });

    // Close on link click
    links.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });

    // Close on outside click
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // 3. Copy-to-clipboard for code blocks
  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var codeBlock = btn.closest('.code-block');
      var code = codeBlock.querySelector('code');
      if (!code) return;

      var text = code.textContent.replace(/^\$\s*/gm, '').trim();

      navigator.clipboard.writeText(text).then(function () {
        var original = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(function () {
          btn.textContent = original;
        }, 2000);
      });
    });
  });
})();
