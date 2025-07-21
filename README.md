# TestRail to Azure DevOps Migrator

## 🚀 What It Does
This script:
- Connects to your TestRail project using their API
- Reads all test cases
- Pushes them into Azure DevOps as Test Case work items

## ⚙️ Setup

### Step 1: Set Up Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   # TestRail Configuration
   TESTRAIL_API_KEY=your_testrail_api_key_here
   
   # Azure DevOps Configuration  
   ADO_PAT=your_azure_devops_personal_access_token_here
   ```

3. Load environment variables before running:
   ```bash
   # On Linux/Mac
   export $(cat .env | xargs)
   
   # On Windows (PowerShell)
   Get-Content .env | ForEach-Object { [Environment]::SetEnvironmentVariable($_.Split('=')[0], $_.Split('=')[1], 'Process') }
   ```

### Step 2: Update Script Configuration

Update the configuration in `testrail_to_ado_migration.py`:
- TestRail domain, project ID, user
- Azure DevOps organization, project details

### Step 3: Install Dependencies

```bash
pip install requests
```

### Step 4: Run the Migration

```bash
python testrail_to_ado_migration.py
```

## 🔐 Security Features
- ✅ Environment variables for sensitive data
- ✅ No hardcoded API keys or tokens
- ✅ `.gitignore` prevents accidental commits
- ✅ GitHub push protection compatible

## 🛠️ Recent Fixes
- Fixed Unicode encoding errors on Windows
- Fixed Azure DevOps authentication issues
- Removed hardcoded secrets for security
- Added proper error handling and logging

## 📋 Requirements
- Python 3.6+
- Valid TestRail API key
- Azure DevOps Personal Access Token with proper permissions:
  - Test management (read & write)
  - Work items (read & write)
