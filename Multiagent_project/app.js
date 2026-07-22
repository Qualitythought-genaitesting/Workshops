const mockData = {
    flights: [
        { id: 'f1', from: 'Mumbai', to: 'Paris', airline: 'Air France', price: 45000, duration: '9h 20m', stops: 0 },
        { id: 'f2', from: 'Mumbai', to: 'Paris', airline: 'Emirates', price: 38000, duration: '12h 45m', stops: 1 },
        { id: 'f3', from: 'Delhi', to: 'Bali', airline: 'Singapore Airlines', price: 28000, duration: '8h 15m', stops: 1 },
        { id: 'f4', from: 'Delhi', to: 'Bali', airline: 'AirAsia', price: 21000, duration: '11h 30m', stops: 1 },
        { id: 'f5', from: 'New York', to: 'London', airline: 'British Airways', price: 40000, duration: '7h 10m', stops: 0 },
        { id: 'f6', from: 'Any', to: 'Tokyo', airline: 'ANA', price: 55000, duration: '10h 00m', stops: 0 },
    ],
    
    hotels: [
        { id: 'h1', city: 'Paris', name: 'Le Meurice', rating: 5, pricePerNight: 35000, amenities: ['Spa', 'Eiffel View', 'Pool'] },
        { id: 'h2', city: 'Paris', name: 'Hotel Monge', rating: 4, pricePerNight: 12000, amenities: ['Free WiFi', 'Breakfast', 'Central'] },
        { id: 'h3', city: 'Paris', name: 'Ibis Styles', rating: 3, pricePerNight: 7000, amenities: ['Free WiFi', 'Breakfast'] },
        { id: 'h4', city: 'Bali', name: 'Ayana Resort', rating: 5, pricePerNight: 20000, amenities: ['Ocean View', 'Infinity Pool', 'Spa'] },
        { id: 'h5', city: 'Bali', name: 'Ubud Village Hotel', rating: 4, pricePerNight: 8000, amenities: ['Pool', 'Jungle View', 'Breakfast'] },
        { id: 'h6', city: 'London', name: 'The Savoy', rating: 5, pricePerNight: 40000, amenities: ['Luxury', 'Central', 'Spa'] },
        { id: 'h7', city: 'Tokyo', name: 'Park Hyatt', rating: 5, pricePerNight: 32000, amenities: ['City View', 'Pool', 'Gym'] },
    ],

    attractions: {
        'Paris': ['Eiffel Tower', 'Louvre Museum', 'Notre-Dame', 'Montmartre', 'Seine River Cruise', 'Palace of Versailles', 'Disneyland Paris'],
        'Bali': ['Uluwatu Temple', 'Ubud Monkey Forest', 'Tegallalang Rice Terrace', 'Mount Batur', 'Seminyak Beach', 'Nusa Penida'],
        'London': ['Tower of London', 'London Eye', 'British Museum', 'Buckingham Palace', 'Westminster Abbey', 'Hyde Park'],
        'Tokyo': ['Senso-ji Temple', 'Tokyo Skytree', 'Meiji Shrine', 'Shibuya Crossing', 'Tsukiji Outer Market', 'Akihabara']
    }
};

function parseInput(text) {
    const lowerText = text.toLowerCase();
    
    const entities = {
        origin: null,
        destination: null,
        days: 3,
        people: 1,
        budget: null,
        intent: 'full_plan'
    };

    if (lowerText.includes('flight') && !lowerText.includes('hotel') && !lowerText.includes('itinerary')) {
        entities.intent = 'flights';
    } else if (lowerText.includes('hotel') && !lowerText.includes('flight')) {
        entities.intent = 'hotels';
    } else if (lowerText.includes('itinerary') || lowerText.includes('day plan')) {
        entities.intent = 'itinerary';
    } else if (lowerText.includes('mcp') || lowerText.includes('packages') || lowerText.includes('external')) {
        entities.intent = 'mcp_packages';
    }

    const cities = ['mumbai', 'delhi', 'paris', 'bali', 'london', 'new york', 'tokyo'];
    
    for (const city of cities) {
        if (lowerText.includes(`from ${city}`)) {
            entities.origin = city.charAt(0).toUpperCase() + city.slice(1);
            break;
        }
    }
    
    for (const city of cities) {
        if (lowerText.includes(`to ${city}`) || lowerText.includes(`in ${city}`)) {
            entities.destination = city.charAt(0).toUpperCase() + city.slice(1);
            break;
        }
    }

    if (!entities.destination) {
        for (const city of cities) {
            if (lowerText.includes(city) && city !== entities.origin?.toLowerCase()) {
                entities.destination = city.charAt(0).toUpperCase() + city.slice(1);
                break;
            }
        }
    }

    // Fallback regex to capture any missed destinations (e.g. "to Rome", "in Rome")
    if (!entities.destination) {
        const toMatch = lowerText.match(/(?:to|in|visit)\s+([a-z]+)/i);
        if (toMatch) {
            const dest = toMatch[1];
            // Exclude common stop words
            if (!['the', 'a', 'an', 'my', 'our'].includes(dest)) {
                entities.destination = dest.charAt(0).toUpperCase() + dest.slice(1);
            }
        }
    }

    const dayMatch = lowerText.match(/(\d+)(?:\s*|-)(?:day|night)/);
    if (dayMatch) {
        entities.days = parseInt(dayMatch[1]);
    }

    const peopleMatch = lowerText.match(/(\d+)\s*people/);
    if (peopleMatch) {
        entities.people = parseInt(peopleMatch[1]);
    }

    const budgetMatch = lowerText.match(/(?:budget|under|around)\s*(?:of\s*)?(?:₹|rs\.?|inr)?\s*([\d,.]+)\s*(lakhs?|k)?/);
    if (budgetMatch) {
        let val = parseFloat(budgetMatch[1].replace(/,/g, ''));
        if (budgetMatch[2]) {
            if (budgetMatch[2].startsWith('lakh')) val *= 100000;
            if (budgetMatch[2] === 'k') val *= 1000;
        }
        entities.budget = val;
    }

    return entities;
}

class FlightAgent {
    constructor() { this.name = "Flight Agent"; }
    async process(context) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        const { origin, destination, people } = context;
        if (!destination) return { error: "I need to know your destination to find flights." };
        let flights = mockData.flights.filter(f => f.to.toLowerCase() === destination.toLowerCase() && (f.from.toLowerCase() === (origin?.toLowerCase() || '') || f.from === 'Any'));
        if (flights.length === 0) flights = mockData.flights.slice(0, 2);
        const results = flights.map(f => ({ ...f, totalPrice: f.price * people, people }));
        return { status: 'success', data: results, message: `Found ${results.length} flight options to ${destination}.` };
    }
    renderCard(data) {
        if (!data || data.length === 0) return '';
        let html = `<div class="itinerary-card"><div class="card-header"><span>✈️</span> Flight Options</div><div class="card-body">`;
        data.forEach(flight => {
            html += `<div class="item-row"><div><strong>${flight.airline}</strong><br><small>${flight.from} → ${flight.to} (${flight.duration}, ${flight.stops} stops)</small></div><div class="price">₹${flight.totalPrice.toLocaleString()} <br><small style="color:var(--text-secondary)">for ${flight.people} pax</small></div></div>`;
        });
        html += `</div></div>`;
        return html;
    }
}

class HotelAgent {
    constructor() { this.name = "Hotel Agent"; }
    async process(context) {
        await new Promise(resolve => setTimeout(resolve, 1800));
        const { destination, days } = context;
        if (!destination) return { error: "I need a destination to find hotels." };
        let hotels = mockData.hotels.filter(h => h.city.toLowerCase() === destination.toLowerCase());
        if (hotels.length === 0) hotels = mockData.hotels.slice(0, 2);
        const nights = Math.max(1, days - 1);
        const results = hotels.map(h => ({ ...h, totalPrice: h.pricePerNight * nights, nights }));
        return { status: 'success', data: results, message: `Found ${results.length} hotels in ${destination} for ${nights} nights.` };
    }
    renderCard(data) {
        if (!data || data.length === 0) return '';
        let html = `<div class="itinerary-card"><div class="card-header"><span>🏨</span> Hotel Accommodations</div><div class="card-body">`;
        data.forEach(hotel => {
            const stars = '⭐'.repeat(hotel.rating);
            html += `<div class="item-row"><div><strong>${hotel.name}</strong> ${stars}<br><small>${hotel.amenities.join(' • ')}</small></div><div class="price">₹${hotel.totalPrice.toLocaleString()} <br><small style="color:var(--text-secondary)">for ${hotel.nights} nights</small></div></div>`;
        });
        html += `</div></div>`;
        return html;
    }
}

class DayPlanAgent {
    constructor() { this.name = "Day Planner"; }
    async process(context) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const { destination, days } = context;
        if (!destination) return { error: "I need a destination to plan activities." };
        let attractions = mockData.attractions[destination] || mockData.attractions['Paris'];
        const itinerary = [];
        let attractionIndex = 0;
        for (let i = 1; i <= days; i++) {
            const dayAttractions = [];
            for (let j = 0; j < 2; j++) {
                if (attractionIndex < attractions.length) { dayAttractions.push(attractions[attractionIndex]); attractionIndex++; } 
                else { attractionIndex = 0; dayAttractions.push(attractions[attractionIndex]); attractionIndex++; }
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
        return { status: 'success', data: itinerary, message: `Created a full ${days}-day itinerary for ${destination}.` };
    }
    renderCard(data) {
        if (!data || data.length === 0) return '';
        let html = `<div class="itinerary-card"><div class="card-header"><span>🗺️</span> Day-by-Day Itinerary</div><div class="card-body">`;
        data.forEach(day => {
            html += `<div style="margin-bottom: 12px;"><strong>Day ${day.day}</strong></div>`;
            day.activities.forEach(act => {
                html += `<div style="display:flex; margin-bottom: 6px; font-size: 14px;"><span style="width: 80px; color: var(--text-secondary); flex-shrink: 0;">${act.time}</span><span>${act.desc}</span></div>`;
            });
            if (day.day !== data.length) html += `<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.05); margin: 12px 0;">`;
        });
        html += `</div></div>`;
        return html;
    }
}

class BudgetAgent {
    constructor() { this.name = "Budget Agent"; }
    async process(context, flightData, hotelData) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const { people, days, budget } = context;
        let flightCost = 0; let hotelCost = 0;
        if (flightData && flightData.length > 0) flightCost = flightData[0].totalPrice;
        if (hotelData && hotelData.length > 0) hotelCost = hotelData[0].totalPrice;
        const totalMeals = 3000 * people * days;
        const totalActivities = 2500 * people * days;
        const totalTransport = 1000 * people * days;
        const totalCost = flightCost + hotelCost + totalMeals + totalActivities + totalTransport;
        let status = 'success'; let message = `Total estimated cost is ₹${totalCost.toLocaleString()}.`;
        if (budget && totalCost > budget) { status = 'warning'; message += ` This is over your budget of ₹${budget.toLocaleString()}.`; } 
        else if (budget) { message += ` This is within your budget of ₹${budget.toLocaleString()}.`; }
        const data = { flightCost, hotelCost, meals: totalMeals, activities: totalActivities, transport: totalTransport, total: totalCost, perPerson: Math.round(totalCost / people), budgetContext: budget ? { target: budget, over: totalCost > budget } : null };
        return { status, data, message };
    }
    renderCard(data) {
        if (!data) return '';
        let html = `<div class="itinerary-card"><div class="card-header"><span>💰</span> Budget Breakdown</div><div class="card-body">
            <div class="item-row"><span>Flights</span><span>₹${data.flightCost.toLocaleString()}</span></div>
            <div class="item-row"><span>Hotel</span><span>₹${data.hotelCost.toLocaleString()}</span></div>
            <div class="item-row"><span>Meals Estimate</span><span>₹${data.meals.toLocaleString()}</span></div>
            <div class="item-row"><span>Activities Estimate</span><span>₹${data.activities.toLocaleString()}</span></div>
            <div class="item-row"><span>Local Transport</span><span>₹${data.transport.toLocaleString()}</span></div>
            <div class="item-row" style="margin-top: 8px; border-top: 1px solid var(--glass-border); padding-top: 12px; font-weight: bold; font-size: 16px;">
                <span>Total Estimated Cost</span><span class="price" style="${data.budgetContext && data.budgetContext.over ? 'color: #ef4444;' : ''}">₹${data.total.toLocaleString()}</span>
            </div>
            <div style="text-align: right; font-size: 13px; color: var(--text-secondary); margin-top: 4px;">₹${data.perPerson.toLocaleString()} per person</div>
        </div></div>`;
        return html;
    }
}

class McpScraperAgent {
    constructor() { this.name = "MCP Scraper Agent"; }
    async process(context) {
        await new Promise(resolve => setTimeout(resolve, 2500)); // Simulating external web scraping via MCP
        const dest = context.destination || 'a popular destination';
        
        // Mock scraped external data
        const packages = [
            { source: 'MakeMyTrip (Simulated)', title: `5 Nights in ${dest} + Flights`, price: 85000, tag: 'Bestseller' },
            { source: 'Expedia (Simulated)', title: `Luxury ${dest} Resort Stay`, price: 120000, tag: 'Premium' },
            { source: 'Agoda (Simulated)', title: `Budget Backpacker ${dest}`, price: 45000, tag: 'Value' }
        ];

        return { status: 'success', data: packages, message: `Scraped ${packages.length} external packages for ${dest}.` };
    }
    renderCard(data) {
        if (!data || data.length === 0) return '';
        let html = `<div class="itinerary-card" style="border-color: var(--accent-purple); box-shadow: 0 0 10px rgba(139, 92, 246, 0.2);"><div class="card-header" style="background: rgba(139, 92, 246, 0.2);"><span>🕸️</span> External Packages (via MCP)</div><div class="card-body">`;
        data.forEach(pkg => {
            html += `<div class="item-row">
                <div>
                    <span style="font-size: 10px; background: var(--accent-purple); padding: 2px 6px; border-radius: 4px; margin-bottom: 4px; display: inline-block;">${pkg.source}</span><br>
                    <strong>${pkg.title}</strong>
                    <br><small style="color:var(--text-secondary)">${pkg.tag}</small>
                </div>
                <div class="price" style="color: #c084fc;">₹${pkg.price.toLocaleString()}</div>
            </div>`;
        });
        html += `</div></div>`;
        return html;
    }
}

class Orchestrator {
    constructor(updateStatusCb, addMessageCb, testerLogCb) {
        this.flightAgent = new FlightAgent();
        this.hotelAgent = new HotelAgent();
        this.dayPlanAgent = new DayPlanAgent();
        this.budgetAgent = new BudgetAgent();
        this.mcpAgent = new McpScraperAgent();
        this.updateStatus = updateStatusCb;
        this.addMessage = addMessageCb;
        this.testerLog = testerLogCb;
    }
    async handleUserInput(text) {
        this.updateStatus('orchestrator', 'working');
        this.testerLog(`[Orchestrator] Received input: "${text}"`, 'info');
        
        const context = parseInput(text);
        this.testerLog(`[NLP Parser] Extracted intent: '${context.intent}', dest: '${context.destination}'`);
        
        if (!context.destination) {
            this.testerLog(`[Orchestrator] No destination found, asking user.`, 'warn');
            this.addMessage("I couldn't detect a destination in your request. Could you please specify where you'd like to go?", 'system');
            this.updateStatus('orchestrator', 'idle');
            return;
        }
        let responseHtml = `<p>I'm planning a ${context.days}-day trip to <strong>${context.destination}</strong> for ${context.people} people.</p>`;
        
        // Check if the destination is known in local mock data
        const knownCities = ['Mumbai', 'Delhi', 'Paris', 'Bali', 'London', 'New York', 'Tokyo'];
        const isKnown = knownCities.some(c => c.toLowerCase() === context.destination.toLowerCase());

        // Fallback to MCP if the destination is a "missed" or external destination
        if (!isKnown && context.intent !== 'mcp_packages') {
            this.testerLog(`[Orchestrator] Destination '${context.destination}' not found locally. Falling back to MCP Web Scraper...`, 'warn');
            context.intent = 'mcp_packages';
            responseHtml = `<p>I couldn't find local data for <strong>${context.destination}</strong>. Connecting to external sources via MCP to find the best packages...</p>`;
        } else if (context.intent === 'mcp_packages') {
            responseHtml = `<p>Searching external sources for the best packages to <strong>${context.destination}</strong>...</p>`;
        }
        
        let flightResults, hotelResults, dayPlanResults, budgetResults, mcpResults;
        try {
            if (context.intent === 'flights' || context.intent === 'full_plan') {
                this.testerLog(`[Orchestrator] Invoking FlightAgent...`);
                this.updateStatus('flight', 'working');
                flightResults = await this.flightAgent.process(context);
                this.updateStatus('flight', 'done');
                responseHtml += this.flightAgent.renderCard(flightResults.data);
            }
            if (context.intent === 'hotels' || context.intent === 'full_plan') {
                this.testerLog(`[Orchestrator] Invoking HotelAgent...`);
                this.updateStatus('hotel', 'working');
                hotelResults = await this.hotelAgent.process(context);
                this.updateStatus('hotel', 'done');
                responseHtml += this.hotelAgent.renderCard(hotelResults.data);
            }
            if (context.intent === 'itinerary' || context.intent === 'full_plan') {
                this.testerLog(`[Orchestrator] Invoking DayPlanAgent...`);
                this.updateStatus('dayplan', 'working');
                dayPlanResults = await this.dayPlanAgent.process(context);
                this.updateStatus('dayplan', 'done');
                responseHtml += this.dayPlanAgent.renderCard(dayPlanResults.data);
            }
            if (context.intent === 'full_plan') {
                this.testerLog(`[Orchestrator] Invoking BudgetAgent...`);
                this.updateStatus('budget', 'working');
                budgetResults = await this.budgetAgent.process(context, flightResults?.data, hotelResults?.data);
                this.updateStatus('budget', 'done');
                responseHtml += this.budgetAgent.renderCard(budgetResults.data);
            }
            if (context.intent === 'mcp_packages') {
                this.testerLog(`[Orchestrator] Invoking McpScraperAgent...`);
                this.updateStatus('mcp', 'working');
                mcpResults = await this.mcpAgent.process(context);
                this.updateStatus('mcp', 'done');
                responseHtml += this.mcpAgent.renderCard(mcpResults.data);
            }
            this.testerLog(`[Orchestrator] Finished. Rendering response.`, 'info');
            this.addMessage(responseHtml, 'system');
            setTimeout(() => {
                ['orchestrator', 'flight', 'hotel', 'dayplan', 'budget', 'mcp'].forEach(agent => {
                    this.updateStatus(agent, 'idle');
                });
            }, 3000);
        } catch (error) {
            console.error("Error during orchestration:", error);
            this.addMessage("Sorry, I encountered an error while planning your trip. Please try again.", 'system');
            this.updateStatus('orchestrator', 'idle');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const promptBtns = document.querySelectorAll('.prompt-btn');

    const updateAgentStatus = (agentId, status) => {
        const agentEl = document.getElementById(`agent-${agentId}`);
        if (!agentEl) return;
        const statusSpan = agentEl.querySelector('.agent-status');
        agentEl.classList.remove('active', 'done');
        statusSpan.classList.remove('status-idle', 'status-working', 'status-done');
        if (status === 'working') {
            agentEl.classList.add('active');
            statusSpan.classList.add('status-working');
            statusSpan.textContent = 'Working...';
        } else if (status === 'done') {
            agentEl.classList.add('done');
            statusSpan.classList.add('status-done');
            statusSpan.textContent = 'Done';
        } else {
            statusSpan.classList.add('status-idle');
            statusSpan.textContent = 'Ready';
        }
    };

    const addMessageToChat = (content, sender = 'system') => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender === 'user' ? 'user-message' : 'system-message'}`;
        const avatar = sender === 'user' ? '👤' : '🤖';
        msgDiv.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-content">${content}</div>`;
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        const typingInd = document.getElementById('typing-indicator');
        if (typingInd && sender === 'system') {
            typingInd.remove();
        }
    };

    const showTypingIndicator = () => {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system-message';
        msgDiv.id = 'typing-indicator';
        msgDiv.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content"><div class="typing-indicator"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>`;
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    };

    // Tester Logging Function
    const testerLogArea = document.getElementById('tester-log');
    const logToTesterPanel = (message, type = '') => {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const p = document.createElement('p');
        if (type) p.className = type;
        p.textContent = `[${time}] ${message}`;
        testerLogArea.appendChild(p);
        testerLogArea.scrollTop = testerLogArea.scrollHeight;
    };

    // Toggle Tester Panel
    const testerHeader = document.getElementById('tester-header');
    const testerPanel = document.getElementById('tester-panel');
    testerHeader.addEventListener('click', () => {
        testerPanel.classList.toggle('collapsed');
        const icon = testerHeader.querySelector('.toggle-icon');
        icon.textContent = testerPanel.classList.contains('collapsed') ? '▲' : '▼';
    });

    const orchestrator = new Orchestrator(updateAgentStatus, addMessageToChat, logToTesterPanel);

    const handleSend = async () => {
        const text = userInput.value.trim();
        if (!text) return;
        addMessageToChat(text, 'user');
        userInput.value = '';
        showTypingIndicator();
        await orchestrator.handleUserInput(text);
    };

    sendBtn.addEventListener('click', handleSend);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    promptBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            userInput.value = btn.textContent;
            handleSend();
        });
    });
});
