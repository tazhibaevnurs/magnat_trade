document.addEventListener('DOMContentLoaded', function() {
    // TOP PRODUCTS CHART
    const ctx = document.getElementById('topProductsChart');
    if (ctx) {
        const topProductsChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: window.topProductsLabels || [],
                datasets: [{
                    label: 'Units Sold',
                    data: window.topProductsData || [],
                    backgroundColor: 'rgba(196, 33, 87, 0.6)',
                    borderColor: 'rgba(196, 33, 87, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // BOTTOM PRODUCTS CHART
    const bottomCtx = document.getElementById('bottomProductsChart');
    if (bottomCtx) {
        new Chart(bottomCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: window.bottomProductsLabels || [],
                datasets: [{
                    label: 'Units Sold',
                    data: window.bottomProductsData || [],
                    backgroundColor: 'rgba(196, 33, 87, 0.6)',
                    borderColor: 'rgba(196, 33, 87, 1)',
                    borderWidth: 2,
                    fill: false
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
});