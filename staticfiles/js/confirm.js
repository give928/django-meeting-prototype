const confirmModal = (() => {
    const queue = [];
    let isShowing = false;

    const modalElement = document.getElementById('modalContainer');
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    const titleElement = modalElement.querySelector('.modal-title');
    const bodyElement = modalElement.querySelector('.modal-body');
    const okButton = modalElement.querySelector('.btn-ok');
    const cancelButton = modalElement.querySelector('.btn-cancel');

    const processQueue = () => {
        if (isShowing || queue.length === 0) {
            return;
        }
        const {options, resolve} = queue.shift();
        showModal(options, resolve);
    };

    const clearFocus = () => {
        modalElement.querySelectorAll('button, [tabindex]')
            .forEach(el => el.blur());
        document.activeElement?.blur();
        try {
            document.body.focus();
        } catch (e) {
        }
    };

    const showModal = (options, resolve) => {
        isShowing = true;

        titleElement.textContent = options.title || '확인';
        bodyElement.innerHTML = options.message || '';
        okButton.textContent = options.okText || '확인';
        cancelButton.textContent = options.cancelText || '취소';
        if (options.okClass) {
            okButton.className = `btn ${options.okClass} btn-ok`;
        } else {
            okButton.className = 'btn btn-primary btn-ok';
        }

        const handleOk = () => {
            cleanup();
            resolve(true);
            modal.hide();
        };

        const handleCancel = () => {
            cleanup();
            resolve(false);
            modal.hide();
        };

        const handleHide = () => {
            clearFocus();
        };

        const handleHidden = () => {
            clearFocus();
            cleanup();
            resolve(false);
        };

        const handleShown = () => {
            requestAnimationFrame(() => {
                try {
                    okButton.focus();
                    if (document.activeElement !== okButton) {
                        document.body.focus();
                    }
                } catch (e) {
                    document.body.focus();
                }
            });
        };

        okButton.addEventListener('click', handleOk);
        cancelButton.addEventListener('click', handleCancel);
        modalElement.addEventListener('hide.bs.modal', handleHide, {once: true});
        modalElement.addEventListener('hidden.bs.modal', handleHidden, {once: true});
        modalElement.addEventListener('shown.bs.modal', handleShown, {once: true});

        const cleanup = () => {
            okButton.removeEventListener('click', handleOk);
            cancelButton.removeEventListener('click', handleCancel);
            isShowing = false;
            processQueue();
        };

        modal.show();
    };

    return {
        show(options = {}) {
            return new Promise((resolve) => {
                queue.push({options, resolve});
                processQueue();
            });
        }
    };
})();