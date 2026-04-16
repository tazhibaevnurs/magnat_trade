export const getTheme = (callback) => {

    const savedTheme = localStorage.getItem('theme');
    const preferredTheme = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const computedTheme =
    (!savedTheme)
        ? (!preferredTheme ? 'light' : 'dark')
        : savedTheme;

    callback(computedTheme);

};

export const setTheme = (theme) => localStorage.setItem('theme', theme);
