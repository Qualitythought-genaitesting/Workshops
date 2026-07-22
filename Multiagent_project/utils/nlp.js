// Simple NLP module to extract intent and entities from user input

export function parseInput(text) {
    const lowerText = text.toLowerCase();
    
    // Default extracted entities
    const entities = {
        origin: null,
        destination: null,
        days: 3, // default
        people: 1, // default
        budget: null,
        intent: 'full_plan' // flights, hotels, itinerary, full_plan
    };

    // Detect Intent
    if (lowerText.includes('flight') && !lowerText.includes('hotel') && !lowerText.includes('itinerary')) {
        entities.intent = 'flights';
    } else if (lowerText.includes('hotel') && !lowerText.includes('flight')) {
        entities.intent = 'hotels';
    } else if (lowerText.includes('itinerary') || lowerText.includes('day plan')) {
        entities.intent = 'itinerary';
    }

    // Extract Cities (simple keyword matching for demo)
    const cities = ['mumbai', 'delhi', 'paris', 'bali', 'london', 'new york', 'tokyo'];
    
    // Find 'from' city
    for (const city of cities) {
        if (lowerText.includes(`from ${city}`)) {
            entities.origin = city.charAt(0).toUpperCase() + city.slice(1);
            break;
        }
    }
    
    // Find 'to' city
    for (const city of cities) {
        if (lowerText.includes(`to ${city}`) || lowerText.includes(`in ${city}`)) {
            entities.destination = city.charAt(0).toUpperCase() + city.slice(1);
            break;
        }
    }

    // Fallback city extraction if "to/from" prepositions missed
    if (!entities.destination) {
        for (const city of cities) {
            if (lowerText.includes(city) && city !== entities.origin?.toLowerCase()) {
                entities.destination = city.charAt(0).toUpperCase() + city.slice(1);
                break;
            }
        }
    }

    // Extract days
    const dayMatch = lowerText.match(/(\d+)(?:\s*|-)(?:day|night)/);
    if (dayMatch) {
        entities.days = parseInt(dayMatch[1]);
    }

    // Extract people
    const peopleMatch = lowerText.match(/(\d+)\s*people/);
    if (peopleMatch) {
        entities.people = parseInt(peopleMatch[1]);
    }

    // Extract budget
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
