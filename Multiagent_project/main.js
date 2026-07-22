document.addEventListener('DOMContentLoaded', () => {
    const tabTravel = document.getElementById('tab-travel');
    const tabSupport = document.getElementById('tab-support');
    const viewTravel = document.getElementById('travel-view');
    const viewSupport = document.getElementById('support-view');

    tabTravel.addEventListener('click', () => {
        tabTravel.classList.add('active');
        tabSupport.classList.remove('active');
        viewTravel.classList.add('active');
        viewSupport.classList.remove('active');
    });

    tabSupport.addEventListener('click', () => {
        tabSupport.classList.add('active');
        tabTravel.classList.remove('active');
        viewSupport.classList.add('active');
        viewTravel.classList.remove('active');
    });
});
