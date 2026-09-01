document.addEventListener('DOMContentLoaded', () => {
    const cityLgas = {
        'Brisbane': 'BRISBANE CITY',
        'Gold Coast': 'GOLD COAST CITY',
        'Sunshine Coast': 'SUNSHINE COAST REGIONAL'
    };
    const localityApi = 'https://spatial-gis.information.qld.gov.au/arcgis/rest/services/Boundaries/AdministrativeBoundaries/MapServer/2/query';
    const suburbCache = {};

    async function getSuburbs(city) {
        if (!city) return [];
        if (suburbCache[city]) return suburbCache[city];
        const parameters = new URLSearchParams({
            f: 'json',
            where: `lga = '${cityLgas[city]}'`,
            outFields: 'locality',
            returnGeometry: 'false',
            orderByFields: 'locality',
            resultRecordCount: '1000'
        });
        try {
            const response = await fetch(`${localityApi}?${parameters}`);
            const data = await response.json();
            suburbCache[city] = [...new Set((data.features || []).map((feature) => feature.attributes.locality).filter(Boolean))];
        } catch (error) {
            suburbCache[city] = [];
        }
        return suburbCache[city];
    }

    document.querySelectorAll('[data-location-city]').forEach((citySelect) => {
        const form = citySelect.closest('form');
        const suburbSelect = form.querySelector('[data-location-suburb]');
        const selectedCity = citySelect.dataset.selected || '';
        const selectedSuburb = suburbSelect.dataset.selected || '';
        const firstCityLabel = citySelect.options[0].text;
        const firstSuburbLabel = suburbSelect.options[0].text;

        citySelect.innerHTML = `<option value="">${firstCityLabel}</option>`;
        Object.keys(cityLgas).forEach((city) => {
            const option = new Option(city, city, false, city === selectedCity);
            citySelect.add(option);
        });

        const fillSuburbs = async () => {
            const city = citySelect.value;
            suburbSelect.disabled = true;
            suburbSelect.innerHTML = `<option value="">${city ? 'Loading suburbs…' : 'Choose a city first'}</option>`;
            const suburbs = await getSuburbs(city);
            suburbSelect.innerHTML = `<option value="">${city ? firstSuburbLabel : 'Choose a city first'}</option>`;
            suburbs.forEach((suburb) => suburbSelect.add(new Option(suburb, suburb, false, suburb === selectedSuburb)));
            suburbSelect.disabled = !city;
        };

        citySelect.addEventListener('change', () => {
            suburbSelect.dataset.selected = '';
            fillSuburbs();
        });
        fillSuburbs();
    });
});
