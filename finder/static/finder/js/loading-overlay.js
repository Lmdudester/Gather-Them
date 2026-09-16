(function () {
    'use strict';

    window.setupLoadingOverlay = function (form, validate) {
        if (!form) return;
        var overlay = document.getElementById('loading-overlay');
        var cancelButton = document.getElementById('loading-cancel');
        var flavor = document.getElementById('loading-flavor');
        if (!overlay || !cancelButton || !flavor) return;

        var generation = 0;
        var trigger = null;
        var fallbackTimer = null;
        var defaultCopy = flavor.textContent;

        function setActive(active) {
            overlay.classList.toggle('active', active);
            overlay.setAttribute('aria-hidden', active ? 'false' : 'true');
            cancelButton.hidden = !active;
        }

        function focusableElements() {
            return Array.prototype.filter.call(
                overlay.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'),
                function (element) {
                    if (element.hidden) return false;
                    var style = window.getComputedStyle(element);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                }
            );
        }

        function hideOverlay(restoreFocus) {
            generation++;
            if (fallbackTimer) window.clearTimeout(fallbackTimer);
            setActive(false);
            flavor.textContent = defaultCopy;
            if (restoreFocus && trigger && document.contains(trigger)) trigger.focus();
        }

        document.addEventListener('keydown', function (event) {
            if (!overlay.classList.contains('active')) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                cancelButton.click();
                return;
            }
            if (event.key !== 'Tab') return;
            var elements = focusableElements();
            if (!elements.length) return;
            var first = elements[0];
            var last = elements[elements.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        });

        cancelButton.addEventListener('click', function () {
            hideOverlay(true);
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            if (validate && !validate()) return;

            trigger = event.submitter || form.querySelector('button[type="submit"]') || document.activeElement;
            var currentGeneration = ++generation;
            setActive(true);
            // Cancel is visible before focus moves into the dialog.
            cancelButton.focus();

            var minimumDelay = new Promise(function (resolve) {
                window.setTimeout(resolve, 400);
            });
            var flavorDone = fetch(overlay.dataset.flavorUrl || '')
                .then(function (response) {
                    if (!response.ok) throw new Error('flavor request failed');
                    return response.json();
                })
                .then(function (data) {
                    flavor.textContent = '\u201c' + (data.flavorText || '') + '\u201d';
                    var source = document.createElement('span');
                    source.className = 'flavor-source';
                    source.textContent = '\u2014 ' + (data.name || '');
                    flavor.appendChild(source);
                })
                .catch(function () {});

            function submitIfCurrent() {
                if (currentGeneration !== generation) return;
                generation++;
                HTMLFormElement.prototype.submit.call(form);
            }

            Promise.all([flavorDone, minimumDelay]).then(submitIfCurrent);
            fallbackTimer = window.setTimeout(submitIfCurrent, 4000);
        });

        window.addEventListener('pageshow', function (event) {
            if (event.persisted) hideOverlay(true);
        });
    };
})();
