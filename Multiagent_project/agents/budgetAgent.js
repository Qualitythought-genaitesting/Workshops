export class BudgetAgent {
    constructor() {
        this.name = "Budget Agent";
    }

    async process(context, flightData, hotelData) {
        // Simulate thinking delay
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const { people, days, budget } = context;

        // Default costs if data not provided
        let flightCost = 0;
        let hotelCost = 0;

        if (flightData && flightData.length > 0) {
            flightCost = flightData[0].totalPrice; // Take cheapest/first option
        }
        
        if (hotelData && hotelData.length > 0) {
            hotelCost = hotelData[0].totalPrice;
        }

        // Estimates
        const mealsCostPerDay = 3000;
        const activitiesCostPerDay = 2500;
        const transportCostPerDay = 1000;

        const totalMeals = mealsCostPerDay * people * days;
        const totalActivities = activitiesCostPerDay * people * days;
        const totalTransport = transportCostPerDay * people * days;

        const totalCost = flightCost + hotelCost + totalMeals + totalActivities + totalTransport;

        let status = 'success';
        let message = `Total estimated cost is ₹${totalCost.toLocaleString()}.`;

        if (budget && totalCost > budget) {
            status = 'warning';
            message += ` This is over your budget of ₹${budget.toLocaleString()}.`;
        } else if (budget) {
            message += ` This is within your budget of ₹${budget.toLocaleString()}.`;
        }

        const data = {
            flightCost,
            hotelCost,
            meals: totalMeals,
            activities: totalActivities,
            transport: totalTransport,
            total: totalCost,
            perPerson: Math.round(totalCost / people),
            budgetContext: budget ? { target: budget, over: totalCost > budget } : null
        };

        return { status, data, message };
    }

    renderCard(data) {
        if (!data) return '';
        
        let html = `
        <div class="itinerary-card">
            <div class="card-header">
                <span>💰</span> Budget Breakdown
            </div>
            <div class="card-body">
                <div class="item-row">
                    <span>Flights</span>
                    <span>₹${data.flightCost.toLocaleString()}</span>
                </div>
                <div class="item-row">
                    <span>Hotel</span>
                    <span>₹${data.hotelCost.toLocaleString()}</span>
                </div>
                <div class="item-row">
                    <span>Meals Estimate</span>
                    <span>₹${data.meals.toLocaleString()}</span>
                </div>
                <div class="item-row">
                    <span>Activities Estimate</span>
                    <span>₹${data.activities.toLocaleString()}</span>
                </div>
                <div class="item-row">
                    <span>Local Transport</span>
                    <span>₹${data.transport.toLocaleString()}</span>
                </div>
                <div class="item-row" style="margin-top: 8px; border-top: 1px solid var(--glass-border); padding-top: 12px; font-weight: bold; font-size: 16px;">
                    <span>Total Estimated Cost</span>
                    <span class="price" style="${data.budgetContext && data.budgetContext.over ? 'color: #ef4444;' : ''}">
                        ₹${data.total.toLocaleString()}
                    </span>
                </div>
                <div style="text-align: right; font-size: 13px; color: var(--text-secondary); margin-top: 4px;">
                    ₹${data.perPerson.toLocaleString()} per person
                </div>
            </div>
        </div>
        `;
        return html;
    }
}
