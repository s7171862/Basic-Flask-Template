document.addEventListener('DOMContentLoaded', () => {
    const queenslandLocations = {
        'Brisbane': ['Acacia Ridge', 'Albion', 'Algester', 'Annerley', 'Ascot', 'Aspley', 'Auchenflower', 'Bald Hills', 'Banyo', 'Bardon', 'Bellbowrie', 'Belmont', 'Boondall', 'Bowen Hills', 'Bracken Ridge', 'Bridgeman Downs', 'Brisbane City', 'Bulimba', 'Calamvale', 'Camp Hill', 'Cannon Hill', 'Carina', 'Carindale', 'Carseldine', 'Chapel Hill', 'Chermside', 'Chermside West', 'Clayfield', 'Coorparoo', 'Darra', 'Deagon', 'Doolandella', 'Drewvale', 'Durack', 'East Brisbane', 'Eight Mile Plains', 'Enoggera', 'Everton Park', 'Fairfield', 'Ferny Grove', 'Fig Tree Pocket', 'Fortitude Valley', 'Gaythorne', 'Geebung', 'Gordon Park', 'Grange', 'Greenslopes', 'Gumdale', 'Hamilton', 'Hawthorne', 'Hemmant', 'Hendra', 'Highgate Hill', 'Holland Park', 'Indooroopilly', 'Jamboree Heights', 'Kangaroo Point', 'Karana Downs', 'Karawatha', 'Kedron', 'Kelvin Grove', 'Kenmore', 'Kippa-Ring', 'Kuraby', 'Lota', 'Lutwyche', 'Macgregor', 'Manly', 'Mansfield', 'McDowall', 'Mildmay', 'Milton', 'Mitchelton', 'Moggill', 'Moorooka', 'Morningside', 'Mount Coot-tha', 'Mount Gravatt', 'Murarrie', 'Nathan', 'New Farm', 'Newmarket', 'Newstead', 'Nudgee', 'Nundah', 'Paddington', 'Parkinson', 'Petrie Terrace', 'Pinkenba', 'Port of Brisbane', 'Pullenvale', 'Ransome', 'Red Hill', 'Richlands', 'Rochedale', 'Runcorn', 'Salisbury', 'Sandgate', 'Seven Hills', 'Sherwood', 'Shorncliffe', 'Sinnamon Park', 'South Brisbane', 'Spring Hill', 'St Lucia', 'Stafford', 'Stretton', 'Sumner', 'Sunnybank', 'Sunnybank Hills', 'Taringa', 'Teneriffe', 'The Gap', 'Toowong', 'Upper Brookfield', 'Virginia', 'Wacol', 'West End', 'Wilston', 'Windsor', 'Wishart', 'Wolston', 'Wynnum', 'Wynnum West', 'Yeerongpilly', 'Yeronga', 'Zillmere'],
        'Gold Coast': ['Advancetown', 'Arundel', 'Ashmore', 'Benowa', 'Biggera Waters', 'Bilinga', 'Bonogin', 'Broadbeach', 'Broadbeach Waters', 'Burleigh Heads', 'Burleigh Waters', 'Bundall', 'Carrara', 'Chevron Island', 'Chirn Park', 'Coombabah', 'Coolangatta', 'Coomera', 'Currumbin', 'Currumbin Waters', 'Elanora', 'Gaven', 'Gilston', 'Helensvale', 'Highland Park', 'Hollywell', 'Hope Island', 'Jacobs Well', 'Kingsholme', 'Labrador', 'Lower Beechmont', 'Maudsland', 'Mermaid Beach', 'Mermaid Waters', 'Miami', 'Molendinar', 'Mudgeeraba', 'Nerang', 'Nerang South', 'Ninderry', 'Nobby Beach', 'North Tamborine', 'Ormeau', 'Ormeau Hills', 'Oxenford', 'Pacific Pines', 'Palm Beach', 'Paradise Point', 'Parkwood', 'Pimpama', 'Reedy Creek', 'Robina', 'Runaway Bay', 'Sanctuary Cove', 'Southport', 'Stapylton', 'Surfers Paradise', 'Tallebudgera', 'Tallebudgera Valley', 'Tugun', 'Upper Coomera', 'Varsity Lakes', 'West Burleigh', 'Willow Vale', 'Wongawallan', 'Worongary', 'Yatala'],
        'Sunshine Coast': ['Alexandra Headland', 'Baringa', 'Battery Hill', 'Bells Creek', 'Bli Bli', 'Bokarina', 'Boreen Point', 'Buddina', 'Buderim', 'Caloundra', 'Caloundra West', 'Cambroon', 'Chevallum', 'Coolum Beach', 'Cooran', 'Cooroy', 'Currimundi', 'Diddillibah', 'Doonan', 'Eerwah Vale', 'Eumundi', 'Flaxton', 'Forest Glen', 'Glenview', 'Golden Beach', 'Harmony', 'Kawana', 'Kawana Island', 'Kiels Mountain', 'Kings Beach', 'Kuluin', 'Landsborough', 'Little Mountain', 'Mapleton', 'Marcus Beach', 'Maroochydore', 'Minyama', 'Mons', 'Montville', 'Mooloolaba', 'Mountain Creek', 'Mudjimba', 'Nambour', 'Noosa Heads', 'Noosaville', 'Peregian Beach', 'Peregian Springs', 'Pelican Waters', 'Pomona', 'Rosemount', 'Sippy Downs', 'Sunrise Beach', 'Tanawha', 'Tewantin', 'Valdora', 'Warana', 'Weyba Downs', 'Woombye', 'Yandina', 'Yaroomba']
    };

    document.querySelectorAll('[data-location-city]').forEach((citySelect) => {
        const form = citySelect.closest('form');
        const suburbSelect = form.querySelector('[data-location-suburb]');
        const selectedCity = citySelect.dataset.selected || '';
        const selectedSuburb = suburbSelect.dataset.selected || '';
        const firstCityLabel = citySelect.options[0].text;
        const firstSuburbLabel = suburbSelect.options[0].text;

        citySelect.innerHTML = `<option value="">${firstCityLabel}</option>`;
        Object.keys(queenslandLocations).forEach((city) => {
            const option = new Option(city, city, false, city === selectedCity);
            citySelect.add(option);
        });

        const fillSuburbs = () => {
            const city = citySelect.value;
            const suburbs = queenslandLocations[city] || [];
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
