const tree = function (options) {
    this.options = Object.assign({
            readonly: true,
            wrapperElement: null,
            toggleButtonSelector: 'a.tree-toggle-button',
            expandButtonSelector: 'a#tree-expand-button',
            collapseButtonSelector: 'a#tree-collapse-button',
            internalCheckboxSelector: 'input.check-internal[type="checkbox"]',
            leafCheckboxSelector: 'input.check-leaf[type="checkbox"]',
            parentAttribute: 'data-parent-id',
            checkValidator: (count) => true
        },
        options);

    this.initialize = () => {
        if (this.options.wrapperElement == null) {
            return;
        }

        this.initializeTree();

        this.initializeCheckbox();

        this.initializeParentCheckbox();
    };

    this.initializeTree = () => {
        this.options.wrapperElement.querySelectorAll(this.options.toggleButtonSelector)
            .forEach(button => {
                button.addEventListener('click', (event) => {
                    event.preventDefault();

                    this.toggle(event.target);
                });
                button.addEventListener('keypress', (event) => {
                    event.preventDefault();

                    this.toggle(event.target);
                });
            });

        this.options.wrapperElement.querySelectorAll(this.options.expandButtonSelector)
            .forEach(button => {
                button.addEventListener('click', (event) => {
                    event.preventDefault();

                    this.options.wrapperElement.querySelectorAll(this.options.toggleButtonSelector)
                        .forEach(toggleButton => {
                            console.log(toggleButton.innerText);
                            if (toggleButton.innerText === '+') {
                                this.toggle(toggleButton);
                            }
                        });
                });
            });

        this.options.wrapperElement.querySelectorAll(this.options.collapseButtonSelector)
            .forEach(button => {
                button.addEventListener('click', (event) => {
                    event.preventDefault();

                    Array.from(this.options.wrapperElement.querySelectorAll(this.options.toggleButtonSelector))
                        .reverse()
                        .forEach(toggleButton => {
                            if (toggleButton.innerText !== '+') {
                                this.toggle(toggleButton);
                            }
                        });
                });
            });
    };

    this.initializeCheckbox = () => {
        this.options.wrapperElement.querySelectorAll(this.options.internalCheckboxSelector)
            .forEach(checkbox => {
                if (this.options.readonly) {
                    this.readonlyCheckbox(checkbox);
                } else {
                    checkbox.addEventListener('change', (event) => {
                        if (typeof this.options.checkValidator === 'function') {
                            const checkedCount = this.getCheckedCount();
                            const innerChecked = event.target.parentElement.querySelectorAll(this.options.leafCheckboxSelector + ':checked');
                            const inner = event.target.parentElement.querySelectorAll(this.options.leafCheckboxSelector);
                            if (!this.options.checkValidator(checkedCount - innerChecked.length + inner.length)) {
                                event.target.checked = !event.target.checked;
                            }
                        }
                        this.checkChildren(event.target.parentElement, event.target.checked);
                        this.updateParent(event.target.parentElement, true);
                    });
                }
            });

        this.options.wrapperElement.querySelectorAll(this.options.leafCheckboxSelector)
            .forEach(checkbox => {
                if (this.options.readonly) {
                    this.readonlyCheckbox(checkbox);
                } else {
                    checkbox.addEventListener('change', (event) => {
                        if (typeof this.options.checkValidator === 'function') {
                            const checked = this.options.wrapperElement.querySelectorAll(this.options.leafCheckboxSelector + ':checked');
                            if (!this.options.checkValidator(checked.length)) {
                                event.target.checked = !event.target.checked;
                            }
                        }
                        this.updateParentFromChild(event.target);
                    });
                }
            });
    };

    this.readonlyCheckbox = (checkbox) => {
        checkbox.setAttribute('readonly', true);
        checkbox.addEventListener('click', (event) => {
            event.target.checked = !event.target.checked;
            return false;
        });
    };

    this.initializeParentCheckbox = () => {
        Array.from(this.options.wrapperElement.querySelectorAll(this.options.internalCheckboxSelector))
            .reverse()
            .forEach(checkbox => {
                const section = checkbox.parentElement;
                this.updateParent(section, false);
                const count = section.querySelector('span.count');
                if (count !== null) {
                    count.innerText = section.querySelectorAll(this.options.leafCheckboxSelector).length;
                }
                const checkedCount = section.querySelector('span.checked_count');
                if (checkedCount === null) {
                    return;
                }
                if (checkedCount.innerText > 0 && section.querySelector(':scope > ul').classList.contains('d-none')) {
                    this.toggle(section.querySelector(':scope > ' + this.options.toggleButtonSelector));
                }
            });
    };

    this.toggle = (element) => {
        element.innerText = element.innerText === '+' ? '-' : '+';

        element.parentElement.querySelectorAll(':scope > ul')
            .forEach(child => {
                child.classList.toggle('d-none');
            });
    };

    this.findParent = (parentId) => {
        const checkbox = document.querySelector(this.options.internalCheckboxSelector + '[value="' + parentId + '"]');
        if (checkbox === null) {
            return null;
        }
        return checkbox.parentElement;
    };

    this.updateParentFromChild = (checkbox) => {
        const parentId = checkbox.getAttribute(this.options.parentAttribute);
        if (typeof parentId === 'undefined' || parentId === null || parentId === '' || parentId === 'None') {
            return;
        }
        const section = this.findParent(parentId);
        this.updateParent(section, true);
    };

    this.updateParent = (section, recursion) => {
        const checkbox = section.querySelector(this.options.internalCheckboxSelector);
        if (checkbox === null) {
            return;
        }
        this.checkParent(checkbox);

        this.updateCheckedCount(section);

        if (!recursion) {
            return;
        }
        const parentId = checkbox.getAttribute(this.options.parentAttribute);
        if (typeof parentId === 'undefined' || parentId === null || parentId === '' || parentId === 'None') {
            return;
        }
        this.updateParent(this.findParent(parentId), recursion);
    };

    this.checkParent = (checkbox) => {
        const checkboxes = checkbox.parentElement.querySelectorAll(':scope > ul > li > input[type="checkbox"]');
        let checkedCount = 0;
        let indeterminateCount = 0;
        let uncheckedCount = 0;
        for (let i = 0; i < checkboxes.length; i++) {
            if (checkboxes[i].checked) {
                checkedCount++;
                continue;
            }
            if (checkboxes[i].indeterminate) {
                indeterminateCount++;
                continue;
            }
            uncheckedCount++;
        }
        if (checkedCount === 0 && indeterminateCount === 0) {
            this.check(checkbox, false, false);
        } else if (indeterminateCount === 0 && uncheckedCount === 0) {
            this.check(checkbox, true, false);
        } else {
            this.check(checkbox, false, true);
        }
    };

    this.check = (checkbox, checked, indeterminate) => {
        checkbox.checked = checked;
        checkbox.indeterminate = indeterminate;
    };

    this.checkChildren = (section, checked) => {
        const _self = this;
        section.querySelectorAll('input[type="checkbox"]')
            .forEach(checkbox => {
                _self.check(checkbox, checked, false);
            });
    }

    this.updateCheckedCount = (section) => {
        const checkedCount = section.querySelector('span.checked_count');
        if (checkedCount === null) {
            return;
        }
        section.querySelector('span.checked_count').innerText = section.querySelectorAll(this.options.leafCheckboxSelector + ':checked').length;
    };

    this.getCheckedCount = () => {
        return this.options.wrapperElement.querySelectorAll(this.options.leafCheckboxSelector + ':checked').length;
    };

    this.getCheckedLeaf = () => {
        return this.options.wrapperElement.querySelectorAll(this.options.leafCheckboxSelector + ':checked');
    };

    this.initialize();
};