import requests
import sys
import json
import io
from datetime import datetime
from PIL import Image

class SebastianChatAPITester:
    def __init__(self, base_url="https://sebastian-messenger.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.user_token = None
        self.admin_token = None
        self.test_chat_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, description="", timeout=10, files=None):
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

    def test_user_registration(self):
        """Test user registration"""
        test_user = f"testuser_{datetime.now().strftime('%H%M%S')}"
        success, response = self.run_test(
            "User Registration",
            "POST",
            "/register",
            200,
            data={"username": test_user, "password": "password123"},
            description="Register a new user account"
        )
        if success and 'token' in response:
            self.user_token = response['token']
            print(f"   Registered user: {test_user}")
            return True, test_user
        return False, None

    def test_user_login(self, username):
        """Test user login"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "/login",
            200,
            data={"username": username, "password": "password123"},
            description="Login with registered user credentials"
        )
        if success and 'token' in response:
            self.user_token = response['token']
            return True
        return False

    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "/admin/login",
            200,
            data={"username": "admin", "password": "sebastian_admin"},
            description="Login with admin credentials"
        )
        if success and 'token' in response:
            self.admin_token = response['token']
            return True
        return False

    def test_get_or_create_chat(self):
        """Test getting or creating a chat"""
        success, response = self.run_test(
            "Get/Create Chat",
            "GET",
            "/chat",
            200,
            token=self.user_token,
            description="Get or create user chat session"
        )
        if success and 'id' in response:
            self.test_chat_id = response['id']
            print(f"   Chat ID: {self.test_chat_id}")
            return True
        return False

    def test_send_message(self, message_content, timeout=30):
        """Test sending a message with longer timeout for AI responses"""
        success, response = self.run_test(
            f"Send Message: '{message_content}'",
            "POST",
            f"/chat/{self.test_chat_id}/message",
            200,
            data={"content": message_content},
            token=self.user_token,
            description="Send user message and get Sebastian AI response",
            timeout=timeout
        )
        return success

    def test_get_messages(self, timeout=15):
        """Test getting chat messages"""
        success, response = self.run_test(
            "Get Messages",
            "GET",
            f"/chat/{self.test_chat_id}/messages",
            200,
            token=self.user_token,
            description="Retrieve chat messages",
            timeout=timeout
        )
        if success:
            print(f"   Found {len(response)} messages")
            # Check if we have both user and Sebastian messages
            user_messages = [msg for msg in response if msg['sender'] == 'user']
            sebastian_messages = [msg for msg in response if msg['sender'] == 'sebastian']
            print(f"   User messages: {len(user_messages)}, Sebastian messages: {len(sebastian_messages)}")
            
            # Print last Sebastian response for verification
            if sebastian_messages:
                last_sebastian = sebastian_messages[-1]
                print(f"   Last Sebastian response: {last_sebastian['content'][:100]}...")
            
            return True, response
        return False, []

    def test_admin_get_chats(self):
        """Test admin getting all chats"""
        success, response = self.run_test(
            "Admin Get All Chats",
            "GET",
            "/admin/chats",
            200,
            token=self.admin_token,
            description="Admin retrieve all chat sessions"
        )
        if success:
            print(f"   Found {len(response)} chats")
            return True, response
        return False, []

    def test_admin_respond(self, message_content):
        """Test admin responding to a chat"""
        success, response = self.run_test(
            f"Admin Response: '{message_content}'",
            "POST",
            f"/admin/chat/{self.test_chat_id}/respond",
            200,
            data={"chat_id": self.test_chat_id, "content": message_content},
            token=self.admin_token,
            description="Admin send message as Sebastian"
        )
        return success

    def test_admin_toggle_active(self):
        """Test admin toggling active status"""
        success, response = self.run_test(
            "Admin Toggle Active",
            "POST",
            f"/admin/chat/{self.test_chat_id}/toggle-active",
            200,
            token=self.admin_token,
            description="Toggle admin active status for chat"
        )
        if success and 'admin_active' in response:
            print(f"   Admin active status: {response['admin_active']}")
            return True, response['admin_active']
        return False, None

    def create_test_image(self):
        """Create a simple test image for upload testing"""
        # Create a simple 100x100 red image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        return img_bytes

    def test_image_upload(self, caption="Test image upload", timeout=30):
        """Test image upload functionality"""
        try:
            # Create test image
            test_image = self.create_test_image()
            
            success, response = self.run_test(
                "Image Upload",
                "POST",
                f"/chat/{self.test_chat_id}/upload",
                200,
                data={"caption": caption},
                files={"file": ("test_image.jpg", test_image, "image/jpeg")},
                token=self.user_token,
                description="Upload image and get Sebastian's elegant response",
                timeout=timeout
            )
            
            if success and 'image_url' in response:
                print(f"   Image uploaded successfully: {response['image_url']}")
                return True, response['image_url']
            return False, None
            
        except Exception as e:
            print(f"❌ Image upload failed - Error: {str(e)}")
            return False, None

    def test_multilingual_responses(self):
        """Test Sebastian's multilingual capabilities"""
        multilingual_tests = [
            ("Sebastian, dimmi qualcosa di molto elegante su te stesso", "Italian"),
            ("Hello Sebastian, can you speak English?", "English"),
            ("Bonjour Sebastian, parlez-vous français?", "French"),
            ("Hola Sebastian, ¿hablas español?", "Spanish")
        ]
        
        all_passed = True
        for message, language in multilingual_tests:
            print(f"\n🌍 Testing {language} conversation...")
            success = self.test_send_message(message, timeout=35)
            if not success:
                all_passed = False
                print(f"   Failed {language} test: {message}")
            else:
                # Wait a bit and check the response
                import time
                time.sleep(2)
                success, messages = self.test_get_messages(timeout=15)
                if success and messages:
                    # Find Sebastian's response to this message
                    sebastian_responses = [msg for msg in messages if msg['sender'] == 'sebastian']
                    if sebastian_responses:
                        last_response = sebastian_responses[-1]['content']
                        print(f"   Sebastian's {language} response: {last_response[:150]}...")
        
        return all_passed

    def test_sebastian_responses(self):
        """Test different types of Sebastian responses"""
        test_messages = [
            ("Ciao Sebastian", "greeting"),
            ("Bravo Sebastian!", "compliment"),
            ("Come stai?", "question"),
            ("Arrivederci", "farewell"),
            ("Test message", "default")
        ]
        
        all_passed = True
        for message, msg_type in test_messages:
            success = self.test_send_message(message)
            if not success:
                all_passed = False
                print(f"   Failed to send {msg_type} message: {message}")
        
        return all_passed

def main():
    print("🤖 Sebastian Michaelis Chat API Testing")
    print("=" * 50)
    
    tester = SebastianChatAPITester()
    
    # Test 1: User Registration
    print("\n📝 TESTING USER AUTHENTICATION")
    success, username = tester.test_user_registration()
    if not success:
        print("❌ User registration failed, stopping tests")
        return 1

    # Test 2: User Login
    success = tester.test_user_login(username)
    if not success:
        print("❌ User login failed, stopping tests")
        return 1

    # Test 3: Admin Login
    print("\n👑 TESTING ADMIN AUTHENTICATION")
    success = tester.test_admin_login()
    if not success:
        print("❌ Admin login failed, continuing with user tests only")

    # Test 4: Chat Creation
    print("\n💬 TESTING CHAT FUNCTIONALITY")
    success = tester.test_get_or_create_chat()
    if not success:
        print("❌ Chat creation failed, stopping tests")
        return 1

    # Test 5: Basic Sebastian Response (single test first)
    print("\n🎭 TESTING BASIC SEBASTIAN RESPONSE")
    success = tester.test_send_message("Ciao Sebastian, come stai?", timeout=35)
    if not success:
        print("❌ Basic Sebastian response failed")
    else:
        # Wait for AI response to be processed
        import time
        time.sleep(3)
        
        # Check messages
        success, messages = tester.test_get_messages(timeout=15)
        if success and messages:
            sebastian_responses = [msg for msg in messages if msg['sender'] == 'sebastian']
            if sebastian_responses:
                print(f"✅ Sebastian responded: {sebastian_responses[-1]['content'][:100]}...")
            else:
                print("⚠️ No Sebastian response found")

    # Test 6: Image Upload
    print("\n📷 TESTING IMAGE UPLOAD")
    success, image_url = tester.test_image_upload("Una bella immagine di test per Sebastian")
    if success:
        print(f"✅ Image upload successful: {image_url}")
        # Wait for Sebastian's response to the image
        import time
        time.sleep(5)
        success, messages = tester.test_get_messages(timeout=15)
        if success:
            image_responses = [msg for msg in messages if msg.get('message_type') == 'image']
            if image_responses:
                print(f"✅ Found {len(image_responses)} image messages")
    else:
        print("❌ Image upload failed")

    # Test 7: Multilingual Responses
    print("\n🌍 TESTING MULTILINGUAL CAPABILITIES")
    success = tester.test_multilingual_responses()
    if not success:
        print("⚠️ Some multilingual tests failed")

    # Test 8: Admin Functions (if admin login worked)
    if tester.admin_token:
        print("\n🔧 TESTING ADMIN FUNCTIONS")
        
        # Get all chats
        success, chats = tester.test_admin_get_chats()
        
        # Toggle admin active
        success, active_status = tester.test_admin_toggle_active()
        
        # Admin respond
        success = tester.test_admin_respond("*si inchina elegantemente* Un messaggio dall'amministratore, mio signore.")
        
        # Check messages after admin response
        success, updated_messages = tester.test_get_messages(timeout=15)

    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 FINAL RESULTS")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️ {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())