(() => {
    const form = document.getElementById('advice-bot-form');
    const input = document.getElementById('advice-bot-input');
    const history = document.getElementById('advice-bot-history');
    if (!form || !input || !history) return;

    const jobSuggestions = [
        { pattern: /paint|wall.*colour|repaint|ceiling/, reply: 'For painting a room, look for a paint roller and tray for most walls. A paint sprayer can be faster for large areas, while an orbital sander helps prepare rough or peeling surfaces. Use a drop sheet and mask.' },
        { pattern: /drill|hole|hang|mount|shelf|screw/, reply: 'For drilling holes or installing shelves, choose a cordless drill/driver. For brick or concrete, you usually need a hammer drill and masonry bit. Check the provider listing or message them about included drill bits.' },
        { pattern: /cut.*timber|cut.*wood|deck|fence|lumber|plank/, reply: 'For straight timber cuts, a circular saw is usually a good fit. A mitre saw is better for precise repeated angles, such as trim or decking. Measure twice, clamp the timber, and wear eye protection.' },
        { pattern: /tile|bathroom.*floor|backsplash|grout/, reply: 'For cutting ceramic or porcelain tiles, look for a tile cutter or wet tile saw. A tile spacer and grout float may also help. Confirm the tool is suitable for the tile material and thickness.' },
        { pattern: /sand|strip.*paint|smooth.*wood|refinish/, reply: 'For smoothing timber or removing old finish, an orbital sander is a practical all-round choice. Start with a coarser grit only when needed, then finish with a finer grit. Wear a dust mask.' },
        { pattern: /lawn|grass|garden|hedge|branch|tree|weed/, reply: 'For lawn work, choose a lawn mower or line trimmer. For hedges, use a hedge trimmer; for thicker branches, a pruning saw is safer than forcing a hedge trimmer. Ask the provider about battery charge or fuel.' },
        { pattern: /concrete|cement|paver|driveway|brick/, reply: 'For small concrete jobs, a concrete mixer can save time. For drilling into masonry, use a hammer drill with masonry bits. For cutting pavers, look for a masonry saw or an angle grinder with the correct blade and safety guard.' },
        { pattern: /plumb|pipe|tap|drain|sink|toilet/, reply: 'For basic pipe work, look for a pipe wrench, adjustable wrench, or drain auger depending on the job. Turn off the water first. If the job involves gas, major leaks, or main plumbing, contact a licensed professional.' },
        { pattern: /car|vehicle|tyre|tire|wheel|oil/, reply: 'For changing a wheel, use a trolley jack and wheel brace only on stable, level ground, and use jack stands before working under a vehicle. Check the tool listing weight rating and your vehicle manual.' }
    ];

    const answer = question => {
        const text = question.toLowerCase();
        const jobMatch = jobSuggestions.find(suggestion => suggestion.pattern.test(text));
        if (jobMatch) return `${jobMatch.reply} You can use Browse Tools to see nearby options.`;
        if (/deposit|security/.test(text)) return 'Toolly adds a refundable security deposit equal to 10% of the tool\'s listed original value. The booking page shows it clearly before you confirm.';
        if (/insurance|cover|damage/.test(text)) return 'Renter insurance is optional. It starts at $5 for a tool under $100 and doubles for each additional $100 of original value. For damage questions, message the provider and keep a record of the tool\'s condition.';
        if (/price|cost|pay|fee/.test(text)) return 'Your total is the daily rental rate multiplied by the number of days, plus the refundable 10% deposit and optional insurance. Toolly shows the full breakdown before booking.';
        if (/available|date|when|long/.test(text)) return 'Each listing shows its available-from and available-until dates. Pick your start and end dates within that period, then confirm the booking.';
        if (/message|provider|owner|contact/.test(text)) return 'Renters can use Message provider on an available listing. Once a conversation is started, both people can reply from the Messages page.';
        if (/safe|safety|danger/.test(text)) return 'Always read the manufacturer instructions, wear suitable protective gear, inspect the tool before use, and stop if anything looks damaged or unsafe.';
        return 'Tell me what job you are doing, such as painting a room, cutting timber, drilling into a wall, mowing a lawn, laying tiles, sanding furniture, or fixing a pipe. I can suggest a suitable tool.';
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
