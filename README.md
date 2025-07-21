# TestRail to Azure DevOps Migrator

## 🚀 What It Does
This script:
- Connects to your TestRail project using their API
- Reads all test cases
- Pushes them into Azure DevOps as Test Case work items

## ⚙️ Setup
1. Replace credentials in `migrator.py`:
   - TestRail domain, project ID, user, API key
   - Azure DevOps organization, project, and PAT token

2. Install dependencies (if not already):
```bash
pip install requests
```

3. Run the script:
```bash
python migrator.py
```

## 🔐 Security Tips
- Use environment variables instead of hardcoding keys in production
- Rotate your tokens regularly
