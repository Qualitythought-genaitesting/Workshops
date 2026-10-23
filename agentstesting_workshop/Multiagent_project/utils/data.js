export const mockData = {
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
