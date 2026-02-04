

from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
import os
from decimal import Decimal

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")

# AWS Clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get("DYNAMODB_REGION", "us-east-1"))
sns_client = boto3.client('sns', region_name=os.environ.get("SNS_REGION", "us-east-1"))
sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

# DynamoDB Tables
users_table = dynamodb.Table('users')
blood_requests_table = dynamodb.Table('blood_requests')
donation_history_table = dynamodb.Table('donation_history')
blood_inventory_table = dynamodb.Table('blood_inventory')
notifications_table = dynamodb.Table('notifications')
appointments_table = dynamodb.Table('appointments')

# Admin Credentials
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@bloodbridge.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Blood Compatibility
blood_compatibility = {
    "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+": ["O+", "A+", "B+", "AB+"],
    "A-": ["A-", "A+", "AB-", "AB+"],
    "A+": ["A+", "AB+"],
    "B-": ["B-", "B+", "AB-", "AB+"],
    "B+": ["B+", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+"]
}

# Helper Functions
def can_donate(user_id):
    response = donation_history_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user_id))
    user_donations = response['Items']
    if not user_donations:
        return True
    last_date = max(datetime.strptime(d['date'], "%Y-%m-%d") for d in user_donations)
    return datetime.now() - last_date >= timedelta(days=90)

def get_available_inventory(blood_group):
    response = blood_inventory_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('blood_group').eq(blood_group) & boto3.dynamodb.conditions.Attr('units').gt(0))
    return response['Items']

def get_matching_donors(blood_group, location):
    response = donation_history_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('blood_group').eq(blood_group) & boto3.dynamodb.conditions.Attr('location').eq(location))
    matched = []
    for d in response['Items']:
        if can_donate(d['user_id']):
            matched.append(d)
    return matched

# Routes
@app.route('/')
def index():
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        dob = request.form["dob"]
        gender = request.form["gender"]
        blood_group = request.form["blood_group"]
        address = request.form["address"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("signup"))

        response = users_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('email').eq(email))
        if response['Items']:
            flash("Email already registered", "danger")
            return redirect(url_for("signup"))

        user_id = str(len(users_table.scan()['Items']) + 1)
        users_table.put_item(Item={
            "id": user_id,
            "name": name,
            "email": email,
            "phone": phone,
            "dob": dob,
            "gender": gender,
            "blood_group": blood_group,
            "address": address,
            "password": generate_password_hash(password),
            "role": "user"
        })
        flash("Signup successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        response = users_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('email').eq(email))
        user = response['Items'][0] if response['Items'] else None
        if user and check_password_hash(user['password'], password):
            session['user'] = {'id': user['id'], 'email': user['email']}
            flash("Login successful", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid email or password", "danger")
    return render_template("login.html")

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials", "danger")
    return render_template("admin_login.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    users = users_table.scan()['Items']
    requests = blood_requests_table.scan()['Items']
    inventory = blood_inventory_table.scan()['Items']
    donations = donation_history_table.scan()['Items']
    notifications = notifications_table.scan()['Items']
    return render_template("admin_dashboard.html", users=users, requests=requests, inventory=inventory, donations=donations, notifications=notifications)

@app.route("/approve_request/<req_id>")
def approve_request(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    blood_requests_table.update_item(
        Key={'id': req_id},
        UpdateExpression="SET #s = :val",
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':val': 'Approved'}
    )
    flash("Request approved", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/delete_request/<req_id>")
def delete_request(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    blood_requests_table.delete_item(Key={'id': req_id})
    flash("Request deleted", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/update_inventory", methods=["POST"])
def update_inventory():
    if "admin" not in session:
        return {"error": "Unauthorized"}, 401
    blood_group = request.form.get("blood_group")
    units = int(request.form.get("units"))
    location = request.form.get("location")
    blood_inventory_table.put_item(Item={"blood_group": blood_group, "units": units, "location": location})
    return {"message": "Inventory updated successfully"}

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    user = users_table.get_item(Key={'id': session["user"]["id"]})['Item']
    user_notifications = notifications_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user['id']))['Items']
    requests = blood_requests_table.scan()['Items']
    enriched_requests = []
    for req in requests:
        enriched_requests.append({
            "request": req,
            "inventory": get_available_inventory(req["blood_group"]),
            "donors": get_matching_donors(req["blood_group"], req["location"])
        })
    user_appointments = appointments_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user['id']))['Items']
    
    available_donors = []
    if request.method == "POST":
        blood_type = request.form.get('blood_type')
        if blood_type:
            compatible_types = blood_compatibility.get(blood_type, [])
            users_response = users_table.scan()
            available_donors = [
                {'id': u['id'], 'name': u['name'], 'phone': u['phone'], 'blood_group': u['blood_group'], 'address': u['address']}
                for u in users_response['Items']
                if u['blood_group'] in compatible_types and can_donate(u['id'])
            ]
    
    return render_template("dashboard.html", user=user, notifications=user_notifications, enriched_requests=enriched_requests, appointments=user_appointments, donors=available_donors)

@app.route('/api/search_donors', methods=['POST'])
def api_search_donors():
    if "user" not in session:
        return {'error': 'Unauthorized'}, 401

    blood_type = request.json.get('blood_type')
    location = request.json.get('location', '').lower()

    if not blood_type:
        return {'error': 'Blood type required'}, 400

    compatible_types = blood_compatibility.get(blood_type, [])

    inventory_results = blood_inventory_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('blood_group').in_(compatible_types) & boto3.dynamodb.conditions.Attr('units').gt(0))['Items']
    if location:
        inventory_results = [i for i in inventory_results if location in i["location"].lower()]

    donor_results = []
    users_response = users_table.scan()
    for u in users_response['Items']:
        if u["blood_group"] in compatible_types and can_donate(u["id"]) and (not location or location in u["address"].lower()):
            donor_results.append({
                "name": u["name"],
                "phone": u["phone"],
                "blood_group": u["blood_group"],
                "address": u["address"]
            })

    return {
        "inventory": inventory_results,
        "donors": donor_results
    }

@app.route("/request_blood", methods=["GET", "POST"])
def request_blood():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("request_blood.html")

    request_id = str(len(blood_requests_table.scan()['Items']) + 1)
    new_request = {
        "id": request_id,
        "blood_group": request.form["blood_group"],
        "units": request.form["units"],
        "priority": request.form["priority"],
        "location": request.form["location"],
        "requested_by": session["user"]["email"],
        "status": "Pending"
    }

    blood_requests_table.put_item(Item=new_request)

    # Notify donors via SNS
    message = f"Urgent {new_request['blood_group']} blood needed at {new_request['location']}"
    sns_client.publish(TopicArn=sns_topic_arn, Message=message, Subject="Blood Request Alert")

    # Add notifications to table
    users_response = users_table.scan()
    for u in users_response['Items']:
        if u["email"] == session["user"]["email"]:
            continue
        if new_request["blood_group"] in blood_compatibility.get(u["blood_group"], []) and can_donate(u["id"]):
            notifications_table.put_item(Item={
                "id": str(len(notifications_table.scan()['Items']) + 1),
                "user_id": u["id"],
                "request_id": request_id,
                "message": message
            })

    flash("Blood request submitted successfully", "success")
    return redirect(url_for("dashboard"))

@app.route("/donate", methods=["GET", "POST"])
def donate_blood():
    if "user" not in session:
        return redirect(url_for("login"))

    request_id = request.args.get("request_id")

    if request.method == "POST":
        blood_group = request.form.get("blood_group")
        location = request.form.get("location")

        if not blood_group or not location:
            flash("Please fill all fields", "danger")
            return redirect(url_for("dashboard"))

        if not can_donate(session["user"]["id"]):
            flash("You can donate blood only once every 3 months", "danger")
            return redirect(url_for("dashboard"))

        donation_history_table.put_item(Item={
            "user_id": session["user"]["id"],
            "blood_group": blood_group,
            "location": location,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "request_id": request_id
        })

        if request_id:
            blood_requests_table.update_item(
                Key={'id': request_id},
                UpdateExpression="SET #s = :val",
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':val': 'Completed'}
            )

        flash("Thank you for donating blood!", "success")
        return redirect(url_for("dashboard"))

    return render_template("donate.html")

@app.route("/add_appointment", methods=["POST"])
def add_appointment():
    if "user" not in session:
        return redirect(url_for("login"))
    appointments_table.put_item(Item={
        "id": str(len(appointments_table.scan()['Items']) + 1),
        "user_id": session["user"]["id"],
        "date": request.form["date"],
        "location": "Community Center"
    })
    flash("Appointment added", "success")
    return redirect(url_for("dashboard"))

@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        blood_group = request.form.get("blood_group")
        units = request.form.get("units")
        location = request.form.get("location")

        if not blood_group or not units or not location:
            flash("All fields are required", "danger")
            return redirect(url_for("inventory"))

        notifications_table.put_item(Item={
            "id": str(len(notifications_table.scan()['Items']) + 1),
            "type": "inventory_request",
            "blood_group": blood_group,
            "units": int(units),
            "location": location,
            "requested_by": session["user"]["email"],
            "status": "Pending"
        })

        flash("Inventory request submitted successfully", "success")
        return redirect(url_for("dashboard"))

    inventory_items = blood_inventory_table.scan()['Items']
    return render_template("inventory.html", inventory=inventory_items)

@app.route("/approve_inventory/<req_id>")
def approve_inventory(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    notification = notifications_table.get_item(Key={'id': req_id})['Item']
    if notification['status'] == "Pending":
        notifications_table.update_item(
            Key={'id': req_id},
            UpdateExpression="SET #s = :val",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':val': 'Approved'}
        )

        # Update inventory
        response = blood_inventory_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('blood_group').eq(notification['blood_group']) & boto3.dynamodb.conditions.Attr('location').eq(notification['location']))
        if response['Items']:
            item = response['Items'][0]
            blood_inventory_table.update_item(
                Key={'blood_group': item['blood_group'], 'location': item['location']},
                UpdateExpression="SET units = units + :inc",
                ExpressionAttributeValues={':inc': Decimal(notification['units'])}
            )
        else:
            blood_inventory_table.put_item(Item={
                "blood_group": notification['blood_group'],
                "units": notification['units'],
                "location": notification['location']
            })

    flash("Inventory request approved", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/reject_inventory/<req_id>")
def reject_inventory(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    notifications_table.update_item(
        Key={'id': req_id},
        UpdateExpression="SET #s = :val",
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':val': 'Rejected'}
    )

    flash("Inventory request rejected", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))

@app.route('/about')
def about():
    return render_template('aboutus.html')

@app.route('/request_blood_page')
def request_blood_page():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template('request_blood.html')

# Run App
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)