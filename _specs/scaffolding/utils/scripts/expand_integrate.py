import csv
import random
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import truncnorm

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)

def generate_realistic_name():
  """Generate realistic first and last names with diversity"""
  first_names = [
    # Western names
    'Zara', 'Kieran', 'Thea', 'Maddox', 'Nova', 'Caspian', 'Indie', 'Atlas',
    'Wren', 'Phoenix', 'Sage', 'River', 'Ember', 'Orion', 'Luna', 'Axel',
    'Ivy', 'Knox', 'Aria', 'Zander', 'Freya', 'Jasper', 'Quinn', 'Leo',
    'Hazel', 'Felix', 'Stella', 'Finn', 'Iris', 'Miles', 'Cora', 'Silas',
    'Ruby', 'Owen', 'Nora', 'Ezra', 'Mila', 'Luca', 'Zoe', 'Kai', 'Elena',
    # Global names
    'Arjun', 'Priya', 'Hiroshi', 'Sakura', 'Diego', 'Valentina', 'Hassan', 
    'Amara', 'Nikolai', 'Anastasia', 'Kwame', 'Asha', 'Ravi', 'Deepika',
    'Yuki', 'Kenji', 'Mateo', 'Esperanza', 'Omar', 'Layla', 'Viktor', 'Katya',
    'Kofi', 'Akira', 'Tariq', 'Fatima', 'Dmitri', 'Svetlana', 'Amir', 'Zara',
    'Emilio', 'Paloma', 'Rashid', 'Nadia', 'Sergei', 'Yelena', 'Jabari', 
    'Kesi', 'Tomás', 'Marisol', 'Farid', 'Yasmin', 'Alexei', 'Darya'
    # Add more names as needed
    'Celeste', 'Rowan', 'Juniper', 'Dante', 'Marlowe', 'Evander', 'Seren',
    'Cleo', 'Enzo', 'Lyra', 'Bodhi', 'Isla', 'Jude', 'Willow', 'Aspen',
    'Remy', 'Sienna', 'Cyrus', 'Briar', 'Damon', 'Reed', 'Juneau', 'Sage',
    'Zion', 'Echo', 'Cruz', 'Willa', 'Atlas', 'Skye', 'Indigo', 'Vale',
    'Aurelius', 'Clementine', 'Rafferty', 'Seraphina', 'Caspian', 'Magnolia',
    'Lucian', 'Cordelia', 'Leander', 'Ophelia', 'Augustus', 'Beatrice',
    'Lysander', 'Evangeline', 'Theodora', 'Maximilian', 'Rosalind',
    'Sebastian', 'Octavia', 'Raphael', 'Genevieve', 'Dorian', 'Serenity',
    'Evander', 'Cordelia', 'Leander', 'Vivienne', 'Damien', 'Arabella',
    'Caius', 'Aurora', 'Phoenix', 'Christina', 'Atlas', 'Cecelia', 'Orion',
    'Victor', 'Luna', 'Nathaniel', 'Eleanor', 'Cyrus', 'Briar', 'Damon'
  ]
  
  last_names = [
    'Blackwood', 'Ashworth', 'Brightwater', 'Thornfield', 'Goldstein', 
    'Rosenberg', 'Nakamura', 'Tanaka', 'Yamamoto', 'Rodriguez', 'Fernandez',
    'Montenegro', 'Al-Hassan', 'Okafor', 'Petrov', 'Volkov', 'Kozlov',
    'Andersson', 'Lindqvist', 'Van Der Berg', 'De Jong', 'Müller', 'Fischer',
    'Dubois', 'Moreau', 'Rossi', 'Bianchi', 'Silva', 'Santos', 'Oliveira',
    'Hassan', 'Ahmed', 'Okoye', 'Adebayo', 'Singh', 'Patel', 'Kumar',
    'Johansson', 'Eriksson', 'Nielsen', 'Hansen', 'Kowalski', 'Nowak',
    'Novák', 'Svoboda', 'Popović', 'Nikolić', 'Papadopoulos', 'Georgakis',
    'Morozov', 'Smirnov', 'Kuznetsov', 'Popov', 'Sokolov', 'Lebedev',
    'Bogdanov', 'Zakharov', 'Gusev', 'Orlov', 'Stepanov', 'Vladimirov',
    'Morrison', 'Chen', 'Walsh', 'Larsson', 'Park', 'Kim', 'O\'Brien',
    'Martinez', 'Clarke', 'Thompson', 'White', 'Graham', 'Fletcher',
    'Hayes', 'Brooks', 'Foster', 'Cross', 'Bell', 'Stone', 'Reed',
    'Davis', 'Cooper', 'Ward', 'Phillips', 'Bennett', 'Turner', 'Morgan',
    'Butler', 'Hamilton', 'Webb', 'Fox', 'Hunt', 'Price', 'Gray',
    'Lane', 'Wright', 'James', 'Sharp', 'Wells', 'Snow', 'Marsh',
    'Drake', 'Pierce', 'Rhodes', 'Frost', 'Knight', 'Blake', 'Steel',
    'Rivers', 'West', 'Hawthorne', 'Winters', 'Sterling', 'Thorne',
    'Nightingale', 'Silverstone', 'Moon', 'Vale', 'Lynch', 'Cole',
    'Storm', 'Pine', 'North', 'Wolfe', 'Hawkins', 'Henderson', 'Hill',
  ]
  
  return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_source():
  """Generate source with specified probabilities"""
  sources = ['organic', 'social', 'referral', 'direct', 'email', 'GoogleAds', 'LinkedIn']
  probabilities = [0.17, 0.14, 0.16, 0.11, 0.09, 0.21, 0.12]
  return np.random.choice(sources, p=probabilities)

def generate_visit_counts():
  """Generate visit counts using truncated Poisson (1-6)"""
  # Using truncated normal as approximation to truncated Poisson
  mu, sigma = 2.5, 1.5
  lower, upper = 1, 6
  
  # Create truncated normal distribution
  a, b = (lower - mu) / sigma, (upper - mu) / sigma
  return int(truncnorm.rvs(a, b, loc=mu, scale=sigma))

def generate_page_visited():
  """Generate page visited uniformly from available options"""
  pages = ['Helpdesk', 'FAQ', 'Pricing', 'Contact', 'Features', 'About', 
           'Home', 'Blog']
  return random.choice(pages)

def generate_first_visit_time():
  """Generate first visit time between March 6 and July 4, 2024"""
  start_date = datetime(2024, 1, 10)
  end_date = datetime(2024, 2, 24)
  
  time_between = end_date - start_date
  random_days = random.randint(0, time_between.days)
  random_seconds = random.randint(0, 86400)  # 24 hours in seconds
  
  visit_time = start_date + timedelta(days=random_days, seconds=random_seconds)
  return visit_time.strftime('%Y-%m-%dT%H:%M:%S')

def generate_downloaded():
  """Generate downloaded with 70% likelihood but high variance"""
  # High variance means some periods might have very different rates
  base_prob = 0.6
  variance = random.uniform(-0.3, 0.3)  # High variance
  actual_prob = max(0.1, min(0.9, base_prob + variance))
  
  return 'Yes' if random.random() < actual_prob else 'No'

def generate_form_submitted():
  """Generate form submitted with 60% likelihood"""
  return random.random() < 0.6

def generate_form_submission_datetime(first_visit_str, form_submitted):
  """Generate form submission datetime after first visit if form submitted"""
  if not form_submitted:
    return ''
  
  first_visit = datetime.strptime(first_visit_str, '%Y-%m-%dT%H:%M:%S')
  
  # Form submission can be same day up to 30 days later
  max_days_later = 30
  random_days = random.randint(0, max_days_later)
  random_seconds = random.randint(0, 86400)
  
  submission_time = first_visit + timedelta(days=random_days, 
                                           seconds=random_seconds)
  return submission_time.strftime('%Y-%m-%dT%H:%M:%S')

def calculate_lead_score(visit_count, downloaded, form_submitted):
  """Calculate lead score based on visit count, download, and form submission"""
  base_score = 20
  
  # Visit count contribution (up to 40 points)
  visit_score = min(40, visit_count * 7)
  
  # Download contribution (15 points)
  download_score = 15 if downloaded == 'Yes' else 0
  
  # Form submission contribution (25 points)
  form_score = 25 if form_submitted else 0
  
  # Add some randomness (±10 points)
  random_adjustment = random.randint(-10, 10)
  
  total_score = base_score + visit_score + download_score + form_score + \
                random_adjustment
  
  # Ensure score is between 20 and 100
  return max(20, min(100, total_score))

def generate_lead_data(start_id, num_records):
  """Generate lead data records"""
  leads = []
  # load existing names from the current file called 'names.txt' where this is a single name per line
  with open('names.txt', 'r') as file:
    existing_names = file.read().splitlines()
  used_names = set(existing_names)
  print("Found", len(used_names), "existing names")
  
  for i in range(num_records):
    # Ensure unique names
    while True:
      name = generate_realistic_name()
      if name not in used_names:
        used_names.add(name)
        break
    
    lead_id = start_id + i
    source = generate_source()
    visit_counts = generate_visit_counts()
    page_visited = generate_page_visited()
    first_visit_time = generate_first_visit_time()
    downloaded = generate_downloaded()
    form_submitted = generate_form_submitted()
    form_submission_datetime = generate_form_submission_datetime(
      first_visit_time, form_submitted
    )
    lead_score = calculate_lead_score(visit_counts, downloaded, form_submitted)
    
    lead = {
      'LeadID': lead_id,
      'UserName': name,
      'Source': source,
      'VisitCounts': visit_counts,
      'PageVisited': page_visited,
      'FirstVisitTime': first_visit_time,
      'DownloadedContent': downloaded,
      'FormSubmitted': str(form_submitted),
      'FormSubmissionDateTime': form_submission_datetime,
      'LeadScore': lead_score
    }
    
    leads.append(lead)  
  return leads

def main():
  # Generate data
  start_id = 1615
  num_records = 200  # Adjust as needed for March 6 - July 4 period
  
  leads = generate_lead_data(start_id, num_records)
  
  # Write to CSV
  fieldnames = ['LeadID', 'UserName', 'Source', 'VisitCounts', 'PageVisited',
                'FirstVisitTime', 'DownloadedContent', 'FormSubmitted',
                'FormSubmissionDateTime', 'LeadScore']
  
  with open('more_data.csv', 'w', newline='', encoding='utf-8') as \
       csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(leads)
  
  print(f"Generated {len(leads)} lead records from March 15 - July 4, 2024")
  print("Data saved to 'extended_lead_data.csv'")
  
  # Print some sample records
  print("\nSample records:")
  for i, lead in enumerate(leads[:5]):
    print(f"Lead {lead['LeadID']}: {lead['UserName']} - "
          f"Score: {lead['LeadScore']}")

if __name__ == "__main__":
  main()