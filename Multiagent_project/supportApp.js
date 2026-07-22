class TriageAgent {
    constructor() { this.name = "Triage Agent"; }
    async process(text) {
        await new Promise(resolve => setTimeout(resolve, 1200));
        const lowerText = text.toLowerCase();
        let intent = 'query';
        let sentiment = 'neutral';
        let priority = 'low';

        if (lowerText.includes('refund') || lowerText.includes('money back')) {
            intent = 'refund';
        } else if (lowerText.includes('broken') || lowerText.includes('cracked') || lowerText.includes('stopped working')) {
            intent = 'technical_issue';
        }

        if (lowerText.includes('angry') || lowerText.includes('now!') || lowerText.includes('horrible') || lowerText.includes('terrible')) {
            sentiment = 'angry';
            priority = 'high';
        } else if (lowerText.includes('please') || lowerText.includes('help')) {
            sentiment = 'polite';
        }

        if (intent === 'refund' || intent === 'technical_issue') priority = 'high';

        return { intent, sentiment, priority };
    }
}

class PolicyAgent {
    constructor() { this.name = "Policy Agent"; }
    async process(triageData, text) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        const lowerText = text.toLowerCase();
        
        // Mock Knowledge Base lookup
        let eligible = false;
        let policyReason = "";

        if (triageData.intent === 'refund' || triageData.intent === 'technical_issue') {
            if (lowerText.includes('yesterday') || lowerText.includes('days ago')) {
                eligible = true;
                policyReason = "Item reported damaged/faulty within 30-day return window.";
            } else if (lowerText.includes('months ago') || lowerText.includes('year ago')) {
                eligible = false;
                policyReason = "Standard warranty expired (over 30 days). Requires extended warranty check.";
            } else {
                eligible = true; // default lenient
                policyReason = "Standard replacement policy applies for unspecified timeframe.";
            }
        } else {
            eligible = true;
            policyReason = "General support query. Standard SLA applies.";
        }

        return { eligible, policyReason };
    }
}

class ActionAgent {
    constructor() { this.name = "Action Agent"; }
    async process(triageData, policyData) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        let actionTaken = "";
        let details = "";

        if (policyData.eligible) {
            if (triageData.intent === 'refund') {
                actionTaken = "PROCESS_REFUND";
                details = "Initiated full refund to original payment method. Expected in 3-5 business days.";
            } else if (triageData.intent === 'technical_issue') {
                actionTaken = "GENERATE_RMA";
                details = "Generated Return Merchandise Authorization (RMA) label and sent to customer email.";
            } else {
                actionTaken = "CREATE_TICKET";
                details = "Created Level 1 Support Ticket and assigned to next available human agent.";
            }
        } else {
            actionTaken = "ESCALATE_TO_HUMAN";
            details = "Request denied by automated policy. Escalating to Level 2 human review to prevent churn.";
        }

        return { actionTaken, details };
    }
}

class SupportOrchestrator {
    constructor(updateStatusCb, addMessageCb, testerLogCb) {
        this.triage = new TriageAgent();
        this.policy = new PolicyAgent();
        this.action = new ActionAgent();
        this.updateStatus = updateStatusCb;
        this.addMessage = addMessageCb;
        this.testerLog = testerLogCb;
    }

    async handleUserInput(text) {
        this.updateStatus('sup-orchestrator', 'working');
        this.testerLog(`[Support Master] Received ticket: "${text}"`, 'info');

        try {
            // Triage Phase
            this.updateStatus('sup-triage', 'working');
            this.testerLog(`[Support Master] Invoking TriageAgent...`);
            const triageResult = await this.triage.process(text);
            this.testerLog(`[TriageAgent] Intent: ${triageResult.intent}, Priority: ${triageResult.priority}`);
            this.updateStatus('sup-triage', 'done');

            // Policy Phase
            this.updateStatus('sup-policy', 'working');
            this.testerLog(`[Support Master] Invoking PolicyAgent...`);
            const policyResult = await this.policy.process(triageResult, text);
            this.testerLog(`[PolicyAgent] Eligible: ${policyResult.eligible}, Reason: ${policyResult.policyReason}`);
            this.updateStatus('sup-policy', 'done');

            // Action Phase
            this.updateStatus('sup-action', 'working');
            this.testerLog(`[Support Master] Invoking ActionAgent...`);
            const actionResult = await this.action.process(triageResult, policyResult);
            this.testerLog(`[ActionAgent] Action: ${actionResult.actionTaken}, Details: ${actionResult.details}`);
            this.updateStatus('sup-action', 'done');

            // Compose final response
            let responseHtml = `
            <div class="itinerary-card" style="border-color: #f43f5e;">
                <div class="card-header" style="background: rgba(244, 63, 94, 0.1);">
                    <span>📋</span> Ticket Resolution Summary
                </div>
                <div class="card-body">
                    <div class="item-row">
                        <span><strong>Priority</strong></span>
                        <span style="color: ${triageResult.priority === 'high' ? '#f43f5e' : '#10b981'}; text-transform: capitalize;">${triageResult.priority}</span>
                    </div>
                    <div class="item-row">
                        <span><strong>Policy Check</strong></span>
                        <span style="max-width: 60%; text-align: right; color: var(--text-secondary);">${policyResult.policyReason}</span>
                    </div>
                    <div class="item-row" style="margin-top: 8px; border-top: 1px solid var(--glass-border); padding-top: 12px;">
                        <span><strong>Action Taken</strong></span>
                        <span style="color: #60a5fa;">${actionResult.actionTaken}</span>
                    </div>
                    <p style="margin-top: 12px; font-size: 13px; color: var(--text-secondary); line-height: 1.5;">${actionResult.details}</p>
                </div>
            </div>`;

            this.addMessage(responseHtml, 'system');

            setTimeout(() => {
                ['sup-orchestrator', 'sup-triage', 'sup-policy', 'sup-action'].forEach(agent => {
                    this.updateStatus(agent, 'idle');
                });
            }, 3000);

        } catch (error) {
            console.error("Support Orchestrator Error:", error);
            this.addMessage("System error processing ticket.", 'system');
            this.updateStatus('sup-orchestrator', 'idle');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const supportChatHistory = document.getElementById('support-chat-history');
    const supportUserInput = document.getElementById('support-user-input');
    const supportSendBtn = document.getElementById('support-send-btn');
    const supportPromptBtns = document.querySelectorAll('.support-prompt');

    const updateSupportAgentStatus = (agentId, status) => {
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

    const testerLogArea = document.getElementById('tester-log');
    const logToTesterPanel = (message, type = '') => {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const p = document.createElement('p');
        if (type) p.className = type;
        p.textContent = `[${time}] ${message}`;
        testerLogArea.appendChild(p);
        testerLogArea.scrollTop = testerLogArea.scrollHeight;
    };

    const addSupportMessage = (content, sender = 'system') => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender === 'user' ? 'user-message' : 'system-message'}`;
        const avatar = sender === 'user' ? '👤' : '🤖';
        
        let contentStyle = '';
        if(sender === 'user') {
            contentStyle = 'background: rgba(244, 63, 94, 0.15); border-color: rgba(244, 63, 94, 0.3);';
        }

        msgDiv.innerHTML = `<div class="message-avatar" style="${sender === 'user' ? 'background: linear-gradient(135deg, #f43f5e, #be123c);' : ''}">${avatar}</div><div class="message-content" style="${contentStyle}">${content}</div>`;
        supportChatHistory.appendChild(msgDiv);
        supportChatHistory.scrollTop = supportChatHistory.scrollHeight;
        
        const typingInd = document.getElementById('support-typing-indicator');
        if (typingInd && sender === 'system') {
            typingInd.remove();
        }
    };

    const showSupportTyping = () => {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system-message';
        msgDiv.id = 'support-typing-indicator';
        msgDiv.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content"><div class="typing-indicator"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>`;
        supportChatHistory.appendChild(msgDiv);
        supportChatHistory.scrollTop = supportChatHistory.scrollHeight;
    };

    // Make sure we only instantiate if the elements exist (in case DOM differs)
    if(supportSendBtn) {
        const supportOrchestrator = new SupportOrchestrator(updateSupportAgentStatus, addSupportMessage, logToTesterPanel);

        const handleSupportSend = async () => {
            const text = supportUserInput.value.trim();
            if (!text) return;
            addSupportMessage(text, 'user');
            supportUserInput.value = '';
            showSupportTyping();
            await supportOrchestrator.handleUserInput(text);
        };

        supportSendBtn.addEventListener('click', handleSupportSend);
        supportUserInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSupportSend();
            }
        });

        supportPromptBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                supportUserInput.value = btn.textContent;
                handleSupportSend();
            });
        });
    }
});
