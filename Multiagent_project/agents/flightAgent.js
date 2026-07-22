import { mockData } from '../utils/data.js';

export class FlightAgent {
    constructor() {
        this.name = "Flight Agent";
    }

    async process(context) {
        // Simulate thinking delay
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        const { origin, destination, people } = context;
        
        if (!destination) {
            return { error: "I need to know your destination to find flights." };
        }

        let flights = mockData.flights.filter(f => 
            f.to.toLowerCase() === destination.toLowerCase() && 
            (f.from.toLowerCase() === (origin?.toLowerCase() || '') || f.from === 'Any')
        );

        if (flights.length === 0) {
            // Fallback: just return a generic flight if exact match not found
            flights = mockData.flights.slice(0, 2);
        }

        // Calculate total price based on people
        const results = flights.map(f => ({
            ...f,
            totalPrice: f.price * people,
            people
        }));

        return {
            status: 'success',
            data: results,
            message: `Found ${results.length} flight options to ${destination}.`
        };
    }

    renderCard(data) {
        if (!data || data.length === 0) return '';
        
        let html = `
        <div class="itinerary-card">
            <div class="card-header">
                <span>✈️</span> Flight Options
            </div>
            <div class="card-body">
        `;

        data.forEach(flight => {
            html += `
                <div class="item-row">
                    <div>
                        <strong>${flight.airline}</strong><br>
                        <small>${flight.from} → ${flight.to} (${flight.duration}, ${flight.stops} stops)</small>
                    </div>
                    <div class="price">
                        ₹${flight.totalPrice.toLocaleString()} <br>
                        <small style="color:var(--text-secondary)">for ${flight.people} pax</small>
                    </div>
                </div>
            `;
        });

        html += `</div></div>`;
        return html;
    }
}
