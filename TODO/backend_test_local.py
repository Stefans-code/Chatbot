import requests
import sys
import json
import io
from datetime import datetime
from PIL import Image

class SebastianChatLocalTester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.user_token = None
        self.admin_token = None
        self.test_chat_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, description="", timeout=30, files=None):
        """Run a single API test"""
        url = f"{self.api_url}{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        # Only set Content-Type for JSON requests
        if not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        if description:
            print(f"   Description: {description}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                if files:
                    # For file uploads, don't set Content-Type (let requests handle it)
                    headers.pop('Content-Type', None)
                    response = requests.post(url, data=data, files=files, headers=headers, timeout=timeout)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error details: {error_detail}")
                except:
                    print(f"   Response text: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_quick_flow(self):
        """Test a quick flow to verify basic functionality"""
        print("🚀 QUICK BACKEND FUNCTIONALITY TEST")
        
        # 1. Register user
        test_user = f"quicktest_{datetime.now().strftime('%H%M%S')}"
        success, response = self.run_test(
            "Quick Registration",
            "POST",
            "/register",
            200,
            data={"username": test_user, "password": "password123"},
            description="Quick user registration test"
        )
        if not success:
            return False
        
        self.user_token = response['token']
        
        # 2. Get chat
        success, response = self.run_test(
            "Quick Chat Creation",
            "GET",
            "/chat",
            200,
            token=self.user_token,
            description="Quick chat creation test"
        )
        if not success:
            return False
            
        self.test_chat_id = response['id']
        
        # 3. Send simple message
        success, response = self.run_test(
            "Quick Message Send",
            "POST",
            f"/chat/{self.test_chat_id}/message",
            200,
            data={"content": "Hello Sebastian!"},
            token=self.user_token,
            description="Quick message send test",
            timeout=45
        )
        if not success:
            return False
            
        # 4. Check messages
        import time
        time.sleep(3)  # Wait for AI response
        
        success, messages = self.run_test(
            "Quick Message Retrieval",
            "GET",
            f"/chat/{self.test_chat_id}/messages",
            200,
            token=self.user_token,
            description="Quick message retrieval test"
        )
        
        if success and messages:
            user_msgs = [m for m in messages if m['sender'] == 'user']
            sebastian_msgs = [m for m in messages if m['sender'] == 'sebastian']
            print(f"   Messages found: {len(user_msgs)} user, {len(sebastian_msgs)} Sebastian")
            
            if sebastian_msgs:
                print(f"   Sebastian's response: {sebastian_msgs[-1]['content'][:100]}...")
                return True
        
        return False

def main():
    print("🤖 Sebastian Michaelis Local Backend Test")
    print("=" * 50)
    
    tester = SebastianChatLocalTester()
    
    # Run quick test
    success = tester.test_quick_flow()
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 RESULTS")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if success:
        print("🎉 Local backend is working correctly!")
        print("✅ AI integration is functional")
        print("✅ Sebastian responses are being generated")
        return 0
    else:
        print("❌ Local backend has issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())