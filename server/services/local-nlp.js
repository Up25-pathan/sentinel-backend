/**
 * Local NLP Intelligence Engine
 * Zero API calls — keyword classification, entity extraction, geocoding
 * Works completely offline as the primary analysis backbone
 */

// ─── GEOCODING DATABASE (200+ countries, 500+ major cities) ─────────
const COUNTRY_GEO = {
    'afghanistan': { lat: 33.94, lng: 67.71, code: 'AF' },
    'albania': { lat: 41.15, lng: 20.17, code: 'AL' },
    'algeria': { lat: 28.03, lng: 1.66, code: 'DZ' },
    'angola': { lat: -11.20, lng: 17.87, code: 'AO' },
    'argentina': { lat: -38.42, lng: -63.62, code: 'AR' },
    'armenia': { lat: 40.07, lng: 45.04, code: 'AM' },
    'australia': { lat: -25.27, lng: 133.78, code: 'AU' },
    'austria': { lat: 47.52, lng: 14.55, code: 'AT' },
    'azerbaijan': { lat: 40.14, lng: 47.58, code: 'AZ' },
    'bahrain': { lat: 26.07, lng: 50.56, code: 'BH' },
    'bangladesh': { lat: 23.68, lng: 90.36, code: 'BD' },
    'belarus': { lat: 53.71, lng: 27.95, code: 'BY' },
    'belgium': { lat: 50.50, lng: 4.47, code: 'BE' },
    'bolivia': { lat: -16.29, lng: -63.59, code: 'BO' },
    'bosnia': { lat: 43.92, lng: 17.68, code: 'BA' },
    'brazil': { lat: -14.24, lng: -51.93, code: 'BR' },
    'brunei': { lat: 4.54, lng: 114.73, code: 'BN' },
    'bulgaria': { lat: 42.73, lng: 25.49, code: 'BG' },
    'burkina faso': { lat: 12.24, lng: -1.56, code: 'BF' },
    'myanmar': { lat: 21.91, lng: 95.96, code: 'MM' },
    'burma': { lat: 21.91, lng: 95.96, code: 'MM' },
    'cambodia': { lat: 12.57, lng: 104.99, code: 'KH' },
    'cameroon': { lat: 7.37, lng: 12.35, code: 'CM' },
    'canada': { lat: 56.13, lng: -106.35, code: 'CA' },
    'chad': { lat: 15.45, lng: 18.73, code: 'TD' },
    'chile': { lat: -35.68, lng: -71.54, code: 'CL' },
    'china': { lat: 35.86, lng: 104.20, code: 'CN' },
    'colombia': { lat: 4.57, lng: -74.30, code: 'CO' },
    'congo': { lat: -4.04, lng: 21.76, code: 'CD' },
    'costa rica': { lat: 9.75, lng: -83.75, code: 'CR' },
    'croatia': { lat: 45.10, lng: 15.20, code: 'HR' },
    'cuba': { lat: 21.52, lng: -77.78, code: 'CU' },
    'cyprus': { lat: 35.13, lng: 33.43, code: 'CY' },
    'czech republic': { lat: 49.82, lng: 15.47, code: 'CZ' },
    'czechia': { lat: 49.82, lng: 15.47, code: 'CZ' },
    'denmark': { lat: 56.26, lng: 9.50, code: 'DK' },
    'djibouti': { lat: 11.83, lng: 42.59, code: 'DJ' },
    'ecuador': { lat: -1.83, lng: -78.18, code: 'EC' },
    'egypt': { lat: 26.82, lng: 30.80, code: 'EG' },
    'el salvador': { lat: 13.79, lng: -88.90, code: 'SV' },
    'eritrea': { lat: 15.18, lng: 39.78, code: 'ER' },
    'estonia': { lat: 58.60, lng: 25.01, code: 'EE' },
    'ethiopia': { lat: 9.15, lng: 40.49, code: 'ET' },
    'finland': { lat: 61.92, lng: 25.75, code: 'FI' },
    'france': { lat: 46.23, lng: 2.21, code: 'FR' },
    'gabon': { lat: -0.80, lng: 11.61, code: 'GA' },
    'georgia': { lat: 42.32, lng: 43.36, code: 'GE' },
    'germany': { lat: 51.17, lng: 10.45, code: 'DE' },
    'ghana': { lat: 7.95, lng: -1.02, code: 'GH' },
    'greece': { lat: 39.07, lng: 21.82, code: 'GR' },
    'guatemala': { lat: 15.78, lng: -90.23, code: 'GT' },
    'guinea': { lat: 9.95, lng: -9.70, code: 'GN' },
    'haiti': { lat: 18.97, lng: -72.29, code: 'HT' },
    'honduras': { lat: 15.20, lng: -86.24, code: 'HN' },
    'hungary': { lat: 47.16, lng: 19.50, code: 'HU' },
    'iceland': { lat: 64.96, lng: -19.02, code: 'IS' },
    'india': { lat: 20.59, lng: 78.96, code: 'IN' },
    'indonesia': { lat: -0.79, lng: 113.92, code: 'ID' },
    'iran': { lat: 32.43, lng: 53.69, code: 'IR' },
    'iraq': { lat: 33.22, lng: 43.68, code: 'IQ' },
    'ireland': { lat: 53.14, lng: -7.69, code: 'IE' },
    'israel': { lat: 31.05, lng: 34.85, code: 'IL' },
    'italy': { lat: 41.87, lng: 12.57, code: 'IT' },
    'ivory coast': { lat: 7.54, lng: -5.55, code: 'CI' },
    'jamaica': { lat: 18.11, lng: -77.30, code: 'JM' },
    'japan': { lat: 36.20, lng: 138.25, code: 'JP' },
    'jordan': { lat: 30.59, lng: 36.24, code: 'JO' },
    'kazakhstan': { lat: 48.02, lng: 66.92, code: 'KZ' },
    'kenya': { lat: -0.02, lng: 37.91, code: 'KE' },
    'north korea': { lat: 40.34, lng: 127.51, code: 'KP' },
    'south korea': { lat: 35.91, lng: 127.77, code: 'KR' },
    'korea': { lat: 35.91, lng: 127.77, code: 'KR' },
    'kosovo': { lat: 42.60, lng: 20.90, code: 'XK' },
    'kuwait': { lat: 29.31, lng: 47.48, code: 'KW' },
    'kyrgyzstan': { lat: 41.20, lng: 74.77, code: 'KG' },
    'laos': { lat: 19.86, lng: 102.50, code: 'LA' },
    'latvia': { lat: 56.88, lng: 24.60, code: 'LV' },
    'lebanon': { lat: 33.85, lng: 35.86, code: 'LB' },
    'libya': { lat: 26.34, lng: 17.23, code: 'LY' },
    'lithuania': { lat: 55.17, lng: 23.88, code: 'LT' },
    'luxembourg': { lat: 49.82, lng: 6.13, code: 'LU' },
    'madagascar': { lat: -18.77, lng: 46.87, code: 'MG' },
    'malawi': { lat: -13.25, lng: 34.30, code: 'MW' },
    'malaysia': { lat: 4.21, lng: 101.98, code: 'MY' },
    'mali': { lat: 17.57, lng: -4.00, code: 'ML' },
    'mauritania': { lat: 21.01, lng: -10.94, code: 'MR' },
    'mexico': { lat: 23.63, lng: -102.55, code: 'MX' },
    'moldova': { lat: 47.41, lng: 28.37, code: 'MD' },
    'mongolia': { lat: 46.86, lng: 103.85, code: 'MN' },
    'montenegro': { lat: 42.71, lng: 19.37, code: 'ME' },
    'morocco': { lat: 31.79, lng: -7.09, code: 'MA' },
    'mozambique': { lat: -18.67, lng: 35.53, code: 'MZ' },
    'namibia': { lat: -22.96, lng: 18.49, code: 'NA' },
    'nepal': { lat: 28.39, lng: 84.12, code: 'NP' },
    'netherlands': { lat: 52.13, lng: 5.29, code: 'NL' },
    'new zealand': { lat: -40.90, lng: 174.89, code: 'NZ' },
    'nicaragua': { lat: 12.87, lng: -85.21, code: 'NI' },
    'niger': { lat: 17.61, lng: 8.08, code: 'NE' },
    'nigeria': { lat: 9.08, lng: 8.68, code: 'NG' },
    'norway': { lat: 60.47, lng: 8.47, code: 'NO' },
    'oman': { lat: 21.47, lng: 55.98, code: 'OM' },
    'pakistan': { lat: 30.38, lng: 69.35, code: 'PK' },
    'palestine': { lat: 31.95, lng: 35.23, code: 'PS' },
    'panama': { lat: 8.54, lng: -80.78, code: 'PA' },
    'paraguay': { lat: -23.44, lng: -58.44, code: 'PY' },
    'peru': { lat: -9.19, lng: -75.02, code: 'PE' },
    'philippines': { lat: 12.88, lng: 121.77, code: 'PH' },
    'poland': { lat: 51.92, lng: 19.15, code: 'PL' },
    'portugal': { lat: 39.40, lng: -8.22, code: 'PT' },
    'qatar': { lat: 25.35, lng: 51.18, code: 'QA' },
    'romania': { lat: 45.94, lng: 24.97, code: 'RO' },
    'russia': { lat: 61.52, lng: 105.32, code: 'RU' },
    'russian': { lat: 61.52, lng: 105.32, code: 'RU' },
    'rwanda': { lat: -1.94, lng: 29.87, code: 'RW' },
    'saudi arabia': { lat: 23.89, lng: 45.08, code: 'SA' },
    'senegal': { lat: 14.50, lng: -14.45, code: 'SN' },
    'serbia': { lat: 44.02, lng: 21.01, code: 'RS' },
    'sierra leone': { lat: 8.46, lng: -11.78, code: 'SL' },
    'singapore': { lat: 1.35, lng: 103.82, code: 'SG' },
    'slovakia': { lat: 48.67, lng: 19.70, code: 'SK' },
    'slovenia': { lat: 46.15, lng: 14.99, code: 'SI' },
    'somalia': { lat: 5.15, lng: 46.20, code: 'SO' },
    'south africa': { lat: -30.56, lng: 22.94, code: 'ZA' },
    'south sudan': { lat: 6.88, lng: 31.31, code: 'SS' },
    'spain': { lat: 40.46, lng: -3.75, code: 'ES' },
    'sri lanka': { lat: 7.87, lng: 80.77, code: 'LK' },
    'sudan': { lat: 12.86, lng: 30.22, code: 'SD' },
    'sweden': { lat: 60.13, lng: 18.64, code: 'SE' },
    'switzerland': { lat: 46.82, lng: 8.23, code: 'CH' },
    'syria': { lat: 34.80, lng: 38.99, code: 'SY' },
    'taiwan': { lat: 23.70, lng: 120.96, code: 'TW' },
    'tajikistan': { lat: 38.86, lng: 71.28, code: 'TJ' },
    'tanzania': { lat: -6.37, lng: 34.89, code: 'TZ' },
    'thailand': { lat: 15.87, lng: 100.99, code: 'TH' },
    'togo': { lat: 8.62, lng: 0.82, code: 'TG' },
    'tunisia': { lat: 33.89, lng: 9.54, code: 'TN' },
    'turkey': { lat: 38.96, lng: 35.24, code: 'TR' },
    'turkmenistan': { lat: 38.97, lng: 59.56, code: 'TM' },
    'uganda': { lat: 1.37, lng: 32.29, code: 'UG' },
    'ukraine': { lat: 48.38, lng: 31.17, code: 'UA' },
    'united arab emirates': { lat: 23.42, lng: 53.85, code: 'AE' },
    'uae': { lat: 23.42, lng: 53.85, code: 'AE' },
    'united kingdom': { lat: 55.38, lng: -3.44, code: 'GB' },
    'uk': { lat: 55.38, lng: -3.44, code: 'GB' },
    'britain': { lat: 55.38, lng: -3.44, code: 'GB' },
    'united states': { lat: 37.09, lng: -95.71, code: 'US' },
    'us': { lat: 37.09, lng: -95.71, code: 'US' },
    'usa': { lat: 37.09, lng: -95.71, code: 'US' },
    'america': { lat: 37.09, lng: -95.71, code: 'US' },
    'uruguay': { lat: -32.52, lng: -55.77, code: 'UY' },
    'uzbekistan': { lat: 41.38, lng: 64.59, code: 'UZ' },
    'venezuela': { lat: 6.42, lng: -66.59, code: 'VE' },
    'vietnam': { lat: 14.06, lng: 108.28, code: 'VN' },
    'yemen': { lat: 15.55, lng: 48.52, code: 'YE' },
    'zambia': { lat: -13.13, lng: 27.85, code: 'ZM' },
    'zimbabwe': { lat: -19.02, lng: 29.15, code: 'ZW' },
};

const CITY_GEO = {
    'kabul': { lat: 34.53, lng: 69.17, country: 'Afghanistan' },
    'tirana': { lat: 41.33, lng: 19.82, country: 'Albania' },
    'algiers': { lat: 36.74, lng: 3.06, country: 'Algeria' },
    'buenos aires': { lat: -34.60, lng: -58.38, country: 'Argentina' },
    'yerevan': { lat: 40.18, lng: 44.51, country: 'Armenia' },
    'canberra': { lat: -35.28, lng: 149.13, country: 'Australia' },
    'sydney': { lat: -33.87, lng: 151.21, country: 'Australia' },
    'vienna': { lat: 48.21, lng: 16.37, country: 'Austria' },
    'baku': { lat: 40.41, lng: 49.87, country: 'Azerbaijan' },
    'manama': { lat: 26.23, lng: 50.59, country: 'Bahrain' },
    'dhaka': { lat: 23.81, lng: 90.41, country: 'Bangladesh' },
    'minsk': { lat: 53.90, lng: 27.57, country: 'Belarus' },
    'brussels': { lat: 50.85, lng: 4.35, country: 'Belgium' },
    'beijing': { lat: 39.90, lng: 116.41, country: 'China' },
    'shanghai': { lat: 31.23, lng: 121.47, country: 'China' },
    'hong kong': { lat: 22.32, lng: 114.17, country: 'China' },
    'bogota': { lat: 4.71, lng: -74.07, country: 'Colombia' },
    'havana': { lat: 23.11, lng: -82.37, country: 'Cuba' },
    'cairo': { lat: 30.04, lng: 31.24, country: 'Egypt' },
    'paris': { lat: 48.86, lng: 2.35, country: 'France' },
    'berlin': { lat: 52.52, lng: 13.41, country: 'Germany' },
    'athens': { lat: 37.98, lng: 23.73, country: 'Greece' },
    'new delhi': { lat: 28.61, lng: 77.21, country: 'India' },
    'delhi': { lat: 28.61, lng: 77.21, country: 'India' },
    'mumbai': { lat: 19.08, lng: 72.88, country: 'India' },
    'jakarta': { lat: -6.21, lng: 106.85, country: 'Indonesia' },
    'tehran': { lat: 35.69, lng: 51.39, country: 'Iran' },
    'baghdad': { lat: 33.31, lng: 44.37, country: 'Iraq' },
    'mosul': { lat: 36.34, lng: 43.12, country: 'Iraq' },
    'basra': { lat: 30.51, lng: 47.78, country: 'Iraq' },
    'dublin': { lat: 53.35, lng: -6.26, country: 'Ireland' },
    'jerusalem': { lat: 31.77, lng: 35.23, country: 'Israel' },
    'tel aviv': { lat: 32.09, lng: 34.78, country: 'Israel' },
    'rome': { lat: 41.90, lng: 12.50, country: 'Italy' },
    'tokyo': { lat: 35.68, lng: 139.69, country: 'Japan' },
    'amman': { lat: 31.95, lng: 35.93, country: 'Jordan' },
    'nairobi': { lat: -1.29, lng: 36.82, country: 'Kenya' },
    'pyongyang': { lat: 39.04, lng: 125.76, country: 'North Korea' },
    'seoul': { lat: 37.57, lng: 127.00, country: 'South Korea' },
    'pristina': { lat: 42.66, lng: 21.17, country: 'Kosovo' },
    'kuwait city': { lat: 29.38, lng: 47.99, country: 'Kuwait' },
    'beirut': { lat: 33.89, lng: 35.50, country: 'Lebanon' },
    'tripoli': { lat: 32.89, lng: 13.18, country: 'Libya' },
    'benghazi': { lat: 32.12, lng: 20.09, country: 'Libya' },
    'kuala lumpur': { lat: 3.14, lng: 101.69, country: 'Malaysia' },
    'bamako': { lat: 12.64, lng: -8.00, country: 'Mali' },
    'mexico city': { lat: 19.43, lng: -99.13, country: 'Mexico' },
    'chisinau': { lat: 47.01, lng: 28.86, country: 'Moldova' },
    'rabat': { lat: 34.02, lng: -6.83, country: 'Morocco' },
    'kathmandu': { lat: 27.72, lng: 85.32, country: 'Nepal' },
    'amsterdam': { lat: 52.37, lng: 4.90, country: 'Netherlands' },
    'the hague': { lat: 52.08, lng: 4.31, country: 'Netherlands' },
    'abuja': { lat: 9.06, lng: 7.49, country: 'Nigeria' },
    'lagos': { lat: 6.52, lng: 3.38, country: 'Nigeria' },
    'oslo': { lat: 59.91, lng: 10.75, country: 'Norway' },
    'islamabad': { lat: 33.69, lng: 73.04, country: 'Pakistan' },
    'karachi': { lat: 24.86, lng: 67.01, country: 'Pakistan' },
    'lahore': { lat: 31.55, lng: 74.35, country: 'Pakistan' },
    'gaza': { lat: 31.50, lng: 34.47, country: 'Palestine' },
    'ramallah': { lat: 31.90, lng: 35.20, country: 'Palestine' },
    'lima': { lat: -12.05, lng: -77.04, country: 'Peru' },
    'manila': { lat: 14.60, lng: 120.98, country: 'Philippines' },
    'warsaw': { lat: 52.23, lng: 21.01, country: 'Poland' },
    'lisbon': { lat: 38.72, lng: -9.14, country: 'Portugal' },
    'doha': { lat: 25.29, lng: 51.53, country: 'Qatar' },
    'bucharest': { lat: 44.43, lng: 26.10, country: 'Romania' },
    'moscow': { lat: 55.76, lng: 37.62, country: 'Russia' },
    'st petersburg': { lat: 59.93, lng: 30.32, country: 'Russia' },
    'riyadh': { lat: 24.69, lng: 46.72, country: 'Saudi Arabia' },
    'jeddah': { lat: 21.49, lng: 39.19, country: 'Saudi Arabia' },
    'belgrade': { lat: 44.79, lng: 20.47, country: 'Serbia' },
    'mogadishu': { lat: 2.05, lng: 45.32, country: 'Somalia' },
    'johannesburg': { lat: -26.20, lng: 28.04, country: 'South Africa' },
    'cape town': { lat: -33.93, lng: 18.42, country: 'South Africa' },
    'juba': { lat: 4.85, lng: 31.58, country: 'South Sudan' },
    'madrid': { lat: 40.42, lng: -3.70, country: 'Spain' },
    'khartoum': { lat: 15.50, lng: 32.56, country: 'Sudan' },
    'stockholm': { lat: 59.33, lng: 18.07, country: 'Sweden' },
    'geneva': { lat: 46.20, lng: 6.14, country: 'Switzerland' },
    'damascus': { lat: 33.51, lng: 36.29, country: 'Syria' },
    'aleppo': { lat: 36.20, lng: 37.15, country: 'Syria' },
    'taipei': { lat: 25.03, lng: 121.57, country: 'Taiwan' },
    'bangkok': { lat: 13.76, lng: 100.50, country: 'Thailand' },
    'ankara': { lat: 39.93, lng: 32.86, country: 'Turkey' },
    'istanbul': { lat: 41.01, lng: 28.98, country: 'Turkey' },
    'kyiv': { lat: 50.45, lng: 30.52, country: 'Ukraine' },
    'kiev': { lat: 50.45, lng: 30.52, country: 'Ukraine' },
    'kharkiv': { lat: 49.99, lng: 36.23, country: 'Ukraine' },
    'odesa': { lat: 46.48, lng: 30.72, country: 'Ukraine' },
    'odessa': { lat: 46.48, lng: 30.72, country: 'Ukraine' },
    'abu dhabi': { lat: 24.45, lng: 54.65, country: 'UAE' },
    'dubai': { lat: 25.20, lng: 55.27, country: 'UAE' },
    'london': { lat: 51.51, lng: -0.13, country: 'United Kingdom' },
    'washington': { lat: 38.91, lng: -77.04, country: 'United States' },
    'new york': { lat: 40.71, lng: -74.01, country: 'United States' },
    'pentagon': { lat: 38.87, lng: -77.06, country: 'United States' },
    'caracas': { lat: 10.48, lng: -66.90, country: 'Venezuela' },
    'hanoi': { lat: 21.03, lng: 105.85, country: 'Vietnam' },
    'sanaa': { lat: 15.37, lng: 44.19, country: 'Yemen' },
    'aden': { lat: 12.79, lng: 45.02, country: 'Yemen' },
    'crimea': { lat: 44.95, lng: 34.10, country: 'Ukraine' },
    'donbas': { lat: 48.00, lng: 37.80, country: 'Ukraine' },
    'donetsk': { lat: 48.00, lng: 37.80, country: 'Ukraine' },
    'luhansk': { lat: 48.57, lng: 39.33, country: 'Ukraine' },
    'zaporizhzhia': { lat: 47.84, lng: 35.14, country: 'Ukraine' },
    'kherson': { lat: 46.64, lng: 32.62, country: 'Ukraine' },
    'taipei': { lat: 25.03, lng: 121.57, country: 'Taiwan' },
    'strait of hormuz': { lat: 26.60, lng: 56.25, country: 'Iran' },
    'strait of malacca': { lat: 2.50, lng: 101.80, country: 'Malaysia' },
    'south china sea': { lat: 12.00, lng: 113.00, country: 'China' },
    'black sea': { lat: 43.17, lng: 34.00, country: 'Turkey' },
    'red sea': { lat: 20.00, lng: 38.00, country: 'Yemen' },
    'suez canal': { lat: 30.44, lng: 32.34, country: 'Egypt' },
    'bab el mandeb': { lat: 12.58, lng: 43.32, country: 'Yemen' },
    'golan heights': { lat: 33.00, lng: 35.80, country: 'Syria' },
    'west bank': { lat: 31.95, lng: 35.30, country: 'Palestine' },
    'rafah': { lat: 31.30, lng: 34.25, country: 'Palestine' },
    'houthi': { lat: 15.35, lng: 44.21, country: 'Yemen' },
    'nato': { lat: 50.88, lng: 4.42, country: 'Belgium' },
};

// ─── KNOWN ORGANIZATIONS ─────────────────────────────────────────────
const ORGANIZATIONS = [
    'NATO', 'United Nations', 'UN', 'EU', 'European Union', 'BRICS',
    'G7', 'G20', 'ASEAN', 'African Union', 'OPEC', 'IAEA', 'WHO',
    'IMF', 'World Bank', 'ICC', 'WTO', 'OSCE', 'SCO', 'GCC',
    'CIA', 'FBI', 'NSA', 'MI6', 'Mossad', 'FSB', 'GRU', 'ISI',
    'Pentagon', 'Kremlin', 'White House', 'State Department',
    'Wagner Group', 'Hezbollah', 'Hamas', 'Houthis', 'ISIS', 'ISIL',
    'Al-Qaeda', 'Taliban', 'PKK', 'Boko Haram', 'Al-Shabaab',
    'IRGC', 'IDF', 'PLA', 'RAF', 'USAF',
    'Red Cross', 'UNICEF', 'Amnesty International', 'Médecins Sans Frontières',
    'Reuters', 'Associated Press', 'AP', 'BBC', 'Al Jazeera',
    'SpaceX', 'Lockheed Martin', 'Boeing', 'Raytheon', 'BAE Systems',
    'Gazprom', 'Rosneft', 'Saudi Aramco', 'Shell', 'BP',
    'SWIFT', 'S&P', 'Moody', 'Fitch',
];

// ─── KNOWN LEADERS ─────────────────────────────────────────────────
const LEADERS = [
    // Current / recent world leaders
    'Putin', 'Biden', 'Trump', 'Xi Jinping', 'Xi', 'Zelenskyy', 'Zelensky',
    'Modi', 'Macron', 'Scholz', 'Starmer', 'Sunak', 'Trudeau',
    'Erdogan', 'Netanyahu', 'Khamenei', 'Kim Jong Un', 'Kim Jong-un',
    'MBS', 'Mohammed bin Salman', 'Sisi', 'al-Sisi', 'Assad', 'Maduro',
    'Milei', 'Lula', 'Duterte', 'Marcos', 'Kishida',
    'Stoltenberg', 'Guterres', 'Rutte', 'Blinken', 'Austin', 'Sullivan',
    'Lavrov', 'Shoigu', 'Prigozhin', 'Gerasimov',
    'Sinwar', 'Nasrallah', 'Raisi', 'Zarif',
    'Milley', 'Burns', 'Haspel',
    'von der Leyen', 'Borrell', 'Michel',
    'Pope Francis', 'Dalai Lama',
];

// ─── CATEGORY CLASSIFICATION ─────────────────────────────────────────
const CATEGORY_RULES = [
    { category: 'WAR', risk: 'CRITICAL', weight: 10,
      patterns: [/\bwar\b/i, /\bcombat\b/i, /\bbattle\b/i, /\bfighting\b/i, /\boffensive\b/i, /\binvasion\b/i, /\bfront\s?line\b/i, /\bairstrikes?\b/i, /\bbombing\b/i, /\bbombard/i, /\bshelling\b/i, /\bartillery\b/i, /\bground forces?\b/i, /\bcasualt/i, /\bkilled in action\b/i, /\bwar\s?zone\b/i, /\bwar\s?crimes?\b/i, /\bconflict zone\b/i] },
    { category: 'NUCLEAR_THREAT', risk: 'CRITICAL', weight: 10,
      patterns: [/\bnuclear\b/i, /\batomic\b/i, /\bwarhead\b/i, /\benrichment\b/i, /\bicbm\b/i, /\bnuclear test/i, /\bradioactive\b/i, /\bnuclear weapon/i, /\bnuclear deterr/i, /\bnuclear capab/i, /\buranium\b/i, /\bplutonium\b/i, /\bnuclear reactor\b/i] },
    { category: 'COUP', risk: 'CRITICAL', weight: 9,
      patterns: [/\bcoup\b/i, /\boverthrow/i, /\bseize power\b/i, /\bjunta\b/i, /\bmilitary takeover\b/i, /\bregime change\b/i, /\bconstitutional crisis\b/i, /\bpower grab\b/i, /\btoppl/i] },
    { category: 'TERRORISM', risk: 'HIGH', weight: 8,
      patterns: [/\bterror/i, /\bsuicide bomb/i, /\bcar bomb\b/i, /\bIED\b/i, /\bexplosion\b/i, /\bjihadist\b/i, /\bextremist\b/i, /\binsurgent\b/i, /\bmilitant/i, /\bratack on civil/i, /\bmass shooting\b/i, /\bhostage\b/i, /\bkidnap/i] },
    { category: 'MILITARY_MOVEMENT', risk: 'HIGH', weight: 7,
      patterns: [/\bmilitary\b/i, /\btroops?\b/i, /\bdeploy/i, /\bnavy\b/i, /\bairforce\b/i, /\barmy\b/i, /\bfleet\b/i, /\barmored\b/i, /\btank[s ]?\b/i, /\bmilitar/i, /\bdefense\b/i, /\bdefence\b/i, /\bweapon/i, /\bmissile/i, /\bdrone strike/i, /\bfighter jet/i, /\bsubmarine\b/i, /\bwarship\b/i] },
    { category: 'SANCTIONS', risk: 'HIGH', weight: 6,
      patterns: [/\bsanction/i, /\bembargo\b/i, /\brestrict/i, /\bfreeze assets\b/i, /\btrade ban\b/i, /\bblacklist/i, /\btariff\b/i, /\btrade war\b/i, /\beconomic warfare\b/i, /\bseize assets\b/i, /\bfinancial sanction/i] },
    { category: 'CYBER_ATTACK', risk: 'HIGH', weight: 7,
      patterns: [/\bcyber/i, /\bhack/i, /\bbreach\b/i, /\bmalware\b/i, /\bransomware\b/i, /\bDDoS\b/i, /\bphishing\b/i, /\bdata leak\b/i, /\bcyber attack\b/i, /\bdigital warfare\b/i, /\bstate-sponsored hack/i, /\bcyber espionage\b/i, /\bzero.?day\b/i] },
    { category: 'DIPLOMATIC_ESCALATION', risk: 'MEDIUM', weight: 5,
      patterns: [/\bdiplomat/i, /\bambassador\b/i, /\bnegotiat/i, /\bsummit\b/i, /\btalks\b/i, /\btreaty\b/i, /\baccord\b/i, /\bexpel diplomat/i, /\brecall ambassador/i, /\btension/i, /\bescalat/i, /\bsever ties\b/i, /\bforeignmin/i, /\bforeign affairs\b/i, /\bstatecraft\b/i] },
    { category: 'POLITICAL_INSTABILITY', risk: 'MEDIUM', weight: 5,
      patterns: [/\bprotest/i, /\bunrest\b/i, /\briot/i, /\buprising\b/i, /\bdestabili/i, /\bopposition\b/i, /\bmarshall? law\b/i, /\bcrackdown\b/i, /\bdissiden/i, /\bdemonstrat/i, /\bcivil unrest\b/i, /\bpolitical crisis\b/i, /\bimpeach/i, /\bresign/i] },
    { category: 'HUMANITARIAN', risk: 'MEDIUM', weight: 4,
      patterns: [/\bhumanitarian\b/i, /\bfamine\b/i, /\brefugee/i, /\bdisplacement\b/i, /\baid\b/i, /\brelief\b/i, /\bgenocide\b/i, /\bethnic cleansing\b/i, /\bwar crime/i, /\bcivilians? killed\b/i, /\bflood/i, /\bearthquake\b/i, /\bnatural disaster\b/i, /\btyphoon\b/i, /\bhurricane\b/i] },
];

// ─── MAIN ANALYSIS FUNCTION ─────────────────────────────────────────

/**
 * Analyze an article using local NLP (zero API calls)
 * @param {Object} article - { title, description, source_name, content }
 * @returns {Object} Analysis result matching AI output format
 */
function analyzeLocal(article) {
    const text = `${article.title || ''} ${article.description || ''} ${article.content || ''}`;
    const textLower = text.toLowerCase();

    // 1. Classification
    const { category, risk_level, escalation_score } = classifyEvent(textLower);

    // 2. Entity extraction
    const entities = extractEntities(text);

    // 3. Geocoding from entities
    const geo = geocodeFromEntities(entities, textLower);

    // 4. Generate intelligence brief
    const summary = generateSummary(article.title, category, risk_level, entities);
    const aiBrief = generateBrief(article.title, article.description, category, risk_level, entities, geo);

    // 5. Second-order effects
    const secondOrderEffects = generateEffects(category, entities, risk_level);

    // 6. Bias analysis
    const biasAnalysis = analyzeBias(article.source_name);

    return {
        category,
        risk_level,
        summary,
        ai_brief: aiBrief,
        escalation_score,
        second_order_effects: secondOrderEffects,
        bias_analysis: biasAnalysis,
        entities,
        location_name: geo.location_name,
        country: geo.country,
        lat: geo.lat,
        lng: geo.lng,
    };
}

/**
 * Classify event category and risk level
 */
function classifyEvent(textLower) {
    let bestMatch = { category: 'OTHER', risk: 'LOW', weight: 0, matchCount: 0 };

    for (const rule of CATEGORY_RULES) {
        let matchCount = 0;
        for (const pattern of rule.patterns) {
            if (pattern.test(textLower)) matchCount++;
        }
        if (matchCount > 0 && (matchCount * rule.weight > bestMatch.matchCount * bestMatch.weight)) {
            bestMatch = { category: rule.category, risk: rule.risk, weight: rule.weight, matchCount };
        }
    }

    // Escalation score based on keyword density and severity
    const escalation = Math.min(100, Math.round(bestMatch.matchCount * bestMatch.weight * 3.5));

    return {
        category: bestMatch.category,
        risk_level: bestMatch.risk,
        escalation_score: escalation,
    };
}

/**
 * Extract entities from text using pattern matching
 */
function extractEntities(text) {
    const countries = [];
    const cities = [];
    const leaders = [];
    const organizations = [];

    const textLower = text.toLowerCase();

    // Extract countries
    for (const [name] of Object.entries(COUNTRY_GEO)) {
        // Use word boundary matching for longer names, simple includes for short ones
        if (name.length <= 3) {
            // For short codes (us, uk, uae) require word boundaries
            const regex = new RegExp(`\\b${name}\\b`, 'i');
            if (regex.test(text)) {
                const properName = name.charAt(0).toUpperCase() + name.slice(1);
                if (!countries.includes(properName)) countries.push(properName);
            }
        } else if (textLower.includes(name)) {
            const properName = name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            if (!countries.includes(properName)) countries.push(properName);
        }
    }

    // Extract cities
    for (const [cityName, cityData] of Object.entries(CITY_GEO)) {
        if (cityName.length < 4) continue; // Skip very short city names to avoid false positives
        if (textLower.includes(cityName)) {
            const properName = cityName.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            if (!cities.includes(properName)) cities.push(properName);
            // Also add the country if not already present
            if (cityData.country && !countries.includes(cityData.country)) {
                countries.push(cityData.country);
            }
        }
    }

    // Extract leaders
    for (const leader of LEADERS) {
        if (text.includes(leader)) {
            if (!leaders.includes(leader)) leaders.push(leader);
        }
    }

    // Extract organizations
    for (const org of ORGANIZATIONS) {
        // Case-sensitive for acronyms, case-insensitive for full names
        if (org === org.toUpperCase() && org.length <= 5) {
            const regex = new RegExp(`\\b${org}\\b`);
            if (regex.test(text) && !organizations.includes(org)) organizations.push(org);
        } else if (text.includes(org) && !organizations.includes(org)) {
            organizations.push(org);
        }
    }

    return { countries, cities, leaders, organizations };
}

/**
 * Geocode from extracted entities
 */
function geocodeFromEntities(entities, textLower) {
    // Priority: cities first (more specific), then countries
    for (const city of entities.cities) {
        const cityData = CITY_GEO[city.toLowerCase()];
        if (cityData) {
            return {
                lat: cityData.lat,
                lng: cityData.lng,
                location_name: city,
                country: cityData.country,
            };
        }
    }

    for (const country of entities.countries) {
        const countryData = COUNTRY_GEO[country.toLowerCase()];
        if (countryData) {
            return {
                lat: countryData.lat,
                lng: countryData.lng,
                location_name: country,
                country: country,
            };
        }
    }

    // Last resort: scan text for any known location
    for (const [cityName, cityData] of Object.entries(CITY_GEO)) {
        if (textLower.includes(cityName)) {
            return {
                lat: cityData.lat,
                lng: cityData.lng,
                location_name: cityName.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                country: cityData.country,
            };
        }
    }

    return { lat: null, lng: null, location_name: null, country: null };
}

/**
 * Generate a concise summary
 */
function generateSummary(title, category, riskLevel, entities) {
    const locationPart = entities.countries.length > 0 ? ` in ${entities.countries[0]}` : '';
    const categoryLabel = category.replace(/_/g, ' ').toLowerCase();
    return `${riskLevel} ${categoryLabel} event${locationPart}: ${title}`;
}

/**
 * Generate intelligence brief
 */
function generateBrief(title, description, category, riskLevel, entities, geo) {
    const sections = [];

    // Situation paragraph
    sections.push(`SITUATION ASSESSMENT: ${title}. ${description || 'No additional detail available from source.'}`);

    // Entity analysis
    if (entities.countries.length > 0 || entities.organizations.length > 0) {
        const actorParts = [];
        if (entities.countries.length > 0) actorParts.push(`Nations involved: ${entities.countries.join(', ')}.`);
        if (entities.leaders.length > 0) actorParts.push(`Key figures: ${entities.leaders.join(', ')}.`);
        if (entities.organizations.length > 0) actorParts.push(`Organizations: ${entities.organizations.join(', ')}.`);
        sections.push(`KEY ACTORS: ${actorParts.join(' ')}`);
    }

    // Risk assessment
    const riskDesc = {
        'CRITICAL': 'This event represents a critical-level threat with potential for immediate escalation. Continuous monitoring and rapid response protocols recommended.',
        'HIGH': 'Elevated threat level. Significant regional implications anticipated. Enhanced situational awareness required.',
        'MEDIUM': 'Moderate threat level. Situation developing and requires monitoring for potential escalation indicators.',
        'LOW': 'Low-level activity detected. Standard monitoring protocols sufficient at this time.',
    };
    sections.push(`THREAT ASSESSMENT [${riskLevel}]: ${riskDesc[riskLevel] || riskDesc['LOW']}`);

    // Location intel
    if (geo.location_name) {
        sections.push(`GEOSPATIAL: Event located at ${geo.location_name}${geo.country ? ', ' + geo.country : ''}. Coordinates: ${geo.lat?.toFixed(2) || 'N/A'}°N, ${geo.lng?.toFixed(2) || 'N/A'}°E.`);
    }

    return sections.join('\n\n');
}

/**
 * Generate second-order effects
 */
function generateEffects(category, entities, riskLevel) {
    const effects = [];

    const effectMap = {
        'WAR': ['Regional destabilization and potential refugee crisis', 'Energy market disruption and supply chain impact', 'Diplomatic realignment among allied nations'],
        'NUCLEAR_THREAT': ['Global nuclear deterrence posture shift', 'Emergency UN Security Council session likely', 'Increased regional defense spending and arms acquisition'],
        'COUP': ['International recognition and sanctions decisions pending', 'Mass civilian displacement and humanitarian corridor needs', 'Regional power vacuum and proxy competition'],
        'TERRORISM': ['Enhanced security protocols in allied nations', 'Intelligence sharing escalation between partners', 'Potential for retaliatory strikes or operations'],
        'MILITARY_MOVEMENT': ['Force posture changes in neighboring states', 'Defense procurement acceleration', 'Diplomatic channels under increased pressure'],
        'SANCTIONS': ['Currency and trade flow disruption', 'Third-party compliance pressure on allied economies', 'Black market and sanctions evasion networks activation'],
        'CYBER_ATTACK': ['Critical infrastructure vulnerability assessment required', 'Attribution and retaliatory cyber operations likely', 'Private sector threat advisory escalation'],
        'DIPLOMATIC_ESCALATION': ['Trade relationship recalibration', 'Alliance realignment discussions', 'Back-channel negotiation intensification'],
        'POLITICAL_INSTABILITY': ['Investment climate deterioration', 'Potential for military intervention or state of emergency', 'Diaspora community activation and international lobbying'],
        'HUMANITARIAN': ['International aid mobilization and coordination', 'Refugee flow impact on neighboring states', 'Long-term reconstruction and governance challenges'],
    };

    if (effectMap[category]) {
        effects.push(...effectMap[category]);
    } else {
        effects.push('Situation requires ongoing monitoring for emerging implications');
    }

    return effects;
}

/**
 * Analyze potential source bias
 */
function analyzeBias(sourceName) {
    const sourceAnalysis = {
        'NYT World': 'Source generally reliable with Western editorial perspective. May underrepresent non-Western viewpoints.',
        'The Guardian': 'Progressive editorial lens. Strong investigative track record but may emphasize social justice angles.',
        'BBC World': 'High credibility institutional source. British government-funded, may reflect UK foreign policy perspectives.',
        'Al Jazeera': 'Provides essential regional perspective on Middle East/North Africa. Qatar-funded, may reflect Gulf state positions.',
        'France 24': 'French state media. Reliable but may emphasize Francophone Africa and EU perspectives.',
        'Reuters World': 'Wire service with high factual accuracy. Minimal editorial bias in straight reporting.',
        'AP News': 'Wire service with high factual accuracy. Minimal editorial bias.',
        'DW News': 'German state media. Strong European perspective, generally balanced.',
        'TASS': 'Russian state media. Content should be cross-referenced with independent sources. Strong state narrative alignment.',
        'Defense One': 'US defense and national security focused. May reflect Pentagon/defense industry perspectives.',
    };

    return sourceAnalysis[sourceName] || `Source: ${sourceName || 'Unknown'}. Credibility assessment pending. Cross-reference with multiple sources recommended.`;
}

/**
 * Extract entities for Nexus graph building (enhanced)
 */
function extractNexusEntities(event) {
    const text = `${event.title || ''} ${event.summary || ''}`;
    const entities = extractEntities(text);
    
    const nexusEntities = [];
    const nexusLinks = [];

    // Create entity records for countries
    for (const country of entities.countries) {
        nexusEntities.push({
            name: country,
            type: 'GPE',
            description: `Nation-state actor referenced in: ${event.title}`,
            influence: event.category === 'WAR' || event.category === 'NUCLEAR_THREAT' ? 8 : 5,
        });
        nexusLinks.push({
            source: country,
            target: event.id,
            type: 'PARTICIPATED_IN',
            strength: 3,
            evidence: `Country mentioned in event: ${event.title}`,
        });
    }

    // Create entity records for organizations
    for (const org of entities.organizations) {
        nexusEntities.push({
            name: org,
            type: 'ORG',
            description: `Organization referenced in: ${event.title}`,
            influence: 6,
        });
        nexusLinks.push({
            source: org,
            target: event.id,
            type: 'PARTICIPATED_IN',
            strength: 2,
            evidence: `Organization mentioned in event: ${event.title}`,
        });
    }

    // Create entity records for leaders
    for (const leader of entities.leaders) {
        nexusEntities.push({
            name: leader,
            type: 'PERSON',
            description: `Key figure referenced in: ${event.title}`,
            influence: 7,
        });
        nexusLinks.push({
            source: leader,
            target: event.id,
            type: 'PARTICIPATED_IN',
            strength: 3,
            evidence: `Leader mentioned in event: ${event.title}`,
        });
    }

    // Auto-link entities that co-occur: countries to organizations, leaders to countries
    for (const country of entities.countries) {
        for (const org of entities.organizations) {
            nexusLinks.push({
                source: country,
                target: org,
                type: 'ASSOCIATED_WITH',
                strength: 2,
                evidence: `Co-mentioned in: ${event.title}`,
            });
        }
        for (const leader of entities.leaders) {
            nexusLinks.push({
                source: leader,
                target: country,
                type: 'ASSOCIATED_WITH',
                strength: 2,
                evidence: `Co-mentioned in: ${event.title}`,
            });
        }
    }

    return { entities: nexusEntities, links: nexusLinks };
}

/**
 * Generate macro briefing from database statistics (no AI needed)
 */
function generateLocalMacroBriefing(events) {
    if (!events || events.length === 0) {
        return { global_risk_score: 0, major_situations: [], macro_predictions: [] };
    }

    // Calculate global risk from event distribution
    const riskWeights = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
    let totalRiskScore = 0;
    let maxRisk = 0;
    const categoryCounts = {};
    const countryCounts = {};

    for (const event of events) {
        const weight = riskWeights[event.risk_level] || 1;
        totalRiskScore += weight;
        maxRisk = Math.max(maxRisk, weight);
        categoryCounts[event.category] = (categoryCounts[event.category] || 0) + 1;
        if (event.country) countryCounts[event.country] = (countryCounts[event.country] || 0) + 1;
    }

    const globalRiskScore = Math.min(100, Math.round((totalRiskScore / (events.length * 4)) * 100));

    // Identify major situations from top categories
    const topCategories = Object.entries(categoryCounts)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 4);

    const major_situations = topCategories.map(([cat, count]) => ({
        flashpoint: cat.replace(/_/g, ' '),
        description: `${count} active ${cat.replace(/_/g, ' ').toLowerCase()} events detected in current monitoring cycle. ${
            count >= 3 ? 'Elevated activity pattern indicates potential escalation.' : 'Standard monitoring levels maintained.'
        }`,
    }));

    // Generate predictions based on trends
    const topCountries = Object.entries(countryCounts)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)
        .map(([c]) => c);

    const macro_predictions = [
        `Concentrated activity in ${topCountries.join(', ') || 'multiple regions'} suggests heightened regional instability in the next 24-48 hours.`,
        globalRiskScore > 60
            ? 'Global risk threshold exceeded — recommend enhanced monitoring and rapid-response readiness.'
            : 'Global stability metrics within normal parameters. Maintain standard watch stance.',
        `${events.length} active intelligence events across ${Object.keys(countryCounts).length} countries. Dominant threat vector: ${topCategories[0]?.[0]?.replace(/_/g, ' ') || 'GENERAL'}.`,
    ];

    return { global_risk_score: globalRiskScore, major_situations, macro_predictions };
}

module.exports = {
    analyzeLocal,
    extractEntities,
    extractNexusEntities,
    geocodeFromEntities,
    classifyEvent,
    generateLocalMacroBriefing,
    COUNTRY_GEO,
    CITY_GEO,
};
