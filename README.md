BloodBridge: AWS-Deployed Blood Donation Management System
Description
BloodBridge is a Flask-based web application for managing blood donations, requests, and inventory. It has been converted for deployment on AWS, utilizing DynamoDB for data persistence and Amazon SNS for sending notifications (e.g., alerts for blood requests via email or SMS). The app supports user registration, blood requests, donations, inventory management, and admin oversight.

This version replaces the original JSON-based storage with AWS services for scalability and reliability.

Features
User Management: Signup, login, and profile management.
Blood Requests: Users can request blood, and admins can approve/reject.
Donations: Track donations with compatibility checks and 3-month cooldown.
Inventory Management: View and update blood stock; users can request inventory additions.
Notifications: SNS-powered alerts for urgent blood needs.
Admin Dashboard: Manage users, requests, inventory, and notifications.
Search Functionality: Find compatible donors and inventory via API.
Prerequisites
Python 3.8+
AWS Account with IAM permissions for DynamoDB and SNS
AWS CLI (optional, for deployment)
Git (for cloning the repo)
Installation
Clone the repository:


Copy code
git clone https://github.com/your-repo/bloodbridge-aws.git
cd bloodbridge-aws
Create a virtual environment:


Copy code
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies:


Copy code
pip install -r requirements.txt
Install AWS CLI (if not already installed):


Copy code
pip install awscli
aws configure  # Set up your AWS credentials
Configuration
Set up the following environment variables (use .env file or AWS console for deployment):

SECRET_KEY: Flask secret key (e.g., a random string).
ADMIN_EMAIL: Admin login email (default: admin@bloodbridge.com).
ADMIN_PASSWORD: Admin login password (default: admin123).
DYNAMODB_REGION: AWS region for DynamoDB (e.g., us-east-1).
SNS_REGION: AWS region for SNS (e.g., us-east-1).
SNS_TOPIC_ARN: ARN of your SNS topic for notifications (create via AWS Console).
AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY: Your AWS credentials (or use IAM roles in production).
AWS Setup
Create DynamoDB Tables:

Use AWS Console or CLI to create tables: users, blood_requests, donation_history, blood_inventory, notifications, appointments.
Set primary keys (e.g., id for most tables).
Optionally, add sample data via AWS Console.
Create SNS Topic:

In AWS Console, create a topic (e.g., "BloodRequestAlerts").
Subscribe donors' emails/phones to the topic for alerts.
Note the Topic ARN for the environment variable.
IAM Permissions:

Attach policies: AmazonDynamoDBFullAccess, AmazonSNSFullAccess to your EC2/EB role.
Deployment to AWS
Option 1: Elastic Beanstalk (Recommended)
Initialize EB:


Copy code
eb init -p python-3.8 bloodbridge-app
Create environment:


Copy code
eb create bloodbridge-env
Set environment variables in EB Console or via CLI:


Copy code
eb setenv SECRET_KEY=your_secret_key DYNAMODB_REGION=us-east-1 ...
Deploy:


Copy code
eb deploy
Access the app: Use the URL provided by EB (e.g., http://bloodbridge-env.eba-xxxx.us-east-1.elasticbeanstalk.com).

Option 2: EC2
Launch an EC2 instance (e.g., t2.micro with Amazon Linux).
SSH into the instance and install dependencies.
Upload your code via SCP or Git.
Run the app with python app.py (use Gunicorn for production: gunicorn -w 4 -b 0.0.0.0:5000 app:app).
Configure a load balancer or domain if needed.
Usage
Local Testing: Run python app.py and visit http://localhost:5000.
Routes:
/: Home page.
/signup and /login: User registration and login.
/dashboard: User dashboard for requests, donations, and search.
/admin_login and /admin_dashboard: Admin panel.
/api/search_donors: API for searching donors/inventory.
Notifications: Blood requests trigger SNS alerts to subscribed users.
Inventory: Admins can update stock; users can request additions.
Dependencies
Flask
boto3
werkzeug
(See requirements.txt for full list)
Troubleshooting
boto3 underline/error: Ensure boto3 is installed (pip install boto3) and your IDE uses the correct Python interpreter.
AWS errors: Check IAM permissions, region settings, and CloudWatch logs.
Deployment issues: Verify requirements.txt and environment variables.
Database issues: Ensure DynamoDB tables exist and are accessible.
