import requests
import json
import time

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

# === HEADERS ===
testrail_auth = (TESTRAIL_USER, TESTRAIL_API_KEY)
ado_auth = ('', ADO_PAT)
ado_headers = {
    'Content-Type': 'application/json'
}

def normalize_suite_name(name):
    return name.strip().lower()

print("Fetching sections from TestRail...")
sections_response = requests.get(
    f'{TESTRAIL_URL}index.php?/api/v2/get_sections/{TESTRAIL_PROJECT_ID}&suite_id={TESTRAIL_SUITE_ID}',
    auth=testrail_auth
)

try:
    sections_data = sections_response.json()
except Exception as e:
    print(f"❌ Error decoding TestRail sections response: {e}\n{sections_response.text}")
    exit(1)

if isinstance(sections_data, dict) and sections_data.get("error"):
    print(f"❌ Error fetching sections: {sections_data['error']}")
    exit(1)

sections = sections_data.get("sections", sections_data if isinstance(sections_data, list) else [])

print("Fetching test cases from TestRail...")
cases_response = requests.get(
    f'{TESTRAIL_URL}index.php?/api/v2/get_cases/{TESTRAIL_PROJECT_ID}&suite_id={TESTRAIL_SUITE_ID}',
    auth=testrail_auth
)

try:
    cases_data = cases_response.json()
except Exception as e:
    print(f"❌ Error decoding TestRail cases response: {e}\n{cases_response.text}")
    exit(1)

if isinstance(cases_data, dict) and cases_data.get('error'):
    print(f"❌ Error fetching test cases: {cases_data['error']}")
    exit(1)

cases = cases_data.get("cases", [])

cases_by_section = {}
for case in cases:
    section_id = case['section_id']
    cases_by_section.setdefault(section_id, []).append(case)

print("Fetching nested test suites from ADO...")
existing_suites = {}

def fetch_all_suites(parent_id):
    url = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/test/plans/{ADO_PLAN_ID}/suites/{parent_id}/suites?api-version=6.0"
    response = requests.get(url, auth=ado_auth)
    try:
        suites = response.json().get("value", [])
        for suite in suites:
            key = (normalize_suite_name(suite['name']), int(suite['parent']['id']))
            if key not in existing_suites:
                existing_suites[key] = suite['id']
                fetch_all_suites(suite['id'])
    except Exception as e:
        print(f"❌ Error fetching child suites: {e}\n{response.text}")

fetch_all_suites(ADO_STATIC_SUITE_PARENT_ID)
time.sleep(2)

added_test_cases = set()

for section in sections:
    section_name = section['name']
    section_id = section['id']
    key = (normalize_suite_name(section_name), ADO_STATIC_SUITE_PARENT_ID)

    if key in existing_suites:
        new_suite_id = existing_suites[key]
        print(f"✅ Using existing test suite: {section_name} (ID: {new_suite_id})")
    else:
        print(f"Creating test suite for section: {section_name}")
        suite_response = requests.post(
            f'https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/test/plans/{ADO_PLAN_ID}/suites/{ADO_STATIC_SUITE_PARENT_ID}/suites?api-version=6.0',
            auth=ado_auth,
            headers=ado_headers,
            json={"name": section_name, "suiteType": "StaticTestSuite"}
        )

        try:
            suite_data = suite_response.json()
        except Exception as e:
            print(f"❌ Error decoding suite creation response: {e}\n{suite_response.text}")
            continue

        if suite_response.status_code in [200, 201] and 'id' in suite_data:
            new_suite_id = suite_data['id']
            print(f"✅ Created suite '{section_name}' with ID: {new_suite_id}")
            existing_suites[(normalize_suite_name(section_name), ADO_STATIC_SUITE_PARENT_ID)] = new_suite_id
            time.sleep(2)
        else:
            print(f"❌ Failed to create suite: {suite_data}")
            continue

    for case in cases_by_section.get(section_id, []):
        case_title = case['title']
        if case_title in added_test_cases:
            print(f"⚠️ Skipping duplicate test case: {case_title}")
            continue

        added_test_cases.add(case_title)

        description = case.get('custom_preconds', '')
        steps = case.get('custom_steps', '')
        expected = case.get('custom_expected', '')
        priority = case.get('priority_id', '')
        automated = case.get('custom_case_automated', '')

        print(f"Adding test case: {case_title}")

        work_item_payload = [
            {"op": "add", "path": "/fields/System.Title", "value": case_title},
            {"op": "add", "path": "/fields/System.Description", "value": f"<b>Preconditions:</b><br>{description}<br><br><b>Expected Result:</b><br>{expected}<br><br><b>Automated:</b> {automated}"},
            {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps},
            {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": priority}
        ]

        work_item_response = requests.post(
            f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/wit/workitems/$Test%20Case?api-version=6.0",
            auth=ado_auth,
            headers={"Content-Type": "application/json-patch+json"},
            json=work_item_payload
        )

        if work_item_response.status_code not in [200, 201]:
            print(f"❌ Failed to create work item: {work_item_response.status_code} → {work_item_response.text}")
            continue

        try:
            response_json = work_item_response.json()
            test_case_id = response_json['id']
            work_item_type = response_json.get('fields', {}).get('System.WorkItemType', '')

            if work_item_type != "Test Case":
                print(f"❌ Created item is not a Test Case (got: {work_item_type})")
                continue

            print(f"✅ Created test case: https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_workitems/edit/{test_case_id}")

            add_to_suite_response = requests.post(
                f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/test/plans/{ADO_PLAN_ID}/suites/{new_suite_id}/testcases/{test_case_id}?api-version=6.0",
                auth=ado_auth,
                headers=ado_headers
            )

            if add_to_suite_response.status_code not in [200, 201]:
                print(f"❌ Failed to add test case {test_case_id} to suite {new_suite_id}: {add_to_suite_response.status_code} → {add_to_suite_response.text}")

        except Exception as e:
            print(f"❌ Failed to parse JSON response for work item creation: {e}\n{work_item_response.text}")
            continue

        time.sleep(2)

print("\n✅ Migration complete.")
