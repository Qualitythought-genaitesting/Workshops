import { mockData } from '../utils/data.js';

export class DayPlanAgent {
    constructor() {
        this.name = "Day Planner";
    }

    async process(context) {
        // Simulate thinking delay
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        const { destination, days } = context;
        
        if (!destination) {
            return { error: "I need a destination to plan activities." };
        }

        let attractions = mockData.attractions[destination] || mockData.attractions['Paris']; // fallback
        
        const itinerary = [];
        let attractionIndex = 0;

        for (let i = 1; i <= days; i++) {
            const dayAttractions = [];
            // Pick 2 attractions per day
            for (let j = 0; j < 2; j++) {
                if (attractionIndex < attractions.length) {
                    dayAttractions.push(attractions[attractionIndex]);
                    attractionIndex++;
                } else {
                    // Loop around if we run out
                    attractionIndex = 0;
                    dayAttractions.push(attractions[attractionIndex]);
                    attractionIndex++;
                }
            }

            itinerary.push({
                day: i,
                activities: [
                    { time: '09:00 AM', desc: 'Breakfast at a local cafe' },
                    { time: '10:30 AM', desc: `Visit ${dayAttractions[0]}` },
                    { time: '01:00 PM', desc: 'Lunch break' },
                    { time: '03:00 PM', desc: `Explore ${dayAttractions[1]}` },
                    { time: '07:00 PM', desc: 'Dinner and evening walk' }
                ]
            });
        }

        return {
            status: 'success',
            data: itinerary,
            message: `Created a full ${days}-day itinerary for ${destination}.`
        };
    }

    renderCard(data) {
        if (!data || data.length === 0) return '';
        
        let html = `
        <div class="itinerary-card">
            <div class="card-header">
                <span>🗺️</span> Day-by-Day Itinerary
            </div>
            <div class="card-body">
        `;

        data.forEach(day => {
            html += `<div style="margin-bottom: 12px;"><strong>Day ${day.day}</strong></div>`;
            day.activities.forEach(act => {
                html += `
                    <div style="display:flex; margin-bottom: 6px; font-size: 14px;">
                        <span style="width: 80px; color: var(--text-secondary); flex-shrink: 0;">${act.time}</span>
                        <span>${act.desc}</span>
                    </div>
                `;
            });
            if (day.day !== data.length) html += `<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.05); margin: 12px 0;">`;
        });

        html += `</div></div>`;
        return html;
    }
}
