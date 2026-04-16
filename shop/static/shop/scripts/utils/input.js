export const handlePasswordToggle = (input, callback) => {

    if (!input) return;

    callback(input.type === "password" ? "text" : "password");

};

export const handleFormInputsChecking = (formInputs, callback) => {

    if (formInputs.length <= 0) return;

    for (const formInput of formInputs) {

        if (!formInput.required)
            continue;

        if (!formInput.value || formInput.value.trim() === '') {
            callback(false);
            return;
        }

    }

    callback(true);
    
};

