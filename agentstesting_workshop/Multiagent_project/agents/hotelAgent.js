import { mockData } from '../utils/data.js';

export class HotelAgent {
    constructor() {
        this.name = "Hotel Agent";
    }

    async process(context) {
        // Simulate thinking delay
        await new Promise(resolve => setTimeout(resolve, 1800));
        
        const { destination, days } = context;
        
        if (!destination) {
            return { error: "I need a destination to find hotels." };
        }

        let hotels = mockData.hotels.filter(h => h.city.toLowerCase() === destination.toLowerCase());

        if (hotels.length === 0) {
            // Fallback: Just take first two
            hotels = mockData.hotels.slice(0, 2);
        }

        // Calculate total price based on days (nights = days - 1)
        const nights = Math.max(1, days - 1);
        
        const results = hotels.map(h => ({
            ...h,
            totalPrice: h.pricePerNight * nights,
            nights
        }));

        return {
            status: 'success',
            data: results,
            message: `Found ${results.length} hotels in ${destination} for ${nights} nights.`
        };
    }

    renderCard(data) {
        if (!data || data.length === 0) return '';
        
        let html = `
        <div class="itinerary-card">
            <div class="card-header">
                <span>🏨</span> Hotel Accommodations
            </div>
            <div class="card-body">
        `;

        data.forEach(hotel => {
            const stars = '⭐'.repeat(hotel.rating);
            html += `
                <div class="item-row">
                    <div>
                        <strong>${hotel.name}</strong> ${stars}<br>
                        <small>${hotel.amenities.join(' • ')}</small>
                    </div>
                    <div class="price">
                        ₹${hotel.totalPrice.toLocaleString()} <br>
                        <small style="color:var(--text-secondary)">for ${hotel.nights} nights</small>
                    </div>
                </div>
            `;
        });

        html += `</div></div>`;
        return html;
    }
}
