"""
tools/flight_tool.py

AviationStack flight search tool with comprehensive IATA resolution.
Covers all countries and major cities worldwide.
"""

import os
import re
import certifi
import airportsdata
import pycountry
import requests
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY             = os.getenv("AVIATIONSTACK_API_KEY")
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "MAA")
BASE_URL            = "https://api.aviationstack.com/v1/flights"

AIRPORTS = airportsdata.load("IATA")


# Comprehensive Country Aliases

COUNTRY_ALIASES: dict[str, str] = {
    # Americas
    "usa": "US", "u.s.a": "US", "u.s.": "US", "america": "US",
    "united states": "US", "united states of america": "US", "us": "US",
    "canada": "CA", "mexico": "MX",
    "brazil": "BR", "brasil": "BR",
    "argentina": "AR", "chile": "CL", "colombia": "CO",
    "peru": "PE", "venezuela": "VE", "ecuador": "EC",
    "bolivia": "BO", "paraguay": "PY", "uruguay": "UY",
    "guyana": "GY", "suriname": "SR",
    "cuba": "CU", "jamaica": "JM", "haiti": "HT",
    "dominican republic": "DO", "puerto rico": "PR",
    "trinidad and tobago": "TT", "barbados": "BB",
    "panama": "PA", "costa rica": "CR", "guatemala": "GT",
    "honduras": "HN", "el salvador": "SV", "nicaragua": "NI",
    "belize": "BZ",

    # Europe
    "uk": "GB", "u.k.": "GB", "britain": "GB", "england": "GB",
    "great britain": "GB", "united kingdom": "GB",
    "scotland": "GB", "wales": "GB", "northern ireland": "GB",
    "ireland": "IE", "eire": "IE",
    "france": "FR", "germany": "DE", "deutschland": "DE",
    "italy": "IT", "italia": "IT",
    "spain": "ES", "espana": "ES",
    "portugal": "PT", "netherlands": "NL", "holland": "NL",
    "belgium": "BE", "luxembourg": "LU",
    "switzerland": "CH", "austria": "AT",
    "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
    "iceland": "IS",
    "poland": "PL", "czech republic": "CZ", "czechia": "CZ",
    "slovakia": "SK", "hungary": "HU", "romania": "RO",
    "bulgaria": "BG", "serbia": "RS", "croatia": "HR",
    "slovenia": "SI", "bosnia": "BA", "bosnia and herzegovina": "BA",
    "north macedonia": "MK", "albania": "AL", "kosovo": "XK",
    "greece": "GR", "cyprus": "CY", "malta": "MT",
    "estonia": "EE", "latvia": "LV", "lithuania": "LT",
    "belarus": "BY", "ukraine": "UA", "moldova": "MD",
    "russia": "RU", "russian federation": "RU",
    "turkey": "TR", "turkiye": "TR",
    "georgia": "GE", "armenia": "AM", "azerbaijan": "AZ",
    "monaco": "MC", "liechtenstein": "LI", "andorra": "AD",
    "san marino": "SM", "vatican": "VA",

    # Asia
    "india": "IN", "bharat": "IN",
    "china": "CN", "prc": "CN", "peoples republic of china": "CN",
    "hong kong": "HK", "macau": "MO", "macao": "MO",
    "taiwan": "TW", "chinese taipei": "TW",
    "japan": "JP", "nippon": "JP",
    "south korea": "KR", "korea": "KR", "republic of korea": "KR",
    "north korea": "KP", "dprk": "KP",
    "singapore": "SG",
    "malaysia": "MY", "malaya": "MY",
    "indonesia": "ID",
    "philippines": "PH", "pilipinas": "PH",
    "thailand": "TH", "siam": "TH",
    "vietnam": "VN", "viet nam": "VN",
    "cambodia": "KH", "kampuchea": "KH",
    "laos": "LA", "lao": "LA",
    "myanmar": "MM", "burma": "MM",
    "bangladesh": "BD",
    "pakistan": "PK",
    "sri lanka": "LK", "ceylon": "LK",
    "nepal": "NP",
    "bhutan": "BT",
    "maldives": "MV",
    "afghanistan": "AF",
    "iran": "IR", "persia": "IR",
    "iraq": "IQ",
    "syria": "SY",
    "lebanon": "LB",
    "jordan": "JO",
    "israel": "IL",
    "palestine": "PS",
    "saudi arabia": "SA", "ksa": "SA",
    "uae": "AE", "dubai": "AE", "united arab emirates": "AE",
    "qatar": "QA",
    "kuwait": "KW",
    "bahrain": "BH",
    "oman": "OM",
    "yemen": "YE",
    "uzbekistan": "UZ",
    "kazakhstan": "KZ",
    "kyrgyzstan": "KG",
    "tajikistan": "TJ",
    "turkmenistan": "TM",
    "mongolia": "MN",
    "brunei": "BN",
    "timor-leste": "TL", "east timor": "TL",
    "papua new guinea": "PG",

    # Africa
    "nigeria": "NG",
    "ethiopia": "ET", "abyssinia": "ET",
    "egypt": "EG",
    "south africa": "ZA",
    "kenya": "KE",
    "ghana": "GH",
    "tanzania": "TZ",
    "uganda": "UG",
    "mozambique": "MZ",
    "madagascar": "MG",
    "cameroon": "CM",
    "ivory coast": "CI", "cote divoire": "CI",
    "angola": "AO",
    "sudan": "SD",
    "south sudan": "SS",
    "algeria": "DZ",
    "morocco": "MA",
    "tunisia": "TN",
    "libya": "LY",
    "senegal": "SN",
    "mali": "ML",
    "burkina faso": "BF",
    "niger": "NE",
    "chad": "TD",
    "somalia": "SO",
    "eritrea": "ER",
    "djibouti": "DJ",
    "zambia": "ZM",
    "zimbabwe": "ZW",
    "malawi": "MW",
    "botswana": "BW",
    "namibia": "NA",
    "rwanda": "RW",
    "burundi": "BI",
    "congo": "CG", "republic of congo": "CG",
    "democratic republic of congo": "CD", "drc": "CD", "zaire": "CD",
    "gabon": "GA",
    "equatorial guinea": "GQ",
    "central african republic": "CF",
    "sierra leone": "SL",
    "liberia": "LR",
    "guinea": "GN",
    "guinea-bissau": "GW",
    "gambia": "GM",
    "mauritania": "MR",
    "mauritius": "MU",
    "seychelles": "SC",
    "cape verde": "CV", "cabo verde": "CV",
    "sao tome": "ST",
    "comoros": "KM",
    "lesotho": "LS",
    "eswatini": "SZ", "swaziland": "SZ",

    # Oceania
    "australia": "AU", "oz": "AU",
    "new zealand": "NZ", "aotearoa": "NZ",
    "fiji": "FJ",
    "papua new guinea": "PG",
    "solomon islands": "SB",
    "vanuatu": "VU",
    "samoa": "WS",
    "tonga": "TO",
    "kiribati": "KI",
    "micronesia": "FM",
    "palau": "PW",
    "marshall islands": "MH",
    "nauru": "NR",
    "tuvalu": "TV",
}

# Country → Primary Airport

COUNTRY_MAIN_AIRPORT: dict[str, str] = {
    # Asia
    "IN": "DEL", "CN": "PEK", "JP": "NRT", "KR": "ICN",
    "SG": "SIN", "MY": "KUL", "TH": "BKK", "ID": "CGK",
    "PH": "MNL", "VN": "SGN", "BD": "DAC", "PK": "KHI",
    "LK": "CMB", "NP": "KTM", "MM": "RGN", "KH": "PNH",
    "LA": "VTE", "BT": "PBH", "MV": "MLE", "AF": "KBL",
    "IR": "IKA", "IQ": "BGW", "SY": "DAM", "LB": "BEY",
    "JO": "AMM", "IL": "TLV", "SA": "RUH", "AE": "DXB",
    "QA": "DOH", "KW": "KWI", "BH": "BAH", "OM": "MCT",
    "YE": "SAH", "HK": "HKG", "TW": "TPE", "MO": "MFM",
    "KP": "FNJ", "UZ": "TAS", "KZ": "ALA", "KG": "FRU",
    "TJ": "DYU", "TM": "ASB", "MN": "ULN", "GE": "TBS",
    "AM": "EVN", "AZ": "GYD", "BN": "BWN",

    # Europe
    "GB": "LHR", "FR": "CDG", "DE": "FRA", "IT": "FCO",
    "ES": "MAD", "PT": "LIS", "NL": "AMS", "BE": "BRU",
    "CH": "ZRH", "AT": "VIE", "SE": "ARN", "NO": "OSL",
    "DK": "CPH", "FI": "HEL", "IS": "KEF", "IE": "DUB",
    "PL": "WAW", "CZ": "PRG", "SK": "BTS", "HU": "BUD",
    "RO": "OTP", "BG": "SOF", "HR": "ZAG", "RS": "BEG",
    "SI": "LJU", "BA": "SJJ", "MK": "SKP", "AL": "TIA",
    "GR": "ATH", "CY": "LCA", "MT": "MLA",
    "EE": "TLL", "LV": "RIX", "LT": "VNO",
    "BY": "MSQ", "UA": "KBP", "MD": "KIV",
    "RU": "SVO", "TR": "IST", "LU": "LUX",

    # Americas
    "US": "JFK", "CA": "YYZ", "MX": "MEX",
    "BR": "GRU", "AR": "EZE", "CL": "SCL",
    "CO": "BOG", "PE": "LIM", "VE": "CCS",
    "EC": "UIO", "BO": "VVI", "PY": "ASU",
    "UY": "MVD", "CU": "HAV", "JM": "KIN",
    "HT": "PAP", "DO": "SDQ", "PA": "PTY",
    "CR": "SJO", "GT": "GUA", "HN": "TGU",
    "SV": "SAL", "NI": "MGA", "BZ": "BZE",

    # Africa
    "NG": "LOS", "ET": "ADD", "EG": "CAI",
    "ZA": "JNB", "KE": "NBO", "GH": "ACC",
    "TZ": "DAR", "UG": "EBB", "MZ": "MPM",
    "MG": "TNR", "CM": "NSI", "CI": "ABJ",
    "AO": "LAD", "SD": "KRT", "DZ": "ALG",
    "MA": "CMN", "TN": "TUN", "LY": "TIP",
    "SN": "DKR", "ZM": "LUN", "ZW": "HRE",
    "BW": "GBE", "NA": "WDH", "RW": "KGL",
    "SO": "MGQ", "ER": "ASM", "DJ": "JIB",
    "CD": "FIH", "CG": "BZV", "GA": "LBV",
    "MU": "MRU", "SC": "SEZ",

    # Oceania
    "AU": "SYD", "NZ": "AKL", "FJ": "NAN",
    "PG": "POM", "SB": "HIR", "VU": "VLI",
    "WS": "APW", "TO": "TBU",
}

# City → Airport

CITY_MAIN_AIRPORT: dict[str, str] = {
    # India
    "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "bombay": "BOM",
    "kolkata": "CCU", "calcutta": "CCU",
    "chennai": "MAA", "madras": "MAA",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD",
    "ahmedabad": "AMD",
    "pune": "PNQ",
    "jaipur": "JAI",
    "goa": "GOI",
    "kochi": "COK", "cochin": "COK",
    "thiruvananthapuram": "TRV", "trivandrum": "TRV",
    "coimbatore": "CJB",
    "lucknow": "LKO",
    "varanasi": "VNS",
    "amritsar": "ATQ",
    "bhubaneswar": "BBI",
    "nagpur": "NAG",
    "indore": "IDR",
    "patna": "PAT",
    "ranchi": "IXR",
    "chandigarh": "IXC",
    "srinagar": "SXR",
    "leh": "IXL",
    "agra": "AGR",
    "aurangabad": "IXU",
    "mangalore": "IXE",
    "visakhapatnam": "VTZ", "vizag": "VTZ",
    "tiruchirappalli": "TRZ", "trichy": "TRZ",
    "madurai": "IXM",
    "raipur": "RPR",
    "bhopal": "BHO",
    "surat": "STV",
    "vadodara": "BDQ",
    "rajkot": "RAJ",
    "jammu": "IXJ",
    "dibrugarh": "DIB",
    "guwahati": "GAU",
    "imphal": "IMF",
    "port blair": "IXZ",
    "dehradun": "DED",
    "jodhpur": "JDH",
    "udaipur": "UDR",

    # East Asia
    "tokyo": "NRT", "osaka": "KIX", "kyoto": "ITM",
    "sapporo": "CTS", "fukuoka": "FUK", "nagoya": "NGO",
    "hiroshima": "HIJ", "okinawa": "OKA",
    "beijing": "PEK", "peking": "PEK",
    "shanghai": "PVG", "guangzhou": "CAN",
    "shenzhen": "SZX", "chengdu": "CTU",
    "chongqing": "CKG", "wuhan": "WUH",
    "xian": "XIY", "xi'an": "XIY",
    "kunming": "KMG", "hangzhou": "HGH",
    "nanjing": "NKG", "tianjin": "TSN",
    "hong kong": "HKG",
    "macau": "MFM", "macao": "MFM",
    "taipei": "TPE", "kaohsiung": "KHH",
    "seoul": "ICN", "busan": "PUS", "jeju": "CJU",
    "pyongyang": "FNJ",
    "ulaanbaatar": "ULN",

    # Southeast Asia
    "singapore": "SIN",
    "kuala lumpur": "KUL", "kl": "KUL",
    "penang": "PEN", "langkawi": "LGK",
    "kota kinabalu": "BKI", "kuching": "KCH",
    "bangkok": "BKK", "phuket": "HKT",
    "chiang mai": "CNX", "krabi": "KBV",
    "pattaya": "UTP", "hat yai": "HDY",
    "jakarta": "CGK", "bali": "DPS",
    "surabaya": "SUB", "medan": "MES",
    "makassar": "UPG", "yogyakarta": "JOG",
    "manila": "MNL", "cebu": "CEB",
    "davao": "DVO", "clark": "CRK",
    "ho chi minh": "SGN", "saigon": "SGN",
    "hanoi": "HAN", "da nang": "DAD",
    "phnom penh": "PNH", "siem reap": "REP",
    "vientiane": "VTE", "luang prabang": "LPQ",
    "yangon": "RGN", "mandalay": "MDL",
    "naypyidaw": "NYT",
    "dili": "DIL",
    "bandar seri begawan": "BWN",

    # South Asia
    "dhaka": "DAC", "chittagong": "CGP",
    "karachi": "KHI", "lahore": "LHE",
    "islamabad": "ISB", "peshawar": "PEW",
    "quetta": "UET",
    "colombo": "CMB",
    "kathmandu": "KTM",
    "thimphu": "PBH", "paro": "PBH",
    "male": "MLE",
    "kabul": "KBL", "kandahar": "KDH",

    # Middle East
    "dubai": "DXB", "abu dhabi": "AUH",
    "sharjah": "SHJ", "ras al khaimah": "RKT",
    "doha": "DOH",
    "riyadh": "RUH", "jeddah": "JED",
    "medina": "MED", "dammam": "DMM",
    "kuwait city": "KWI",
    "manama": "BAH",
    "muscat": "MCT", "salalah": "SLL",
    "sanaa": "SAH", "aden": "ADE",
    "amman": "AMM", "aqaba": "AQJ",
    "beirut": "BEY",
    "damascus": "DAM", "aleppo": "ALP",
    "baghdad": "BGW", "basra": "BSR",
    "erbil": "EBL",
    "tehran": "IKA", "mashhad": "MHD",
    "isfahan": "IFN", "shiraz": "SYZ",
    "tel aviv": "TLV", "jerusalem": "TLV",
    "haifa": "HFA",

    # Central Asia
    "tashkent": "TAS", "samarkand": "SKD",
    "almaty": "ALA", "nur-sultan": "NQZ", "astana": "NQZ",
    "bishkek": "FRU",
    "dushanbe": "DYU",
    "ashgabat": "ASB",

    # Caucasus
    "tbilisi": "TBS", "batumi": "BUS",
    "yerevan": "EVN",
    "baku": "GYD",

    # Europe — Western
    "london": "LHR", "heathrow": "LHR",
    "gatwick": "LGW", "stansted": "STN",
    "manchester": "MAN", "birmingham": "BHX",
    "edinburgh": "EDI", "glasgow": "GLA",
    "dublin": "DUB",
    "paris": "CDG", "orly": "ORY",
    "lyon": "LYS", "marseille": "MRS",
    "nice": "NCE", "bordeaux": "BOD",
    "toulouse": "TLS", "nantes": "NTE",
    "frankfurt": "FRA", "munich": "MUC",
    "berlin": "BER", "hamburg": "HAM",
    "dusseldorf": "DUS", "cologne": "CGN",
    "stuttgart": "STR", "nuremberg": "NUE",
    "rome": "FCO", "fiumicino": "FCO",
    "milan": "MXP", "venice": "VCE",
    "florence": "FLR", "naples": "NAP",
    "bologna": "BLQ", "turin": "TRN",
    "catania": "CTA", "palermo": "PMO",
    "madrid": "MAD", "barcelona": "BCN",
    "valencia": "VLC", "seville": "SVQ",
    "bilbao": "BIO", "malaga": "AGP",
    "lisbon": "LIS", "porto": "OPO",
    "amsterdam": "AMS",
    "brussels": "BRU",
    "zurich": "ZRH", "geneva": "GVA",
    "vienna": "VIE",
    "stockholm": "ARN",
    "oslo": "OSL",
    "copenhagen": "CPH",
    "helsinki": "HEL",
    "reykjavik": "KEF",
    "athens": "ATH", "thessaloniki": "SKG",
    "nicosia": "LCA", "paphos": "PFO",
    "valletta": "MLA",

    # Europe — Eastern
    "warsaw": "WAW", "krakow": "KRK",
    "prague": "PRG", "brno": "BRQ",
    "bratislava": "BTS",
    "budapest": "BUD",
    "bucharest": "OTP", "cluj-napoca": "CLJ",
    "sofia": "SOF", "varna": "VAR",
    "zagreb": "ZAG", "split": "SPU", "dubrovnik": "DBV",
    "belgrade": "BEG", "novi sad": "BEG",
    "sarajevo": "SJJ",
    "skopje": "SKP",
    "tirana": "TIA",
    "pristina": "PRN",
    "istanbul": "IST", "ankara": "ESB",
    "antalya": "AYT", "izmir": "ADB",
    "kyiv": "KBP", "kiev": "KBP",
    "kharkiv": "HRK", "odessa": "ODS",
    "minsk": "MSQ",
    "chisinau": "KIV",
    "riga": "RIX",
    "tallinn": "TLL",
    "vilnius": "VNO",
    "moscow": "SVO", "saint petersburg": "LED",
    "st petersburg": "LED", "novosibirsk": "OVB",
    "yekaterinburg": "SVX", "kazan": "KZN",
    "vladivostok": "VVO",
    "tbilisi": "TBS",

    # Africa — North
    "cairo": "CAI", "alexandria": "HBE",
    "casablanca": "CMN", "marrakech": "RAK",
    "rabat": "RBA", "fez": "FEZ",
    "tunis": "TUN", "sfax": "SFA",
    "algiers": "ALG", "oran": "ORN",
    "tripoli": "TIP", "benghazi": "BEN",
    "khartoum": "KRT",

    # Africa — Sub-Saharan
    "addis ababa": "ADD",
    "nairobi": "NBO", "mombasa": "MBA",
    "dar es salaam": "DAR",
    "entebbe": "EBB", "kampala": "EBB",
    "lagos": "LOS", "abuja": "ABV",
    "accra": "ACC",
    "dakar": "DKR",
    "johannesburg": "JNB", "cape town": "CPT",
    "durban": "DUR", "pretoria": "PRY",
    "harare": "HRE",
    "lusaka": "LUN",
    "maputo": "MPM",
    "antananarivo": "TNR",
    "douala": "DLA", "yaounde": "YAO",
    "abidjan": "ABJ",
    "luanda": "LAD",
    "kinshasa": "FIH",
    "brazzaville": "BZV",
    "libreville": "LBV",
    "kigali": "KGL",
    "bujumbura": "BJM",
    "mogadishu": "MGQ",
    "asmara": "ASM",
    "djibouti city": "JIB",
    "gaborone": "GBE",
    "windhoek": "WDH",
    "port louis": "MRU",
    "victoria": "SEZ",

    # Oceania
    "sydney": "SYD",
    "melbourne": "MEL",
    "brisbane": "BNE",
    "perth": "PER",
    "adelaide": "ADL",
    "gold coast": "OOL",
    "cairns": "CNS",
    "darwin": "DRW",
    "canberra": "CBR",
    "hobart": "HBA",
    "auckland": "AKL",
    "wellington": "WLG",
    "christchurch": "CHC",
    "queenstown": "ZQN",
    "nadi": "NAN",
    "suva": "SUV",
    "port moresby": "POM",
    "honiara": "HIR",
    "port vila": "VLI",
    "apia": "APW",
    "nuku alofa": "TBU",

    # Americas — North
    "new york": "JFK", "nyc": "JFK",
    "los angeles": "LAX", "la": "LAX",
    "chicago": "ORD",
    "houston": "IAH",
    "dallas": "DFW",
    "miami": "MIA",
    "san francisco": "SFO", "sf": "SFO",
    "seattle": "SEA",
    "boston": "BOS",
    "washington": "IAD", "washington dc": "IAD",
    "washington d.c.": "IAD", "dc": "IAD",
    "atlanta": "ATL",
    "denver": "DEN",
    "las vegas": "LAS",
    "phoenix": "PHX",
    "minneapolis": "MSP",
    "detroit": "DTW",
    "philadelphia": "PHL",
    "orlando": "MCO",
    "new orleans": "MSY",
    "portland": "PDX",
    "salt lake city": "SLC",
    "san diego": "SAN",
    "honolulu": "HNL", "hawaii": "HNL",
    "anchorage": "ANC", "alaska": "ANC",
    "toronto": "YYZ",
    "vancouver": "YVR",
    "montreal": "YUL",
    "calgary": "YYC",
    "edmonton": "YEG",
    "ottawa": "YOW",
    "mexico city": "MEX",
    "cancun": "CUN",
    "guadalajara": "GDL",
    "monterrey": "MTY",

    # Americas — South / Central
    "bogota": "BOG",
    "medellin": "MDE",
    "cali": "CLO",
    "lima": "LIM",
    "quito": "UIO",
    "guayaquil": "GYE",
    "caracas": "CCS",
    "sao paulo": "GRU",
    "rio de janeiro": "GIG", "rio": "GIG",
    "brasilia": "BSB",
    "buenos aires": "EZE",
    "santiago": "SCL",
    "montevideo": "MVD",
    "asuncion": "ASU",
    "la paz": "LPB",
    "santa cruz": "VVI",
    "havana": "HAV",
    "kingston": "KIN",
    "port-au-prince": "PAP",
    "santo domingo": "SDQ",
    "panama city": "PTY",
    "san jose": "SJO",
    "guatemala city": "GUA",
    "tegucigalpa": "TGU",
    "san salvador": "SAL",
    "managua": "MGA",
    "belmopan": "BZE",

    # Caribbean
    "nassau": "NAS",
    "bridgetown": "BGI",
    "port of spain": "POS",
    "castries": "SLU",
}


_STOP_WORDS = {
    "flight", "flights", "ticket", "tickets", "trip", "travel",
    "plan", "complete", "days", "day", "including", "hotel",
    "hotels", "sightseeing", "under", "budget", "info", "information",
    "book", "booking", "cheap", "cheapest", "best", "direct",
    "nonstop", "international", "domestic",
}


# Text helpers

def _clean(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return " ".join(w for w in text.split() if w not in _STOP_WORDS).strip()


# IATA Resolution

def _country_code(text: str) -> str | None:
    text_clean = _clean(text)
    if text_clean in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text_clean]
    try:
        return pycountry.countries.lookup(text_clean).alpha_2
    except LookupError:
        pass
    for country in pycountry.countries:
        if country.name.lower() in text_clean:
            return country.alpha_2
    for alias, code in COUNTRY_ALIASES.items():
        if alias in text_clean:
            return code
    return None


def _airport_in_country(airport: dict, cc: str) -> bool:
    ac = str(airport.get("country", "")).upper().strip()
    if ac == cc:
        return True
    try:
        country = pycountry.countries.get(alpha_2=cc)
        if country and ac.lower() == country.name.lower():
            return True
    except Exception:
        pass
    return False


def _best_airport_for_country(cc: str) -> str | None:
    preferred = COUNTRY_MAIN_AIRPORT.get(cc)
    if preferred and preferred in AIRPORTS:
        return preferred
    candidates: list[tuple[int, str]] = []
    for iata, ap in AIRPORTS.items():
        if not iata or not _airport_in_country(ap, cc):
            continue
        name = str(ap.get("name", "")).lower()
        score = 0
        if "international" in name:
            score += 50
        if "intl" in name:
            score += 40
        if "capital" in name:
            score += 20
        if ap.get("city"):
            score += 5
        candidates.append((score, iata))
    return sorted(candidates, reverse=True)[0][1] if candidates else None


def resolve_iata(location: str) -> str | None:
    """Convert a city / country / alias / IATA string to an IATA code."""
    if not location:
        return None
    raw = location.strip()

    # Already a valid IATA code?
    if re.fullmatch(r"[A-Za-z]{3}", raw):
        code = raw.upper()
        if code in AIRPORTS:
            return code

    clean = _clean(raw)
    if not clean:
        return None

    # Direct city lookup
    if clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[clean]

    # Multi-word city lookup (try progressively shorter suffixes)
    words = clean.split()
    for length in range(len(words), 1, -1):
        phrase = " ".join(words[:length])
        if phrase in CITY_MAIN_AIRPORT:
            return CITY_MAIN_AIRPORT[phrase]

    # Country lookup
    cc = _country_code(clean)
    if cc:
        return _best_airport_for_country(cc)

    # Fuzzy airport-database match
    candidates: list[tuple[int, str]] = []
    for iata, ap in AIRPORTS.items():
        city = str(ap.get("city", "")).lower().strip()
        name = str(ap.get("name", "")).lower().strip()
        score = 0
        if city == clean:
            score += 100
        elif clean in city:
            score += 70
        if clean in name:
            score += 50
        if "international" in name:
            score += 10
        if score:
            candidates.append((score, iata))
    return sorted(candidates, reverse=True)[0][1] if candidates else None


# Route Parsing

def _location_mentions(query: str) -> list[str]:
    q = query.lower()
    seen: list[str] = []

    # Check all city aliases first (longest match wins)
    city_keys_sorted = sorted(CITY_MAIN_AIRPORT.keys(), key=len, reverse=True)
    for city in city_keys_sorted:
        if re.search(rf"\b{re.escape(city)}\b", q) and city not in seen:
            seen.append(city)

    # Check country aliases
    for alias in COUNTRY_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", q) and alias not in seen:
            seen.append(alias)

    # pycountry names
    for country in pycountry.countries:
        name = country.name.lower()
        if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", q) and name not in seen:
            seen.append(name)

    return seen


def parse_route(query: str) -> tuple[str | None, str | None]:
    """Parse a natural-language query and return (dep_iata, arr_iata)."""
    q_lower = query.strip().lower()

    global_kw = [
        "all country", "all countries", "global flight", "global flights",
        "all flight", "all flights", "worldwide flight", "worldwide flights",
    ]
    if any(kw in q_lower for kw in global_kw):
        return None, None

    # Bare IATA codes e.g. "DAC to NRT"
    codes = re.findall(r"\b[A-Z]{3}\b", query)
    if len(codes) >= 2:
        return codes[0], codes[1]

    # "from X to Y"
    m = re.search(
        r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )
    if m:
        return resolve_iata(m.group(1)), resolve_iata(m.group(2))

    # "to Y from X"
    m = re.search(
        r"\bto\s+(.+?)\s+from\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )
    if m:
        return resolve_iata(m.group(2)), resolve_iata(m.group(1))

    # "from X"
    m = re.search(r"\bfrom\s+(.+?)(?:[.!?]|$)", q_lower)
    if m:
        return resolve_iata(m.group(1)), None

    # "to Y"
    m = re.search(r"\bto\s+(.+?)(?:[.!?]|$)", q_lower)
    if m:
        return None, resolve_iata(m.group(1))

    # Fallback: location mentions
    mentions = _location_mentions(query)
    if len(mentions) >= 2:
        return resolve_iata(mentions[0]), resolve_iata(mentions[1])
    if len(mentions) == 1:
        return DEFAULT_ORIGIN_IATA, resolve_iata(mentions[0])

    return None, None


# Formatting

def _fmt_flight(f: dict) -> str:
    airline = (f.get("airline") or {}).get("name") or "Unknown airline"
    fnum    = (f.get("flight")  or {}).get("iata") or "N/A"
    status  = f.get("flight_status") or "Unknown"
    dep     = f.get("departure") or {}
    arr     = f.get("arrival")   or {}

    def delay_txt(d: dict) -> str:
        v = d.get("delay")
        return f"{v} min" if v is not None else "N/A"

    return (
        f"Airline: {airline} | Flight: {fnum} | Status: {status}\n"
        f"  DEP  {dep.get('iata','?')} {dep.get('airport','?')} "
        f"T{dep.get('terminal','?')} G{dep.get('gate','?')} "
        f"@ {dep.get('scheduled','?')}  delay={delay_txt(dep)}\n"
        f"  ARR  {arr.get('iata','?')} {arr.get('airport','?')} "
        f"T{arr.get('terminal','?')} G{arr.get('gate','?')} "
        f"@ {arr.get('scheduled','?')}  delay={delay_txt(arr)}"
    )


# Public API

def search_flights(query: str, limit: int = 10) -> str:
    """
    Search live flights via AviationStack.
    Returns a formatted string with flight details, or an error message.
    Note: AviationStack provides live/status data, NOT ticket prices.
    """
    if not API_KEY:
        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Add it to your .env file: AVIATIONSTACK_API_KEY=your_key"
        )

    dep_iata, arr_iata = parse_route(query)

    params: dict = {"access_key": API_KEY, "limit": min(limit, 100)}
    if dep_iata:
        params["dep_iata"] = dep_iata
    if arr_iata:
        params["arr_iata"] = arr_iata

    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        data = resp.json()
    except requests.RequestException as e:
        return f"Flight API request failed: {e}"
    except ValueError:
        return "Flight API returned invalid JSON."

    if "error" in data:
        err = data["error"]
        return f"Flight API error [{err.get('code')}]: {err.get('message')}"

    flights = data.get("data") or []
    if not flights:
        route = (
            f"{dep_iata} → {arr_iata}" if dep_iata and arr_iata
            else f"from {dep_iata}" if dep_iata
            else f"to {arr_iata}"   if arr_iata
            else "global"
        )
        return (
            f"No live flight data found ({route}).\n"
            "AviationStack provides live status data, not fare prices. "
            "For prices, consider the Amadeus API."
        )

    label = (
        f"Live flights {dep_iata} → {arr_iata}" if dep_iata and arr_iata
        else f"Live flights from {dep_iata}"     if dep_iata
        else f"Live flights to {arr_iata}"       if arr_iata
        else "Global live flights"
    )
    body = "\n\n".join(_fmt_flight(f) for f in flights[:limit])
    return f"{label}\n\n{body}"


# ── CLI smoke-test ────────────────────────────────────────────────
if __name__ == "__main__":
    print(search_flights("Plan a 7 days Japan trip from India"))
    print("\n" + "=" * 80 + "\n")
    print(search_flights("Weekend trip Bangkok from Chennai"))
    print("\n" + "=" * 80 + "\n")
    print(search_flights("Trip from New York to London"))