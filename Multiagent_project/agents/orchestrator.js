import { parseInput } from '../utils/nlp.js';
import { FlightAgent } from './flightAgent.js';
import { HotelAgent } from './hotelAgent.js';
import { DayPlanAgent } from './dayPlanAgent.js';
import { BudgetAgent } from './budgetAgent.js';

export class Orchestrator {
    constructor(updateStatusCb, addMessageCb) {
        this.flightAgent = new FlightAgent();
        this.hotelAgent = new HotelAgent();
        this.dayPlanAgent = new DayPlanAgent();
        this.budgetAgent = new BudgetAgent();
        
        this.updateStatus = updateStatusCb;
        this.addMessage = addMessageCb;
    }

    async handleUserInput(text) {
        this.updateStatus('orchestrator', 'working');
        
        // Parse context
        const context = parseInput(text);
        
        if (!context.destination) {
            this.addMessage("I couldn't detect a destination in your request. Could you please specify where you'd like to go?", 'system');
            this.updateStatus('orchestrator', 'idle');
            return;
        }

        let responseHtml = `<p>I'm planning a ${context.days}-day trip to <strong>${context.destination}</strong> for ${context.people} people.</p>`;
        
        let flightResults, hotelResults, dayPlanResults, budgetResults;

        try {
            // Depending on intent, call specific agents
            if (context.intent === 'flights' || context.intent === 'full_plan') {
                this.updateStatus('flight', 'working');
                flightResults = await this.flightAgent.process(context);
                this.updateStatus('flight', 'done');
                responseHtml += this.flightAgent.renderCard(flightResults.data);
            }

            if (context.intent === 'hotels' || context.intent === 'full_plan') {
                this.updateStatus('hotel', 'working');
                hotelResults = await this.hotelAgent.process(context);
                this.updateStatus('hotel', 'done');
                responseHtml += this.hotelAgent.renderCard(hotelResults.data);
            }

            if (context.intent === 'itinerary' || context.intent === 'full_plan') {
                this.updateStatus('dayplan', 'working');
                dayPlanResults = await this.dayPlanAgent.process(context);
                this.updateStatus('dayplan', 'done');
                responseHtml += this.dayPlanAgent.renderCard(dayPlanResults.data);
            }

            if (context.intent === 'full_plan') {
                this.updateStatus('budget', 'working');
                budgetResults = await this.budgetAgent.process(
                    context, 
                    flightResults?.data, 
                    hotelResults?.data
                );
                this.updateStatus('budget', 'done');
                responseHtml += this.budgetAgent.renderCard(budgetResults.data);
            }

            // Final message
            this.addMessage(responseHtml, 'system');
            
            // Reset statuses after a delay
            setTimeout(() => {
                ['orchestrator', 'flight', 'hotel', 'dayplan', 'budget'].forEach(agent => {
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
