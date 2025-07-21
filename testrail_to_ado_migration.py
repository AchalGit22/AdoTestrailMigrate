import requests
import json
import time
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
# TestRail details
TESTRAIL_URL = "https://as0108.testrail.io/"
TESTRAIL_PROJECT_ID = 1
TESTRAIL_SUITE_ID = 2
TESTRAIL_USER = "achal01@live.in"
TESTRAIL_API_KEY = "WscprQ3NPh7EHWRqCe4b-B8CVwzSC/8gQ7NvfwKsc"

# Azure DevOps details
ADO_ORG = 'amaditya902'
ADO_PROJECT = 'TestPro'
ADO_PAT = '1ibVmwpy5iEWOE9KVPVWS3DW7cDucaQHqAxB2MBjyswNi79xTpiJJQQJ99BGACAAAAAAAAAAAAASAZDO2Oor'
ADO_PLAN_ID = 3
ADO_STATIC_SUITE_PARENT_ID = 4

# Rate limiting
REQUEST_DELAY = 1  # seconds between requests

# === HEADERS ===
testrail_auth = (TESTRAIL_USER, TESTRAIL_API_KEY)
ado_auth = ('', ADO_PAT)
ado_headers = {
    'Content-Type': 'application/json'
}

class TestRailMigrator:
    def __init__(self):
        self.existing_suites = {}
        self.added_test_cases = set()
        self.priority_mapping = {
            1: 4,  # Low
            2: 3,  # Medium  
            3: 2,  # High
            4: 1   # Critical
        }
        self.automation_status_mapping = {
            0: "Not Automated",
            1: "Automated", 
            2: "To Be Automated"
        }
    
    def normalize_suite_name(self, name: str) -> str:
        """Normalize suite name for comparison"""
        return name.strip().lower()
    
    def make_request(self, method: str, url: str, auth: tuple, headers: dict = None, 
                    json_data: dict = None, timeout: int = 30) -> requests.Response:
        """Make HTTP request with error handling and rate limiting"""
        try:
            time.sleep(REQUEST_DELAY)
            response = requests.request(
                method=method, 
                url=url, 
                auth=auth, 
                headers=headers, 
                json=json_data,
                timeout=timeout
            )
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def fetch_testrail_data(self, endpoint: str, params: dict = None) -> dict:
        """Fetch data from TestRail API with error handling"""
        url = f'{TESTRAIL_URL}index.php?/api/v2/{endpoint}'
        if params:
            url += '&' + '&'.join([f'{k}={v}' for k, v in params.items()])
        
        response = self.make_request('GET', url, testrail_auth)
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding TestRail response: {e}\nResponse: {response.text}")
            raise
        
        if isinstance(data, dict) and data.get("error"):
            logger.error(f"TestRail API error: {data['error']}")
            raise Exception(f"TestRail API error: {data['error']}")
        
        return data
    
    def fetch_sections(self) -> List[dict]:
        """Fetch sections from TestRail"""
        logger.info("Fetching sections from TestRail...")
        data = self.fetch_testrail_data(
            f'get_sections/{TESTRAIL_PROJECT_ID}',
            {'suite_id': TESTRAIL_SUITE_ID}
        )
        sections = data.get("sections", data if isinstance(data, list) else [])
        logger.info(f"Found {len(sections)} sections")
        return sections
    
    def fetch_test_cases(self) -> List[dict]:
        """Fetch test cases from TestRail"""
        logger.info("Fetching test cases from TestRail...")
        data = self.fetch_testrail_data(
            f'get_cases/{TESTRAIL_PROJECT_ID}',
            {'suite_id': TESTRAIL_SUITE_ID}
        )
        cases = data.get("cases", [])
        logger.info(f"Found {len(cases)} test cases")
        return cases
    
    def fetch_ado_suites(self, parent_id: int):
        """Recursively fetch all ADO test suites"""
        url = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/test/plans/{ADO_PLAN_ID}/suites/{parent_id}/suites?api-version=6.0"
        
        try:
            response = self.make_request('GET', url, ado_auth)
            if response.status_code == 200:
                suites = response.json().get("value", [])
                for suite in suites:
                    key = (self.normalize_suite_name(suite['name']), int(suite['parent']['id']))
                    if key not in self.existing_suites:
                        self.existing_suites[key] = suite['id']
                        self.fetch_ado_suites(suite['id'])  # Recursively fetch child suites
        except Exception as e:
            logger.warning(f"Error fetching child suites for parent {parent_id}: {e}")
    
    def create_ado_suite(self, section_name: str, parent_id: int) -> Optional[int]:
        """Create a new test suite in ADO"""
        logger.info(f"Creating test suite: {section_name}")
        
        url = f'https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/test/plans/{ADO_PLAN_ID}/suites/{parent_id}/suites?api-version=6.0'
        payload = {
            "name": section_name,
            "suiteType": "StaticTestSuite"
        }
        
        response = self.make_request('POST', url, ado_auth, ado_headers, payload)
        
        if response.status_code in [200, 201]:
            suite_data = response.json()
            if 'id' in suite_data:
                suite_id = suite_data['id']
                logger.info(f"✅ Created suite '{section_name}' with ID: {suite_id}")
                key = (self.normalize_suite_name(section_name), parent_id)
                self.existing_suites[key] = suite_id
                return suite_id
        
        logger.error(f"❌ Failed to create suite '{section_name}': {response.status_code} - {response.text}")
        return None
    
    def format_steps(self, steps_data: str) -> str:
        """Format test steps for ADO"""
        if not steps_data:
            return ""
        
        # If steps are in JSON format, parse and format them
        try:
            if steps_data.startswith('['):
                steps = json.loads(steps_data)
                formatted_steps = []
                for i, step in enumerate(steps, 1):
                    content = step.get('content', '')
                    expected = step.get('expected', '')
                    formatted_steps.append(f"Step {i}: {content}")
                    if expected:
                        formatted_steps.append(f"Expected: {expected}")
                return '\n'.join(formatted_steps)
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Return as plain text if not JSON
        return str(steps_data)
    
    def create_ado_test_case(self, case: dict, suite_id: int) -> bool:
        """Create a test case in ADO"""
        case_title = case.get('title', 'Untitled Test Case')
        
        # Skip if already added
        if case_title in self.added_test_cases:
            logger.warning(f"⚠️ Skipping duplicate test case: {case_title}")
            return False
        
        self.added_test_cases.add(case_title)
        
        # Extract all relevant fields from TestRail
        description = case.get('custom_preconds', '')
        steps = self.format_steps(case.get('custom_steps', ''))
        expected_result = case.get('custom_expected', '')
        priority_id = case.get('priority_id', 2)  # Default to Medium
        automation_status = case.get('custom_case_automated', 0)
        case_type = case.get('type_id', '')
        template = case.get('template_id', '')
        estimate = case.get('estimate', '')
        milestone = case.get('milestone_id', '')
        references = case.get('refs', '')
        
        # Map priority from TestRail to ADO
        ado_priority = self.priority_mapping.get(priority_id, 3)
        automation_text = self.automation_status_mapping.get(automation_status, "Not Automated")
        
        # Build comprehensive description
        description_parts = []
        if description:
            description_parts.append(f"<b>Prerequisites:</b><br>{description}")
        if expected_result:
            description_parts.append(f"<b>Expected Result:</b><br>{expected_result}")
        
        description_parts.append(f"<b>Automation Status:</b> {automation_text}")
        
        if estimate:
            description_parts.append(f"<b>Estimate:</b> {estimate}")
        if references:
            description_parts.append(f"<b>References:</b> {references}")
        
        full_description = "<br><br>".join(description_parts)
        
        # Create work item payload
        work_item_payload = [
            {"op": "add", "path": "/fields/System.Title", "value": case_title},
            {"op": "add", "path": "/fields/System.Description", "value": full_description},
            {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": ado_priority}
        ]
        
        # Add steps if available
        if steps:
            work_item_payload.append({
                "op": "add", 
                "path": "/fields/Microsoft.VSTS.TCM.Steps", 
                "value": steps
            })
        
        # Add tags for automation status
        work_item_payload.append({
            "op": "add",
            "path": "/fields/System.Tags",
            "value": f"AutomationStatus:{automation_text.replace(' ', '')}"
        })
        
        logger.info(f"Creating test case: {case_title}")
        
        # Create the work item
        url = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/wit/workitems/$Test%20Case?api-version=6.0"
        headers = {"Content-Type": "application/json-patch+json"}
        
        response = self.make_request('POST', url, ado_auth, headers, work_item_payload)
        
        if response.status_code not in [200, 201]:
            logger.error(f"❌ Failed to create work item: {response.status_code} → {response.text}")
            return False
        
        try:
            response_json = response.json()
            test_case_id = response_json['id']
            work_item_type = response_json.get('fields', {}).get('System.WorkItemType', '')
            
            if work_item_type != "Test Case":
                logger.error(f"❌ Created item is not a Test Case (got: {work_item_type})")
                return False
            
            logger.info(f"✅ Created test case: https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_workitems/edit/{test_case_id}")
            
            # Add test case to suite
            return self.add_test_case_to_suite(test_case_id, suite_id)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response: {e}\nResponse: {response.text}")
            return False
    
    def add_test_case_to_suite(self, test_case_id: int, suite_id: int) -> bool:
        """Add test case to ADO test suite"""
        url = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/test/plans/{ADO_PLAN_ID}/suites/{suite_id}/testcases/{test_case_id}?api-version=6.0"
        
        response = self.make_request('POST', url, ado_auth, ado_headers)
        
        if response.status_code not in [200, 201]:
            logger.error(f"❌ Failed to add test case {test_case_id} to suite {suite_id}: {response.status_code} → {response.text}")
            return False
        
        logger.info(f"✅ Added test case {test_case_id} to suite {suite_id}")
        return True
    
    def migrate(self):
        """Main migration method"""
        try:
            logger.info("Starting TestRail to ADO migration...")
            
            # Fetch data from TestRail
            sections = self.fetch_sections()
            cases = self.fetch_test_cases()
            
            # Group cases by section
            cases_by_section = {}
            for case in cases:
                section_id = case.get('section_id')
                if section_id:
                    cases_by_section.setdefault(section_id, []).append(case)
            
            # Fetch existing ADO suites
            logger.info("Fetching existing test suites from ADO...")
            self.fetch_ado_suites(ADO_STATIC_SUITE_PARENT_ID)
            logger.info(f"Found {len(self.existing_suites)} existing suites")
            
            # Process each section
            total_cases_created = 0
            total_cases_failed = 0
            
            for section in sections:
                section_name = section.get('name', 'Unnamed Section')
                section_id = section.get('id')
                
                logger.info(f"\n=== Processing section: {section_name} ===")
                
                # Check if suite already exists
                key = (self.normalize_suite_name(section_name), ADO_STATIC_SUITE_PARENT_ID)
                
                if key in self.existing_suites:
                    suite_id = self.existing_suites[key]
                    logger.info(f"✅ Using existing test suite: {section_name} (ID: {suite_id})")
                else:
                    suite_id = self.create_ado_suite(section_name, ADO_STATIC_SUITE_PARENT_ID)
                    if not suite_id:
                        logger.error(f"❌ Failed to create/find suite for section: {section_name}")
                        continue
                
                # Process test cases in this section
                section_cases = cases_by_section.get(section_id, [])
                logger.info(f"Processing {len(section_cases)} test cases in section '{section_name}'")
                
                for case in section_cases:
                    try:
                        if self.create_ado_test_case(case, suite_id):
                            total_cases_created += 1
                        else:
                            total_cases_failed += 1
                    except Exception as e:
                        logger.error(f"❌ Error creating test case '{case.get('title', 'Unknown')}': {e}")
                        total_cases_failed += 1
            
            # Summary
            logger.info(f"\n✅ Migration complete!")
            logger.info(f"Total test cases created: {total_cases_created}")
            logger.info(f"Total test cases failed: {total_cases_failed}")
            logger.info(f"Total sections processed: {len(sections)}")
            
        except Exception as e:
            logger.error(f"❌ Migration failed with error: {e}")
            raise

if __name__ == "__main__":
    migrator = TestRailMigrator()
    migrator.migrate()