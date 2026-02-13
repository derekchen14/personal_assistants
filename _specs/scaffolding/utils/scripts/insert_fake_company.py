import csv
import random
import re
from typing import Dict, List, Tuple

# Define industries and subcategories with real and fake companies
COMPANY_DATA = {
  "MarTech": {
    "Marketing Automation": {
      "real": ["hubspot", "marketo", "pardot", "mailchimp", "activecampaign"],
      "fake": ["growthhub", "leadforge", "campaignify", "marketpulse", "funnelio",
               "conversionlab", "engagestream", "reachmetrics", "targetflow"]
    },
    "Analytics & Attribution": {
      "real": ["segment", "mixpanel", "amplitude", "heap", "kissmetrics"],
      "fake": ["insightcore", "trackwise", "metricshub", "databridge", "clickpath",
               "journeymap", "attributeiq", "analyticspro", "measurestack"]
    },
    "Customer Data Platforms": {
      "real": ["segment", "tealium", "lytics", "blueconic"],
      "fake": ["dataforge", "customerhub", "profilestack", "unifydata", "cdpcloud",
               "audiencecore", "datastream", "customeriq", "profilemaster"]
    },
    "Email Marketing": {
      "real": ["sendgrid", "mailgun", "postmark", "sparkpost"],
      "fake": ["mailflow", "inboxpro", "sendwise", "emailforge", "campaignpost",
               "delivermax", "mailmetrics", "sendstack", "emailhub"]
    }
  },
  "Sales Tech": {
    "CRM & Sales Enablement": {
      "real": ["salesforce", "pipedrive", "copper", "insightly", "zoho"],
      "fake": ["dealflow", "salesstack", "pipelineiq", "closemore", "revenuehub",
               "salesboost", "dealmaker", "quotepro", "winrate"]
    },
    "Sales Intelligence": {
      "real": ["zoominfo", "lusha", "clearbit", "leadiq", "seamless"],
      "fake": ["prospectiq", "leadminer", "contacthub", "salesintel", "findlead",
               "prospector", "leadscope", "targetfind", "salesdata"]
    },
    "Sales Engagement": {
      "real": ["outreach", "salesloft", "groove", "yesware", "reply"],
      "fake": ["engagepro", "touchpoint", "reachout", "connectflow", "salestouch",
               "followupiq", "cadencelab", "sequencer", "engagebot"]
    }
  },
  "Startup SaaS": {
    "Productivity Tools": {
      "real": ["notion", "airtable", "monday", "asana", "clickup"],
      "fake": ["workstream", "taskflow", "productivehub", "teamspace", "projectiq",
               "collaborator", "workwise", "efficiencylab", "teamforge"]
    },
    "Communication": {
      "real": ["slack", "discord", "zoom", "loom", "calendly"],
      "fake": ["chatflow", "teamchat", "connecthub", "talkspace", "meetingpro",
               "scheduleiq", "videosync", "chatwise", "teamconnect"]
    },
    "Developer Tools": {
      "real": ["github", "gitlab", "vercel", "netlify", "heroku"],
      "fake": ["codestack", "devforge", "deployiq", "buildflow", "codehub",
               "devops360", "releasepro", "cicdlab", "codestream"]
    },
    "Finance & Operations": {
      "real": ["stripe", "square", "gusto", "rippling", "bill"],
      "fake": ["payflow", "financeiq", "billstack", "expensehub", "invoicepro",
               "paymentforge", "finops", "moneystream", "cashflowiq"]
    }
  },
  "Healthcare": {
    "EHR Providers": {
      "real": ["epic", "cerner", "allscripts", "athenahealth", "nextgen"],
      "fake": ["healthrecordpro", "medchartiq", "clinicalcore", "ehrhub", "patientstack",
               "medrecords360", "healthdataflow", "carechartpro", "medicalvault"]
    },
    "Medical Imaging": {
      "real": ["gehealthcare", "siemens-healthineers", "philips", "fujifilm", "carestream"],
      "fake": ["imagingcore", "scanpro", "medimageiq", "diagnosticshub", "radiology360",
               "imageflowmed", "scanstream", "medvisuals", "imagingcloud"]
    },
    "Clinical Trial Management": {
      "real": ["veeva", "medidata", "oracle-health", "iqvia", "parexel"],
      "fake": ["trialhub", "clinicaliq", "studymanager", "trialflow", "researchcore",
               "trialstack", "clinicalops", "studystream", "trialdatapro"]
    },
    "Healthcare Analytics": {
      "real": ["optum", "ibm-watson-health", "health-catalyst", "qlik-health"],
      "fake": ["healthinsights", "medanalytics", "carestats", "healthmetrics360",
               "medicaliq", "healthdatapro", "analyticsmed", "insightcare"]
    }
  },
  "Finance": {
    "Payment Processing": {
      "real": ["stripe", "square", "adyen", "paypal", "braintree"],
      "fake": ["paymentflow", "transactiq", "paycore", "merchantpro", "paystream",
               "processhub", "paymentstack", "transactwise", "merchantflow"]
    },
    "Risk Assessment": {
      "real": ["fico", "experian", "equifax", "lexisnexis", "moody's"],
      "fake": ["riskiq", "creditcore", "riskanalytics", "scorepro", "riskmetrics",
               "creditflow", "riskinsight", "scorestack", "assessmentpro"]
    },
    "Fraud Detection": {
      "real": ["sift", "riskified", "forter", "signifyd", "kount"],
      "fake": ["fraudguard", "detectiq", "fraudshield", "secureflow", "fraudstop",
               "protectwise", "fraudcore", "shieldpro", "detectstream"]
    },
    "Compliance Platforms": {
      "real": ["thomsonreuters", "workiva", "diligent", "nasdaq-bwise"],
      "fake": ["complianceiq", "regtech360", "complyhub", "regulatorypro", "govstack",
               "compliancecore", "regflow", "auditstream", "complysmart"]
    }
  },
  "Logistics": {
    "Warehouse Management": {
      "real": ["manhattan-associates", "highjump", "infor-wms", "sap-ewm", "jda"],
      "fake": ["warehouseiq", "inventorypro", "stockflow", "warehousecore", "wmscloud",
               "fulfillhub", "stockstream", "warehousepro", "inventorystack"]
    },
    "Fleet Tracking": {
      "real": ["samsara", "geotab", "verizon-connect", "trimble", "omnitracs"],
      "fake": ["fleetiq", "trackpro", "vehiclecore", "fleetmetrics", "gpsflow",
               "fleetwise", "trackstream", "telematicsiq", "fleetguard"]
    },
    "Supply Chain Visibility": {
      "real": ["project44", "fourkites", "shippeo", "descartes", "e2open"],
      "fake": ["supplyiq", "chainvisibility", "logisticscore", "shipmentpro", "chainflow",
               "visibilitystack", "supplystream", "chainmetrics", "trackchain"]
    },
    "Shipping Aggregators": {
      "real": ["shipstation", "easyship", "shippo", "sendcloud", "pirateship"],
      "fake": ["shipiq", "freightcore", "shippingpro", "carrierflow", "shipstack",
               "freighthub", "shipwise", "carrierstream", "shippingcloud"]
    }
  },
  "Ecommerce": {
    "Product Information Management": {
      "real": ["salsify", "akeneo", "inriver", "pimcore", "plytix"],
      "fake": ["productiq", "catalogcore", "pimstack", "productflow", "catalogpro",
               "itemhub", "productstream", "catalogwise", "productmaster"]
    },
    "Inventory Sync": {
      "real": ["skubana", "sellbrite", "ecomdash", "zoho-inventory", "cin7"],
      "fake": ["synciq", "inventorybridge", "stocksync", "multichannel360", "syncpro",
               "inventoryflow", "channelhub", "stockbridge", "omnisync"]
    },
    "Order Management": {
      "real": ["orderhive", "brightpearl", "netsuite", "orderbot", "skuvault"],
      "fake": ["orderiq", "fulfillcore", "orderpro", "orderstream", "fulfillstack",
               "orderflow", "processiq", "orderhub", "fulfillwise"]
    },
    "Pricing Intelligence": {
      "real": ["prisync", "competera", "price2spy", "minderest", "wiser"],
      "fake": ["priceiq", "competitorcore", "pricepro", "pricewatch360", "priceflow",
               "marketprice", "pricestack", "competitoriq", "pricemetrics"]
    }
  },
  "Energy": {
    "Smart Grid Management": {
      "real": ["schneider-electric", "siemens-grid", "abb", "ge-grid", "oracle-utilities"],
      "fake": ["gridiq", "smartgridpro", "gridcore", "powerflow", "gridmetrics",
               "energygrid360", "gridstack", "powerstream", "gridwise"]
    },
    "Energy Analytics": {
      "real": ["opower", "c3-ai", "uptake", "spacetime", "autogrid"],
      "fake": ["energyiq", "poweranalytics", "consumptionpro", "energycore", "powermetrics",
               "energyflow", "analyticspower", "energystack", "powerinsights"]
    },
    "Predictive Maintenance": {
      "real": ["aveva", "aspentech", "senseye", "augury", "uptake"],
      "fake": ["maintainiq", "predictpro", "assetcore", "maintenanceflow", "predictstack",
               "assetguard", "maintainwise", "predictstream", "assetmetrics"]
    },
    "Renewable Forecasting": {
      "real": ["solcast", "meteologica", "vaisala", "awstruepower", "3tier"],
      "fake": ["renewableiq", "solarpredict", "windcore", "forecastpro", "renewflow",
               "solarmetrics", "windstack", "predictrenew", "greenforecast"]
    }
  },
  "Manufacturing": {
    "Production Monitoring": {
      "real": ["rockwell-automation", "honeywell", "yokogawa", "emerson", "abb"],
      "fake": ["productioniq", "linepro", "manufacturcore", "productionflow", "linestack",
               "monitorpro", "productionmetrics", "linestream", "manufacturehub"]
    },
    "Quality Control": {
      "real": ["minitab", "infinityqs", "qualityline", "1factory", "qima"],
      "fake": ["qualityiq", "inspectpro", "qccore", "qualityflow", "defectstack",
               "inspectwise", "qualitymetrics", "qcstream", "qualityguard"]
    },
    "Equipment Analytics": {
      "real": ["ptc-thingworx", "sap-apm", "ibm-maximo", "infor-eam", "fiix"],
      "fake": ["equipmentiq", "assetpro", "machinecore", "equipflow", "assetstack",
               "machinemetrics", "equipwise", "assetstream", "machinehub"]
    },
    "Supply Chain Integration": {
      "real": ["e2open", "kinaxis", "o9solutions", "blueyonder", "llamasoft"],
      "fake": ["supplyintegrate", "chainconnect", "integrationpro", "supplybridge",
               "chainiq", "integrateflow", "supplylink", "chainconnector", "supplyhub"]
    }
  },
  "Real Estate": {
    "Property Listing Aggregators": {
      "real": ["zillow", "realtor", "redfin", "trulia", "homes"],
      "fake": ["listingiq", "propertyhub", "realtypro", "listingcore", "propertyflow",
               "realestatestack", "listingstream", "propertywise", "realtymetrics"]
    },
    "Market Analytics": {
      "real": ["corelogic", "realsuite", "housecanary", "rentberry", "mashvisor"],
      "fake": ["marketiq", "realtyanalytics", "propertymetrics", "marketcore", "realtyflow",
               "analyticsrealty", "marketstack", "propertyinsights", "realtydata"]
    },
    "Lease Management": {
      "real": ["appfolio", "buildium", "yardi", "rentmanager", "propertyware"],
      "fake": ["leaseiq", "tenantpro", "leasecore", "rentflow", "leasestack",
               "tenanthub", "leasemetrics", "rentstream", "leasewise"]
    },
    "Building Management": {
      "real": ["procore", "plangrid", "fieldwire", "buildertrend", "corecon"],
      "fake": ["buildingiq", "facilitypro", "buildcore", "managementflow", "buildstack",
               "facilitywise", "buildmetrics", "managestream", "buildinghub"]
    }
  },
  "Human Resources": {
    "Applicant Tracking": {
      "real": ["greenhouse", "lever", "workday", "icims", "jobvite"],
      "fake": ["recruitiq", "hirepro", "talentcore", "recruitflow", "hirestack",
               "talentstream", "recruitwise", "hiremetrics", "talenthub"]
    },
    "Payroll Administration": {
      "real": ["adp", "paychex", "gusto", "rippling", "paycom"],
      "fake": ["payrolliq", "wagepro", "paycore", "salaryflow", "payrollstack",
               "wagewise", "paymetrics", "salarystream", "payrollhub"]
    },
    "Performance Analytics": {
      "real": ["lattice", "15five", "culture-amp", "officevibe", "bamboohr"],
      "fake": ["performiq", "reviewpro", "performancecore", "reviewflow", "performstack",
               "evaluationhub", "performmetrics", "reviewstream", "performwise"]
    },
    "Workforce Planning": {
      "real": ["workday", "kronos", "deputy", "humanity", "when-i-work"],
      "fake": ["workforceiq", "schedulepro", "staffcore", "scheduleflow", "workstack",
               "staffwise", "planmetrics", "schedulestream", "workforcehub"]
    }
  },
  "Legal": {
    "Contract Management": {
      "real": ["docusign", "ironclad", "contractworks", "concord", "agiloft"],
      "fake": ["contractiq", "agreementpro", "contractcore", "legalflow", "contractstack",
               "agreementhub", "contractmetrics", "legalstream", "contractwise"]
    },
    "E-Discovery": {
      "real": ["relativity", "everlaw", "logikcull", "exterro", "nuix"],
      "fake": ["discoveryiq", "evidencepro", "ediscoverycore", "legaldata", "discoverystack",
               "evidenceflow", "discoveryhub", "legalmetrics", "evidencestream"]
    },
    "Compliance Tracking": {
      "real": ["thomson-reuters", "lexisnexis", "complysci", "starCompliance"],
      "fake": ["complianceiq", "regulatorypro", "compliancecore", "regflow", "complystack",
               "regulatoryhub", "compliancemetrics", "regstream", "complywise"]
    },
    "IP Management": {
      "real": ["anaqua", "clarivate", "questel", "dennemeyer", "ipfolio"],
      "fake": ["patentiq", "ippro", "intellectualcore", "patentflow", "ipstack",
               "trademarkhub", "ipmetrics", "patentstream", "intellectualwise"]
    }
  }
}

# Common domain variations
DOMAIN_VARIATIONS = [".com", ".io", ".co", ".ai", ".app", ".tech"]

def generate_company_domain() -> str:
  """Generate a realistic company domain."""
  # 20% chance for real company, 80% for fake
  use_real = random.random() < 0.2
  
  # Select industry
  industry = random.choice(list(COMPANY_DATA.keys()))
  
  # Select subcategory
  subcategory = random.choice(list(COMPANY_DATA[industry].keys()))
  
  # Select company name
  company_type = "real" if use_real else "fake"
  companies = COMPANY_DATA[industry][subcategory][company_type]
  company_name = random.choice(companies)
  
  # For real companies, use .com, for fake ones vary it
  if use_real:
    domain_ext = ".com"
  else:
    # Weight .com higher for realism
    weights = [0.5, 0.2, 0.1, 0.1, 0.05, 0.05]
    domain_ext = random.choices(DOMAIN_VARIATIONS, weights=weights)[0]
  
  return f"{company_name}{domain_ext}"

def should_replace_domain(email: str) -> bool:
  """Check if email domain should be replaced."""
  changed_domains = ["example.com", "hotmail.com", "yahoo.com", "outlook.com", "gmail.com"]
  if not email:
    return False
    
  lowered = email.lower()
  for domain in changed_domains:
    if lowered.endswith(domain):
      if domain == 'gmail.com':
        return random.random() < 0.8
      else:
        return True
    
  return False

def replace_email_domain(email: str, new_domain: str) -> str:
  """Replace the domain part of an email address."""
  changed_domains = ["example.com", "hotmail.com", "yahoo.com", "outlook.com"]
  
  # Find which domain this email ends with
  for domain in changed_domains:
    if email.lower().endswith(domain):
      # Extract the local part
      domain_start = len(email) - len(domain)
      local_part = email[:domain_start]
      
      # Handle case where there's no @ symbol
      if local_part.endswith("@"):
        # Standard case: user@domain
        local_part = local_part[:-1]
      else:
        # Missing @ case: userdomain - need to clean up
        local_part = local_part.rstrip(" .-_")
        if not local_part:
          local_part = "contact"
      
      return f"{local_part}@{new_domain}"
  
  return email

def process_salesforce_csv(input_file: str, output_file: str):
  """Process the Salesforce CSV file and replace generic email domains."""
  # Track used domains to ensure variety
  used_domains = set()
  domain_usage_count = {}
  
  # Read and process the CSV
  rows_processed = []
  emails_replaced = 0
  
  try:
    with open(input_file, 'r', encoding='utf-8') as infile:
      reader = csv.DictReader(infile)
      fieldnames = reader.fieldnames
      
      for row in reader:
        # Clean the email address first
        email_address = row.get('EmailAddress', '')
        row['EmailAddress'] = email_address
        
        # Check if we should replace the domain
        if should_replace_domain(email_address):
          # Generate a new domain
          # Try to get a unique domain, but allow some repeats
          attempts = 0
          while attempts < 10:
            new_domain = generate_company_domain()
            
            # Allow up to 2 uses of the same domain
            if domain_usage_count.get(new_domain, 0) < 2:
              break
            attempts += 1
          
          # Update tracking
          domain_usage_count[new_domain] = domain_usage_count.get(
            new_domain, 0
          ) + 1
          used_domains.add(new_domain)
          
          # Replace the email domain
          row['EmailAddress'] = replace_email_domain(
            email_address, new_domain
          )
          emails_replaced += 1
        
        rows_processed.append(row)
    
    # Write the processed data to the output file
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
      writer = csv.DictWriter(outfile, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(rows_processed)
    
    # Print summary statistics
    print(f"Processing complete!")
    print(f"Total rows processed: {len(rows_processed)}")
    print(f"Emails replaced: {emails_replaced}")
    print(f"Unique domains created: {len(used_domains)}")
    print(f"\nDomain usage distribution:")
    for domain, count in sorted(
      domain_usage_count.items(), 
      key=lambda x: x[1], 
      reverse=True
    )[:10]:
      print(f"  {domain}: {count} time(s)")
    
  except FileNotFoundError:
    print(f"Error: Could not find input file '{input_file}'")
  except Exception as e:
    print(f"Error processing file: {str(e)}")

if __name__ == "__main__":
  # Process the Salesforce CSV file
  process_salesforce_csv('Salesforce_Original.csv', 'Salesforce_v2.csv')