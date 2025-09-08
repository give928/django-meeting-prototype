(function () {
    'use strict'

    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                const elements = document.querySelectorAll('input.form-control:invalid');
                if (elements !== null && elements.length > 0) {
                    elements[0].focus();
                }
            }

            form.classList.add('was-validated');
        }, false);
    });

    const signOut = () => window.location.href = '/sign-out/'
    const signOutButtons = document.querySelectorAll('.btn-sign-out');
    signOutButtons.forEach(button => {
        button.addEventListener('click', signOut);
        button.addEventListener('keypress', signOut);
    });
})();