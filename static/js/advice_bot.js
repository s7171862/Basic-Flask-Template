(() => {
    const form = document.getElementById('advice-bot-form');
    const input = document.getElementById('advice-bot-input');
    const history = document.getElementById('advice-bot-history');
    if (!form || !input || !history) return;

    const answer = question => {
        const text = question.toLowerCase();
        if (/deposit|security/.test(text)) {
            return 'Toolly adds a refundable security deposit equal to 10% of the tool’s listed original value. The booking page shows it clearly before you confirm.';
        }
        if (/insurance|cover|damage/.test(text)) {
            return 'Renter insurance is optional. It starts at $5 for a tool under $100 and doubles for each additional $100 of original value. For damage questions, message the provider and keep a record of the tool’s condition.';
        }
        if (/price|cost|pay|fee/.test(text)) {
            return 'Your total is the daily rental rate × number of days, plus the refundable 10% deposit and optional insurance. Toolly shows the full breakdown before booking.';
        }
        if (/available|date|when|long/.test(text)) {
            return 'Each listing shows its available-from and available-until dates. Pick your start and end dates within that period, then confirm the booking.';
        }
        if (/tool|drill|saw|choose|project/.test(text)) {
            return 'Use Browse Tools to filter by Queensland city, suburb, tool type, brand, condition, price, and availability. If you are unsure, message the provider before booking.';
        }
        if (/message|provider|owner|contact/.test(text)) {
            return 'Renters can use “Message provider” on an available listing. Once a conversation is started, both people can reply from the Messages page.';
        }
        if (/safe|safety|danger/.test(text)) {
            return 'Always read the manufacturer instructions, wear suitable protective gear, inspect the tool before use, and stop if anything looks damaged or unsafe.';
        }
        return 'I can help with renting, deposits, insurance, availability, messaging a provider, choosing a tool, or basic tool safety.';
    };

    const addMessage = (message, className) => {
        const item = document.createElement('div');
        item.className = `advice-message ${className}`;
        item.textContent = message;
        history.appendChild(item);
        history.scrollTop = history.scrollHeight;
    };

    form.addEventListener('submit', event => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) return;
        addMessage(question, 'from-user');
        addMessage(answer(question), 'from-bot');
        input.value = '';
        input.focus();
    });
})();
