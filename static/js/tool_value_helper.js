document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-tool-value-form]').forEach((form) => {
        const typeInput = form.querySelector('[name="tool_type"]');
        const conditionInput = form.querySelector('[name="tool_condition"]');
        const valueInput = form.querySelector('[name="original_value"]');
        const suggestion = form.querySelector('[data-value-suggestion]');
        const baseValues = [
            ['pressure washer', 350], ['lawn mower', 450], ['hedge trimmer', 200],
            ['mitre saw', 400], ['circular saw', 220], ['jigsaw', 130],
            ['angle grinder', 160], ['generator', 900], ['drill', 180],
            ['sander', 150], ['ladder', 180]
        ];
        const conditionMultipliers = { 'New': 1, 'Excellent': 0.8, 'Good': 0.65, 'Fair': 0.45 };

        function updateSuggestion() {
            const type = typeInput.value.trim().toLowerCase();
            const match = baseValues.find(([keyword]) => type.includes(keyword));
            const baseValue = match ? match[1] : 200;
            const multiplier = conditionMultipliers[conditionInput.value] || 1;
            const suggestedValue = baseValue * multiplier;
            suggestion.textContent = `Suggested original value: $${suggestedValue.toFixed(2)}. You can change this amount.`;
            if (!valueInput.value || valueInput.dataset.suggested === 'true') {
                valueInput.value = suggestedValue.toFixed(2);
                valueInput.dataset.suggested = 'true';
            }
        }

        valueInput.addEventListener('input', () => { valueInput.dataset.suggested = 'false'; });
        typeInput.addEventListener('input', updateSuggestion);
        conditionInput.addEventListener('change', updateSuggestion);
        updateSuggestion();
    });
});
