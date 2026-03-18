// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.auto-dismiss').forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      bsAlert.close();
    }, 5000);
  });

  // Highlight active nav link
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });
});

// Unit converter: update from/to unit dropdowns based on selected category
const unitOptions = {
  length: [
    ['mm', 'Millimeters (mm)'], ['cm', 'Centimeters (cm)'], ['m', 'Meters (m)'],
    ['km', 'Kilometers (km)'], ['inch', 'Inches (in)'], ['foot', 'Feet (ft)'],
    ['yard', 'Yards (yd)'], ['mile', 'Miles (mi)'],
  ],
  mass: [
    ['mg', 'Milligrams (mg)'], ['g', 'Grams (g)'], ['kg', 'Kilograms (kg)'],
    ['tonne', 'Tonnes (t)'], ['oz', 'Ounces (oz)'], ['lb', 'Pounds (lb)'], ['ton', 'Tons (US)'],
  ],
  temperature: [
    ['celsius', 'Celsius (°C)'], ['fahrenheit', 'Fahrenheit (°F)'], ['kelvin', 'Kelvin (K)'],
  ],
  area: [
    ['mm2', 'mm²'], ['cm2', 'cm²'], ['m2', 'm²'], ['km2', 'km²'],
    ['ft2', 'ft²'], ['acre', 'Acres'], ['hectare', 'Hectares'],
  ],
  volume: [
    ['ml', 'Milliliters (mL)'], ['l', 'Liters (L)'], ['m3', 'm³'],
    ['fl_oz', 'Fluid Ounces'], ['cup', 'Cups'], ['pint', 'Pints'], ['gallon', 'Gallons'],
  ],
  speed: [
    ['m_s', 'm/s'], ['km_h', 'km/h'], ['mph', 'mph'], ['knot', 'Knots'],
  ],
  pressure: [
    ['pa', 'Pascals (Pa)'], ['kpa', 'Kilopascals (kPa)'], ['mpa', 'Megapascals (MPa)'],
    ['bar', 'Bar'], ['psi', 'PSI'], ['atm', 'Atmospheres (atm)'],
  ],
  energy: [
    ['j', 'Joules (J)'], ['kj', 'Kilojoules (kJ)'], ['mj', 'Megajoules (MJ)'],
    ['cal', 'Calories (cal)'], ['kcal', 'Kilocalories (kcal)'],
    ['kwh', 'Kilowatt-hours (kWh)'], ['btu', 'BTU'],
  ],
};

function populateUnits(selectId, options, defaultIndex) {
  const select = document.getElementById(selectId);
  if (!select) return;
  select.innerHTML = '';
  options.forEach(([value, label], i) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    if (i === defaultIndex) opt.selected = true;
    select.appendChild(opt);
  });
}

const categorySelect = document.getElementById('categorySelect');
if (categorySelect) {
  categorySelect.addEventListener('change', () => {
    const opts = unitOptions[categorySelect.value] || [];
    populateUnits('fromUnit', opts, 0);
    populateUnits('toUnit', opts, 1);
  });
  // Initialize on page load
  const opts = unitOptions[categorySelect.value] || [];
  populateUnits('fromUnit', opts, 0);
  populateUnits('toUnit', opts, 1);
}
