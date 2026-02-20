import requests
import json
from django.conf import settings

APPS_SCRIPT_URL = settings.APPS_SCRIPT_URL
APPS_SCRIPT_TOKEN = settings.APPS_SCRIPT_TOKEN

class GoogleSheetsAPI:
    @staticmethod
    def _get_headers():
        # Passing token in header or query param depending on implementation. 
        # Usually internal tools might not strict auth, but user said "secure this token".
        # Assuming token is passed as a query param or Authorization header.
        # User prompt: "token=EDUSCORE_2026_SECRET secure this tocken into env file"
        # I'll pass it as a query param 'token' alongside action.
        return {}

    @staticmethod
    def get_domains():
        """Fetches available domains (tabs) from Question Bank Spreadsheet."""
        try:
            response = requests.get(
                APPS_SCRIPT_URL, 
                params={'action': 'getDomains', 'token': APPS_SCRIPT_TOKEN}
            )
            response.raise_for_status()
            return response.json() # Expecting ['Android', 'Web', ...]
        except requests.RequestException as e:
            # Log error
            print(f"Error fetching domains: {e}")
            return []

    @staticmethod
    def get_questions(domain):
        """Fetches questions for a specific domain."""
        try:
            response = requests.get(
                APPS_SCRIPT_URL, 
                params={'action': 'getQuestions', 'domain': domain, 'token': APPS_SCRIPT_TOKEN}
            )
            response.raise_for_status()
            return response.json() 
            # Expecting list of dicts: 
            # [{'question_id': 1, 'question_text': '...', 'option_a': '...', ...}]
        except requests.RequestException as e:
            print(f"Error fetching questions for {domain}: {e}")
            return []

    @staticmethod
    def get_candidates(domain):
        """Fetches approved candidates for a specific domain."""
        try:
            response = requests.get(
                APPS_SCRIPT_URL,
                params={'action': 'getCandidates', 'domain': domain, 'token': APPS_SCRIPT_TOKEN}
            )
            response.raise_for_status()
            return response.json()
            # Expecting list of dicts:
            # [{'candidate_id': '...', 'email': '...', 'status': 'approved'}]
        except requests.RequestException as e:
            print(f"Error fetching candidates for {domain}: {e}")
            return []

    @staticmethod
    def append_result(payload):
        """
        Sends result data to Google Sheet.
        Payload should include: 
        candidate_id, name, email, domain, test_code, score, total_marks, percentage, result_status
        """
        try:
            # Ensure token is in payload for POST or as query param
            # Requests post sends form-data by default or json. 
            # Apps Script doPost(e) handles e.postData.contents
            
            data = payload.copy()
            data['action'] = 'appendResult'
            data['token'] = APPS_SCRIPT_TOKEN
            
            # Using data=json.dumps(data) ensures it's sent as raw body which Apps Script reads easily
            response = requests.post(
                APPS_SCRIPT_URL, 
                data=json.dumps(data),
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error appending result: {e}")
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def create_result_sheet(sheet_name):
        """
        Creates a new sheet tab in the Google Spreadsheet.
        Returns {'status': 'success', 'gid': '12345'} or error.
        """
        try:
            payload = {
                'action': 'createSheet',
                'sheetName': sheet_name,
                'token': APPS_SCRIPT_TOKEN
            }
            response = requests.post(
                APPS_SCRIPT_URL,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error creating sheet {sheet_name}: {e}")
            return {'status': 'error', 'message': str(e)}
