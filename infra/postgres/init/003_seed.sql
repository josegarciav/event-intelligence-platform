-- ============================================================
-- COUNTRY CODES SEED
-- ============================================================

INSERT INTO country_codes (
    country_code,
    country_name,
    iso3_code,
    numeric_code,
    region,
    subregion
) VALUES
('ES', 'Spain', 'ESP', 724, 'Europe', 'Southern Europe'),
('US', 'United States', 'USA', 840, 'Americas', 'Northern America'),
('GB', 'United Kingdom', 'GBR', 826, 'Europe', 'Northern Europe'),
('FR', 'France', 'FRA', 250, 'Europe', 'Western Europe'),
('DE', 'Germany', 'DEU', 276, 'Europe', 'Western Europe'),
('IT', 'Italy', 'ITA', 380, 'Europe', 'Southern Europe'),
('NL', 'Netherlands', 'NLD', 528, 'Europe', 'Western Europe'),
('PT', 'Portugal', 'PRT', 620, 'Europe', 'Southern Europe'),
('BE', 'Belgium', 'BEL', 56, 'Europe', 'Western Europe'),
('CH', 'Switzerland', 'CHE', 756, 'Europe', 'Western Europe'),
('AT', 'Austria', 'AUT', 40, 'Europe', 'Western Europe'),
('SE', 'Sweden', 'SWE', 752, 'Europe', 'Northern Europe'),
('NO', 'Norway', 'NOR', 578, 'Europe', 'Northern Europe'),
('DK', 'Denmark', 'DNK', 208, 'Europe', 'Northern Europe'),
('FI', 'Finland', 'FIN', 246, 'Europe', 'Northern Europe'),
('PL', 'Poland', 'POL', 616, 'Europe', 'Eastern Europe'),
('IE', 'Ireland', 'IRL', 372, 'Europe', 'Northern Europe'),
('CA', 'Canada', 'CAN', 124, 'Americas', 'Northern America'),
('MX', 'Mexico', 'MEX', 484, 'Americas', 'Central America'),
('BR', 'Brazil', 'BRA', 76, 'Americas', 'South America'),
('AR', 'Argentina', 'ARG', 32, 'Americas', 'South America'),
('CO', 'Colombia', 'COL', 170, 'Americas', 'South America'),
('CL', 'Chile', 'CHL', 152, 'Americas', 'South America'),
('PE', 'Peru', 'PER', 604, 'Americas', 'South America'),
('AU', 'Australia', 'AUS', 36, 'Oceania', 'Australia and New Zealand'),
('NZ', 'New Zealand', 'NZL', 554, 'Oceania', 'Australia and New Zealand'),
('JP', 'Japan', 'JPN', 392, 'Asia', 'Eastern Asia'),
('KR', 'South Korea', 'KOR', 410, 'Asia', 'Eastern Asia'),
('CN', 'China', 'CHN', 156, 'Asia', 'Eastern Asia'),
('IN', 'India', 'IND', 356, 'Asia', 'Southern Asia'),
('SG', 'Singapore', 'SGP', 702, 'Asia', 'South-Eastern Asia'),
('AE', 'United Arab Emirates', 'ARE', 784, 'Asia', 'Western Asia'),
('ZA', 'South Africa', 'ZAF', 710, 'Africa', 'Southern Africa')
ON CONFLICT (country_code) DO NOTHING;



-- ============================================================
-- CURRENCY CODES SEED
-- ============================================================

INSERT INTO currency_codes (
    currency_code,
    currency_name,
    symbol,
    numeric_code,
    minor_unit
) VALUES
('EUR', 'Euro', '€', 978, 2),
('USD', 'US Dollar', '$', 840, 2),
('GBP', 'Pound Sterling', '£', 826, 2),
('CHF', 'Swiss Franc', 'CHF', 756, 2),
('SEK', 'Swedish Krona', 'kr', 752, 2),
('NOK', 'Norwegian Krone', 'kr', 578, 2),
('DKK', 'Danish Krone', 'kr', 208, 2),
('PLN', 'Polish Zloty', 'zł', 985, 2),
('CAD', 'Canadian Dollar', '$', 124, 2),
('AUD', 'Australian Dollar', '$', 36, 2),
('NZD', 'New Zealand Dollar', '$', 554, 2),
('JPY', 'Japanese Yen', '¥', 392, 0),
('CNY', 'Chinese Yuan', '¥', 156, 2),
('INR', 'Indian Rupee', '₹', 356, 2),
('KRW', 'South Korean Won', '₩', 410, 0),
('SGD', 'Singapore Dollar', '$', 702, 2),
('AED', 'UAE Dirham', 'د.إ', 784, 2),
('BRL', 'Brazilian Real', 'R$', 986, 2),
('MXN', 'Mexican Peso', '$', 484, 2),
('ARS', 'Argentine Peso', '$', 32, 2),
('COP', 'Colombian Peso', '$', 170, 2),
('CLP', 'Chilean Peso', '$', 152, 0),
('PEN', 'Peruvian Sol', 'S/', 604, 2),
('ZAR', 'South African Rand', 'R', 710, 2)
ON CONFLICT (currency_code) DO NOTHING;
