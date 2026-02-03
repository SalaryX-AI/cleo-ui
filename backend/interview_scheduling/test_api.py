"""
Test script for interview scheduling system
Run this to test the API endpoints
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
# BASE_URL = "https://scanandhire.com/scheduling"
BASE_URL = "http://localhost:8001"  # Local testing
API_KEY = "scheduling_key_456"  # Replace with your actual key

# Test data
TEST_APPLICANT = {
    "applicant_name": "Zubier",
    "applicant_phone": "+15082237081",
    "company_name": "Big Chicken",
    "position": "Shift Manager",
    "slots": {
        "Tuesday, January 28, 2025": ["9:00 AM - 10:00 AM", "11:00 AM - 12:00 PM", "2:00 PM - 3:00 PM", "4:00 PM - 5:00 PM"],
        "Wednesday, January 29, 2025": ["10:00 AM - 11:00 AM", "1:00 PM - 2:00 PM", "3:00 PM - 4:00 PM", "5:00 PM - 6:00 PM"]
    },
    "job_id": "job_12345",
    "candidate_id": 67890, 
    "location": "any location",
    "interview_type": "Online Meeting",
    "meeting_link": "https://meet.google.com/abc-defg-hij"
}


def test_health_check():
    """Test the root endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response.status_code == 200


def test_initiate_scheduling():
    """Test initiating interview scheduling"""
    print("\n" + "="*60)
    print("TEST 2: Initiate Scheduling")
    print("="*60)
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    print(f"\nSending request to: {BASE_URL}/api/schedule-interview")
    print(f"Payload: {json.dumps(TEST_APPLICANT, indent=2)}")
    
    response = requests.post(
        f"{BASE_URL}/api/schedule-interview",
        headers=headers,
        json=TEST_APPLICANT
    )
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        return result.get('session_id')
    else:
        print(f"Error: {response.text}")
        return None


def test_check_status(session_id):
    """Test checking scheduling status"""
    print("\n" + "="*60)
    print("TEST 3: Check Status")
    print("="*60)
    
    if not session_id:
        print("⚠️  No session_id provided, skipping test")
        return
    
    headers = {
        "X-API-Key": API_KEY
    }
    
    print(f"\nChecking status for session: {session_id}")
    
    response = requests.get(
        f"{BASE_URL}/api/scheduling-status/{session_id}",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
    else:
        print(f"Error: {response.text}")


def test_invalid_api_key():
    """Test with invalid API key"""
    print("\n" + "="*60)
    print("TEST 4: Invalid API Key (Should Fail)")
    print("="*60)
    
    headers = {
        "X-API-Key": "invalid_key",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/schedule-interview",
        headers=headers,
        json=TEST_APPLICANT
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 403:
        print("✓ Correctly rejected invalid API key")
    else:
        print("✗ Should have rejected invalid API key")


def test_invalid_phone():
    """Test with invalid phone number"""
    print("\n" + "="*60)
    print("TEST 5: Invalid Phone Number (Should Fail)")
    print("="*60)
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    invalid_data = TEST_APPLICANT.copy()
    invalid_data["applicant_phone"] = "123"  # Too short
    
    response = requests.post(
        f"{BASE_URL}/api/schedule-interview",
        headers=headers,
        json=invalid_data
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 422:
        print("✓ Correctly rejected invalid phone number")
    else:
        print("✗ Should have rejected invalid phone number")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("INTERVIEW SCHEDULING API - TEST SUITE")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test 1: Health check
        if not test_health_check():
            print("\n✗ Health check failed - is the server running?")
            return
        
        # Test 2: Initiate scheduling
        session_id = test_initiate_scheduling()
        
        # Test 3: Check status
        if session_id:
            test_check_status(session_id)
        
        # Test 4: Invalid API key
        test_invalid_api_key()
        
        # Test 5: Invalid phone
        test_invalid_phone()
        
        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print("="*60)
        
        if session_id:
            print(f"\n✓ Created test session: {session_id}")
            print(f"✓ Initial SMS should have been sent to: {TEST_APPLICANT['applicant_phone']}")
            print("\nNow you can:")
            print("1. Reply to the SMS from your phone")
            print("2. Watch the console logs in the server")
            print("3. Check status endpoint to see updates")
        
    except requests.exceptions.ConnectionError:
        print("\n✗ Cannot connect to server")
        print(f"Make sure the server is running at {BASE_URL}")
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
