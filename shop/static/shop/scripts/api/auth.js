const getCSRFToken = () => {
    
    const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
   
    if (tokenInput) return tokenInput.value;

    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];

    return cookieValue || '';

};

export const loginUser = async (data) => {

    try {

        const response = await fetch('/api/login/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok)
            throw new Error(result.err || 'Не удалось выполнить вход.');
        
        return result;

    } catch (err) {

        console.error('api/auth script loginUser function error: ', err);
        throw err;

    }

};

export const createUser = async (data) => {

    try {

        const response = await fetch('/api/register/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok)
            throw new Error(result.err || 'Не удалось создать аккаунт.');
        
        return result;

    } catch (err) {

        console.error('api/auth script createUser function error: ', err);
        throw err;

    }

};

