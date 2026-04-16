const initializeModalComponent = () => {
    
    document.querySelectorAll('[data-modal-trigger]').forEach(trigger => {
        trigger.addEventListener('click', () => {
            
            const modalName = trigger.getAttribute('data-modal-trigger');
            const targetModal = document.querySelector(`[data-modal=${ modalName }]`);
            const targetModalWrapper = targetModal.closest('.modal-wrapper');

            targetModalWrapper.style.display = 'grid'
            targetModal.style.display = 'flex';

        });
    });

    document.querySelectorAll('[data-modal-close]').forEach(trigger => {
        trigger.addEventListener('click', () => {

            const targetModal = trigger.closest('.modal');
            const targetModalWrapper = targetModal.closest('.modal-wrapper');

            targetModal.style.display = 'none';
            targetModalWrapper.style.display = 'none';

        })
    });

};

export default initializeModalComponent;
