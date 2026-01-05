class StringUtils {
    static _toWords(str) {
        return str.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
            .replace(/[_\-]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase()
            .split(' ');
    }

    static toSnakeCase(str) {
        return this._toWords(str).join('_');
    }

    static toKebabCase(str) {
        return this._toWords(str).join('-');
    }

    static toCamelCase(str) {
        const [first, ...rest] = this._toWords(str);
        return first + rest.map(this._capitalize).join('');
    }

    static toPascalCase(str) {
        return this._toWords(str)
            .map(this._capitalize)
            .join('');
    }

    static _capitalize(word) {
        return word.charAt(0).toUpperCase() + word.slice(1);
    }
}

const BootstrapAccordionUtils = {
    focus(element, block='start') {
        console.log(element, block);
        const accordion = bootstrap.Collapse.getOrCreateInstance(element, {
            toggle: false
        });


        if (element.classList.contains('show')) {
            element.scrollIntoView({behavior: 'smooth', block: block, inline: 'nearest'});
        } else {
            const handler = () => {
                element.scrollIntoView({behavior: 'smooth', block: block, inline: 'nearest'});
                element.removeEventListener('shown.bs.collapse', handler);
            };
            element.addEventListener('shown.bs.collapse', handler);
        }

        accordion.show();
    }
};
