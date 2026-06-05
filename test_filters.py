import sys, os; sys.path.append(os.path.join(os.getcwd(), 'src'))
from routers.jobs import _search_terms
import requests

expanded_terms = _search_terms('DevOps Engineer')
r = requests.get('https://remotive.com/api/remote-jobs?search=devops%20engineer&limit=50')
jobs = r.json().get('jobs', [])

for item in jobs:
    title = item.get('title', '').lower()
    desc = item.get('description', '').lower()
    
    passed_exact = any(term.lower() in title or term.lower() in desc for term in expanded_terms)
    
    print(f"{item.get('title')[:30]:<30} | Exact: {passed_exact}")
