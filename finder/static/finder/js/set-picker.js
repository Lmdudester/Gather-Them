(function () {
    'use strict';

    var hiddenSelect = document.getElementById('id_set_code');
    var searchInput = document.getElementById('set-search');
    var dropdown = document.getElementById('set-dropdown-listbox');
    var chipsContainer = document.querySelector('.set-chips');
    var selectionStatus = document.getElementById('set-selection-status');
    var error = document.getElementById('set-code-error');
    if (!hiddenSelect || !searchInput || !dropdown || !chipsContainer) return;

    hiddenSelect.removeAttribute('required');
    var activeIndex = -1;
    var allSets = Array.prototype.map.call(hiddenSelect.options, function (option) {
        return { value: option.value, label: option.textContent };
    });
    var recentCount = 15;

    function selectedOptions() {
        return Array.prototype.filter.call(hiddenSelect.options, function (option) {
            return option.selected;
        });
    }

    function selectedValues() {
        return new Set(selectedOptions().map(function (option) { return option.value; }));
    }

    function closeDropdown() {
        while (dropdown.firstChild) dropdown.removeChild(dropdown.firstChild);
        dropdown.classList.remove('open');
        searchInput.setAttribute('aria-expanded', 'false');
        searchInput.setAttribute('aria-activedescendant', '');
        activeIndex = -1;
    }

    function announceSelection(name) {
        var count = selectedOptions().length;
        var message = count + ' set' + (count === 1 ? '' : 's') + ' selected';
        if (name) message += ': ' + name;
        chipsContainer.setAttribute('aria-label', message);
        if (selectionStatus) selectionStatus.textContent = message;
    }

    function renderDropdown(filter) {
        var selected = selectedValues();
        var query = (filter || '').toLowerCase();
        var available = allSets.filter(function (set) { return !selected.has(set.value); });
        var matches = (query === ''
            ? available.slice(0, recentCount)
            : available.filter(function (set) {
                return set.label.toLowerCase().indexOf(query) !== -1;
            }).slice(0, 50));

        closeDropdown();
        if (!matches.length) return;

        matches.forEach(function (set, index) {
            var option = document.createElement('div');
            option.className = 'set-dropdown-item';
            option.id = 'set-option-' + index;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', 'false');
            option.dataset.value = set.value;
            option.textContent = set.label;
            dropdown.appendChild(option);
        });
        dropdown.classList.add('open');
        searchInput.setAttribute('aria-expanded', 'true');
    }

    function updateActiveItem() {
        var items = dropdown.querySelectorAll('.set-dropdown-item');
        Array.prototype.forEach.call(items, function (item, index) {
            var active = index === activeIndex;
            item.classList.toggle('active', active);
            item.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        if (activeIndex >= 0 && items[activeIndex]) {
            searchInput.setAttribute('aria-activedescendant', items[activeIndex].id);
            items[activeIndex].scrollIntoView({ block: 'nearest' });
        } else {
            searchInput.setAttribute('aria-activedescendant', '');
        }
    }

    function renderChips() {
        var selected = selectedValues();
        while (chipsContainer.firstChild) chipsContainer.removeChild(chipsContainer.firstChild);
        allSets.filter(function (set) { return selected.has(set.value); }).forEach(function (set) {
            var chip = document.createElement('span');
            chip.className = 'set-chip';
            chip.appendChild(document.createTextNode(set.label + ' '));

            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'set-chip-remove';
            remove.dataset.value = set.value;
            remove.setAttribute('aria-label', 'Remove ' + set.label);
            remove.textContent = '\u00d7';
            chip.appendChild(remove);
            chipsContainer.appendChild(chip);
        });
        announceSelection();
    }

    function findOption(value) {
        return Array.prototype.find.call(hiddenSelect.options, function (option) {
            return option.value === value;
        });
    }

    function selectSet(value) {
        var option = findOption(value);
        if (!option) return;
        option.selected = true;
        searchInput.value = '';
        closeDropdown();
        renderChips();
        if (error) {
            error.style.display = 'none';
            searchInput.removeAttribute('aria-invalid');
        }
    }

    function deselectSet(value) {
        var option = findOption(value);
        if (!option) return;
        option.selected = false;
        renderChips();
        searchInput.focus();
    }

    searchInput.addEventListener('input', function () { renderDropdown(searchInput.value); });
    searchInput.addEventListener('focus', function () { renderDropdown(searchInput.value); });
    searchInput.addEventListener('keydown', function (event) {
        var items = dropdown.querySelectorAll('.set-dropdown-item');
        var isOpen = dropdown.classList.contains('open');
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (!isOpen) {
                renderDropdown(searchInput.value);
                items = dropdown.querySelectorAll('.set-dropdown-item');
            }
            if (items.length) {
                activeIndex = Math.min(activeIndex + 1, items.length - 1);
                updateActiveItem();
            }
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (isOpen && items.length) {
                activeIndex = Math.max(activeIndex - 1, -1);
                updateActiveItem();
            }
        } else if (event.key === 'Enter' && isOpen && items.length) {
            event.preventDefault();
            selectSet(items[activeIndex >= 0 ? activeIndex : 0].dataset.value);
        } else if (event.key === 'Escape' && isOpen) {
            event.preventDefault();
            closeDropdown();
        }
    });

    dropdown.addEventListener('click', function (event) {
        var item = event.target.closest('.set-dropdown-item');
        if (item) selectSet(item.dataset.value);
    });
    chipsContainer.addEventListener('click', function (event) {
        var button = event.target.closest('.set-chip-remove');
        if (button) deselectSet(button.dataset.value);
    });
    document.addEventListener('click', function (event) {
        if (!event.target.closest('.set-picker')) closeDropdown();
    });

    renderChips();
})();
