allowed_formats = {
    'csv': 'text/csv',
    'tsv': 'text/tab-separated-values',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
}

date_mappings = {
    'month': {
        '%b': {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }, '%B': {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 
            'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 
            'october': 10, 'november': 11, 'december': 12
        }
    },
    'week': {
        '%a': {
            'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6, 'sun': 7
        }, '%A': {
            'monday': 1, 'tuesday': 2, 'wednesday': 3, 'thursday': 4,
            'friday': 5, 'saturday': 6, 'sunday': 7
        }
    },
    'quarter': {
        '%o': {
            '1st': 1, '2nd': 2, '3rd': 3, '4th': 4
        }, '%O': {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4
        }
    }
}

style_mapping = {
    'order': ['first', 'last'],
    'length': ['longer', 'shorter'],
    'alpha': ['A to Z', 'Z to A'],
    'time': ['earlier', 'later'],
    'contains': ['free'],
    'binary': ['positive', 'negative'],
    'size': ['minimum', 'maximum'],
    'mean': ['average']
}

time_formats = ['%H:%M:%S', '%-H:%M:%S', '%H:%M', '%-H:%M', '%I:%M:%S %p', '%-I:%M:%S %p', '%I:%M %p', '%-I:%M %p']
date_formats = ['%B %d, %Y', '%Y/%m/%d', '%Y/%-m/%-d', '%Y-%m-%d', '%Y-%-m-%-d', '%d-%b-%y', 
                             '%m/%d/%Y', '%-m/%-d/%Y', '%m-%d-%Y', '%-m-%-d-%Y', '%m/%d/%y',
                             '%d/%m/%Y', '%d/%-m/%Y',  '%d-%m-%Y', '%d-%-m-%Y', '%d/%m/%y']

missing_tokens = ['<n/a>', 'n/a', 'unknown', 'none', 'not applicable', 'not available',
                  'null', 'missing', 'empty', 'blank', 'unavailable', ' ', 'unreported']
default_tokens = ['default', 'example', 'placeholder', 'lorem ipsum', 'test ', 'john smith', 'jane doe'
                  'abc', 'xyz', '000-0000']
exact_match_tokens = ['test', 'example.com', 'your name', 'your email', 'your phone', 'your address']

common_tlds = ['com', 'org', 'net', 'edu', 'gov', 'biz', 'info', 'name', 'ai', 'io',
               'co', 'app', 'tech', 'dev', 'store', 'shop', 'cloud', 'xyz', 'online',
               'us', 'uk', 'ca', 'de', 'fr', 'au', 'jp', 'kr', 'cn', 'in', 'ru', 'br']

related_terms = [
    ['revenue', 'price', 'sales'],
    ['cost', 'loss', 'expense'],
    ['profit', 'margin', 'earnings'],
    ['order', 'transaction', 'sale'],
    ['customer', 'client', 'shopper', 'user', 'buyer'],
    ['product', 'item', 'sku'],
    ['channel', 'method', 'source', 'medium'],
    ['volume', 'quantity', 'amount'],
]

relation_map = {
    '+': 'summing',
    '-': 'subtracting',
    '*': 'multiplying',
    '/': 'dividing',
    'filter': 'filtering by',
    'group': 'grouping by',
    'join': 'joining by'
}
valid_relations = ['add', 'subtract', 'multiply', 'divide', 'not', 'exponent', 'and', 'or',
                   'less_than', 'greater_than', 'equals', 'conditional', 'placeholder']
shared_operations = ['filter', 'group', 'sort', 'compare', 'aggregate']
valid_operations = {
  'query': shared_operations,
  'pivot': shared_operations + ['insert', 'move'],
  'measure': shared_operations + ['calculate'],
  'segment': shared_operations + ['calculate', 'insert', 'move'],
  'plot': shared_operations + ['plot', 'apply']
}

default_limit = 256   # initial number of rows to show in the table
NA_string = '<N/A>'   # default string for missing values in the table

common_abbreviations = { 'Abandon': 'Abandonment Rate', 'ARPU': 'Average Revenue Per User',
  'Attribute': 'Attribution Modeling', 'AOV': 'Average Order Value', 'Bounce': 'Bounce Rate',
  'CAC': 'Customer Acquisition Cost', 'Churn': 'Customer Churn Rate', 'Conv': 'Conversion',
  'CPA': 'Cost Per Acquisition', 'CPC': 'Cost Per Click', 'CPL': 'Cost Per Lead', 'CPM': 'Cost Per Mille',
  'CPV': 'Cost Per View', 'CRM': 'Customer Relationship Management', 'CTA': 'Call to Action',
  'CTR': 'Click-Through Rate', 'Cust': 'Customer', 'CVR': 'Conversion Rate', 'DAU': 'Daily Active Users',
  'Device': 'Device Ratio', 'DMP': 'Data Management Platform', 'DSP': 'Demand Side Platform',
  'Engage': 'Engagement Rate', 'FB': 'Facebook', 'Freq': 'Purchase Frequency', 'GA4': 'Google Analytics',
  'Impr': 'Impressions', 'Inactive': 'Inactive Users', 'KE': 'Key Event', 'LTV': 'Customer Lifetime Value',
  'MAU': 'Monthly Active Users', 'MQL': 'Marketing Qualified Lead', 'MRR': 'Monthly Recurring Revenue',
  'NPS': 'Net Promoter Score', 'Open': 'Open Rate', 'PPC': 'Pay Per Click', 'PR': 'Public Relations',
  'Profit': 'Net Profit', 'ROAS': 'Return on Ad Spend', 'ROI': 'Return on Investment', 'SEM': 'Search Engine Marketing',
  'SEO': 'Search Engine Optimization', 'SKU': 'Stock Keeping Unit', 'SMM': 'Social Media Marketing',
  'TOS': 'Time On Site', 'TTR': 'Time to Resolution', 'Uniques': 'Unique Visitors', 'WOM': 'Word Of Mouth' }

state_abbreviations = {'al': 'alabama', 'ak': 'alaska', 'az': 'arizona', 'ar': 'arkansas',
    'ca': 'california', 'co': 'colorado', 'ct': 'connecticut', 'de': 'delaware', 'fl': 'florida',
    'ga': 'georgia', 'hi': 'hawaii', 'id': 'idaho', 'il': 'illinois', 'in': 'indiana',
    'ia': 'iowa', 'ks': 'kansas', 'ky': 'kentucky', 'la': 'louisiana', 'me': 'maine',
    'md': 'maryland', 'ma': 'massachusetts', 'mi': 'michigan', 'mn': 'minnesota',
    'ms': 'mississippi', 'mo': 'missouri', 'mt': 'montana', 'ne': 'nebraska', 'nv': 'nevada',
    'nh': 'new hampshire', 'nj': 'new jersey', 'nm': 'new mexico', 'ny': 'new york',
    'nc': 'north carolina', 'nd': 'north dakota', 'oh': 'ohio', 'ok': 'oklahoma', 'or': 'oregon',
    'pa': 'pennsylvania', 'ri': 'rhode island', 'sc': 'south carolina', 'sd': 'south dakota',
    'tn': 'tennessee', 'tx': 'texas', 'ut': 'utah', 'vt': 'vermont', 'va': 'virginia',
    'wa': 'washington', 'wv': 'west virginia', 'wi': 'wisconsin', 'wy': 'wyoming' }

generic_responses = ["OK, no problem.", "Done! Thanks for waiting.", "You got it."]
visualize_responses = ["Sure, here's your figure.", "Done, here's your figure.", "Here you go."]
transform_responses = ["Sure, I've restrucured the table.", "You got it, I've made the changes.", "OK, how does this look?"]
clean_responses = ["Ok, I've updated the table as requested.", "Sure, I've made the changes.", "Done, how does this look?"]

thought_prefixes = ["Just FYI, ", "Just so you know, ", "Please note, "]
agreeable_prefixes = ["Sure, ", "No problem, ", "You got it, ", "OK, ", "Understood, "]
prefix_options = ["Just a heads up, ", "Please note, ", "Just so you know, ", "During my analysis, ", ""]
suffix_options = ["Would you like to see the rows?", "Would you like to investigate?", "Want to take a look?",
                "Would you like to take a look?", "Would you like to see them?", "This may affect the results."]

type_hierarchy = {
    'blank': ['null', 'missing', 'default'],
    'unique': ['boolean', 'status', 'category', 'id'],
    'datetime': ['year', 'quarter', 'month', 'week', 'day', 'hour', 'minute', 'second', 'date', 'time', 'timestamp'],
    'location': ['street', 'city', 'zip', 'state', 'country', 'address'],
    'number': ['currency', 'percent', 'whole', 'decimal'],
    'text': ['email', 'phone', 'name', 'url', 'general']
}

error_responses = [
    "Sorry, I'm having a bit of trouble here. Let me ping this request to my team and get back to you when they respond.",
    "Sorry, my LLM API provider is having trouble again. I can't get any results from the server.",
    "I apologize, but I can't get you an answer at this time. Please come back later.",
    "Sorry, my brain is in a fog at the moment. Please try again in an hour.",
    "My mind is just not functioning at the moment. Let me get some coffee first, can you come back later?"
]    
delay_responses = [
    "Hmm, I'll have to think about that for a bit",
    "That's a hard one, let me think about it.",
    "Still thinking about this, please give me a second.",
    "I'm still thinking about this, sorry for the wait."
]

embedder_options = {
    'all-MiniLM-L12-v2': 'selected for balance, 59.76 accuracy, 7500 sentences/sec, 120 MB',
    'all-distilroberta-v1': 'slower, but better performance, 290 MB',
    'all-MiniLM-L6-v2': 'faster, but lower performance, 80 MB',
}

typo_corpus = {
    'marketing': {
        "advertisement": ["advertisment", "advertizement"],
        "acquisition": ["aquisition", "acquasition"],
        "analytics": ["analyics", "analitics", "analytycs", "analitycs"],
        "audience": ["audiance", "audence"],
        "brochure": ["brouchure", "broshure", "brouchre"],
        "campaign": ["campain", "campaigne", "campagn"],
        "commercial": ["comercial", "commertial"],
        "conversion": ["convertion", "convesion", "converstion"],
        "demographics": ["demografics", "demograhics"],
        "engagement": ["engagment", "engadgement", "engagment"],
        "ecommerce": ["ecomerce", "e-commerce"],
        "guerrilla": ["guerilla", "gorilla", "guerila"],
        "influencer": ["influenzer"],
        "marketing": ["marketting", "maketing", "marketeing"],
        "merchandise": ["merchadise", "merchandize", "merchandice"],
        "newsletter": ["newslatter", "newsleter", "newsetter"],
        "optimization": ["optimisation", "optimzation"],
        "promotional": ["promotinal", "promtional", "promotonal"],
        "questionnaire": ["questionaire", "questionare", "questionnair"],
        "responsive": ["responcive", "responsiv"],
        "retention": ["retension", "retantion", "retenton"],
        "referrals": ["referals"],
        "segmentation": ["segmetation", "segmantation", "segmention"],
        "testimonial": ["testimonal", "testemonial", "testimoneal"]
    },
    'sales': {
        "agreement": ["agrement"],
        "ambassador": ["ambasador"],
        "appointment": ["apointment"],
        "commission": ["comission"],
        "consultant": ["consulant"],
        "contract": ["contrat"],
        "customer": ["costumer", "custumer", "custmer"],
        "discount": ["disscount"],
        "demonstration": ["demonstation"],
        "fulfillment": ["fullfillment"],
        "incentive": ["insentive"],
        "implement": ["impliment"],
        "personnel": ["personel"],
        "pipeline": ["pipline"],
        "proposal": ["proposel"],
        "qualified": ["qualifed"],
        "negotiation": ["negotation"],
        "objection": ["objection"],
        "referral": ["referal"],
        "targeting": ["targetting"],
        "territory": ["teritory"],
        "utilization": ["utilisation"],
        "visibility": ["visability"],
        "wholesale": ["wholsale"]
    },
    'accounting': {
        "accounting": ["acounting", "accountting", "acountting"],
        "amortization": ["amortisation", "amortazation", "amoritization"],
        "asset": ["aset", "assset", "asett"],
        "balance": ["balence", "balanse", "ballance"],
        "budget": ["budjet", "budgit", "budgut"],
        "benefits": ["benifits"],
        "collateral": ["colateral", "colaterall"],
        "compliance": ["complience", "complianse"],
        "depreciation": ["depriciation", "depresiation", "depreaciation"],
        "expenses": ["expences", "expensis"],
        "government": ["goverment"],
        "infrastructure": ["infastructure"],
        "liability": ["liabilty", "liablity", "libaility"],
        "revenue": ["revenu", "reveue", "revanue"],
        "mortgage": ["morgage", "mortage"],
        "possession": ["posession"],
        "preferred": ["prefered"],
        "profit": ["proffit", "profitt"],
    },
    'finance': {
        "analysis": ["analisis", "analisys", "analysys"],
        "algorithm": ["algorithem"],
        "capital": ["capitol", "capitel", "capitall"],
        "equity": ["eqity", "equety", "equty"],
        "dividend": ["divident", "dividand", "dividen"],
        "financial": ["financal", "finnancial", "finacial"],
        "forecast": ["forcast", "forecest"],
        "forecasting": ["forcasting"],
        "investment": ["investmant", "invesment", "investiment"],
        "management": ["managment"],
        "planning": ["planing"],
        "portfolio": ["portofolio"],
        "recurring": ["reccuring"],
        "reconciliation": ["reconsiliation", "reconcilation", "reconsilation"],
        "transaction": ["transation", "tranaction"],
        "valuation": ["valuaton"],
        "volatility": ["volatilty", "volatiliy"]
    },
    'general': {
        "accommodate": ["accomodate"],
        "accessibility": ["accesibility"],
        "authentic": ["authenthic"],
        "business": ["buisness", "bisiness"],
        "committee": ["commitee"],
        "collaboration": ["colaboration"],
        "competitive": ["competative"],
        "communication": ["comunication"],
        "development": ["developement"],
        "efficiency": ["efficency"],
        "entrepreneur": ["entrepeneur", "entreprenuer", "enterprenuer"],
        "guarantee": ["garantee"],
        "generally": ["generaly"],
        "improvement": ["improvment"],
        "integrate": ["intergrate"],
        "millennial": ["millenial"],
        "occurrence": ["occurence"],
        "persistent": ["persistant"],
        "probably": ["probaly"],
        "recommend": ["reccomend"],
        "relevant": ["revelant"],
        "separate": ["seperate"],
        "strategy": ["stratergy", "stratagy", "strategie"],
        "successful": ["succesful"],
        "technology": ["tecnology"],
        "threshold": ["threshhold"],
        "transferred": ["transfered"],
        "usability": ["usibility"]
    }
}