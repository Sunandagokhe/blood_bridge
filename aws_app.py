from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
import os
from decimal import Decimal

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")

# AWS Clients (SNS REMOVED)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get("DYNAMODB_REGION", "us-east-1"))

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
    response = donation_history_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user_id)
    )
    user_donations = response['Items']
    if not user_donations:
        return True
    last_date = max(datetime.strptime(d['date'], "%Y-%m-%d") for d in user_donations)
    return datetime.now() - last_date >= timedelta(days=90)

def get_available_inventory(blood_group):
    response = blood_inventory_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('blood_group').eq(blood_group) &
        boto3.dynamodb.conditions.Attr('units').gt(0)
    )
    return response['Items']

def get_matching_donors(blood_group, location):
    response = donation_history_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('blood_group').eq(blood_group) &
        boto3.dynamodb.conditions.Attr('location').eq(location)
    )
    matched = []
    for d in response['Items']:
        if can_donate(d['user_id']):
            matched.append(d)
    return matched

# Routes
@app.route('/')
def index():
    return render_template("index.html")


# SIGNUP
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        email = request.form["email"]

        response = users_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('email').eq(email)
        )

        if response['Items']:
            flash("Email already registered", "danger")
            return redirect(url_for("signup"))

        user_id = str(len(users_table.scan()['Items']) + 1)

        users_table.put_item(Item={
            "id": user_id,
            "name": request.form["name"],
            "email": email,
            "phone": request.form["phone"],
            "dob": request.form["dob"],
            "gender": request.form["gender"],
            "blood_group": request.form["blood_group"],
            "address": request.form["address"],
            "password": generate_password_hash(request.form["password"]),
            "role": "user"
        })

        flash("Signup successful", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        response = users_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('email').eq(email)
        )

        user = response['Items'][0] if response['Items'] else None

        if user and check_password_hash(user['password'], password):

            session['user'] = {
                'id': user['id'],
                'email': user['email']
            }

            flash("Login successful", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")

    return render_template("login.html")


# DASHBOARD
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    user = users_table.get_item(
        Key={'id': session["user"]["id"]}
    )['Item']

    requests = blood_requests_table.scan()['Items']

    enriched_requests = []

    for req in requests:

        enriched_requests.append({
            "request": req,
            "inventory": get_available_inventory(req["blood_group"]),
            "donors": get_matching_donors(req["blood_group"], req["location"])
        })

    return render_template(
        "dashboard.html",
        user=user,
        enriched_requests=enriched_requests
    )


# REQUEST BLOOD (SNS REMOVED)
@app.route("/request_blood", methods=["POST"])
def request_blood():

    if "user" not in session:
        return redirect(url_for("login"))

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

    # SNS REMOVED — ONLY DATABASE NOTIFICATION

    message = f"{new_request['blood_group']} blood needed at {new_request['location']}"

    users_response = users_table.scan()

    for u in users_response['Items']:

        if new_request["blood_group"] in blood_compatibility.get(u["blood_group"], []):

            notifications_table.put_item(Item={

                "id": str(len(notifications_table.scan()['Items']) + 1),

                "user_id": u["id"],

                "message": message
            })

    flash("Blood request submitted", "success")

    return redirect(url_for("dashboard"))


# LOGOUT
@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out", "info")

    return redirect(url_for("index"))


# RUN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
