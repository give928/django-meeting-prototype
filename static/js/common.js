const FormValidators = {
    validate(form) {
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            const invalidElement = form.querySelector('input.form-control:invalid');
            if (invalidElement !== null) {
                invalidElement.focus();
            }
            return false;
        }

        const formValidator = FormValidators[form.id];
        if (formValidator) {
            const validate = FormValidators[form.id].validate;
            if (typeof validate === 'function' && !validate(form)) {
                return false;
            }
        }

        return true;
    },
    add(form, validate) {
        this[form.id] = {form: form, validate: validate};
    }
};

document.addEventListener('DOMContentLoaded', function () {
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', event => {
            event.preventDefault();
            event.stopPropagation();

            if (!FormValidators.validate(form)) {
                return;
            }

            form.classList.add('was-validated');

            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 저장 중...';

            form.submit();
        }, false);
    });

    const signOut = () => window.location.href = '/sign-out/'
    const signOutButtons = document.querySelectorAll('.btn-sign-out');
    signOutButtons.forEach(button => {
        button.addEventListener('click', signOut);
        button.addEventListener('keypress', signOut);
    });
});
