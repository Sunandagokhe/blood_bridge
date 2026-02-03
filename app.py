from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

app = Flask(__name__)
app.secret_key = "secret_key_here"

# -------------------------
# Admin Credentials (temporary)
# -------------------------
ADMIN_EMAIL = "admin@bloodbridge.com"
ADMIN_PASSWORD = "admin123"

# -------------------------
# Data File
# -------------------------
DATA_FILE = "data.json"

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "users": users,
            "blood_requests": blood_requests,
            "donation_history": donation_history,
            "inventory": blood_inventory,
            "notifications": notifications,
            "appointments": appointments
        }, f, indent=4)

def load_data():
    global users, blood_requests, donation_history, blood_inventory, notifications, appointments
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
            users = data.get("users", [])
            blood_requests = data.get("blood_requests", [])
            donation_history = data.get("donation_history", [])
            blood_inventory = data.get("inventory", [])
            notifications = data.get("notifications", [])
            appointments = data.get("appointments", [])
    else:
        # Initialize with sample data
        users = []
        blood_requests = []
        donation_history = [
            {
                "user_id": 1,
                "blood_group": "A+",
                "location": "City Hospital",
                "date": "2026-01-01"
            }
        ]
        blood_inventory = [
            {"blood_group": "A+", "units": 10, "location": "City Hospital"},
            {"blood_group": "B+", "units": 5, "location": "City Hospital"},
            {"blood_group": "O+", "units": 8, "location": "District Hospital"}
        ]
        notifications = []
        appointments = []

# -------------------------
# Blood Compatibility
# -------------------------
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

# -------------------------
# Helper Functions
# -------------------------
def can_donate(user_id):
    user_donations = [d for d in donation_history if d["user_id"] == user_id]
    if not user_donations:
        return True
    last_date = max(datetime.strptime(d["date"], "%Y-%m-%d") for d in user_donations)
    return datetime.now() - last_date >= timedelta(days=90)

def get_available_inventory(blood_group):
    return [item for item in blood_inventory if item["blood_group"] == blood_group and item["units"] > 0]

def get_matching_donors(blood_group, location):
    matched = []
    for d in donation_history:
        if d.get("blood_group") == blood_group and d.get("location") == location and can_donate(d.get("user_id")):
            matched.append(d)
    return matched

# -------------------------
# Routes
# -------------------------
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

        if any(u["email"] == email for u in users):
            flash("Email already registered", "danger")
            return redirect(url_for("signup"))

        users.append({
            "id": len(users) + 1,
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
        save_data()
        flash("Signup successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = next((u for u in users if u['email'] == email), None)
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
    return render_template("admin_dashboard.html", users=users, requests=blood_requests, inventory=blood_inventory, donations=donation_history, notifications=notifications)

@app.route("/approve_request/<int:req_id>")
def approve_request(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    for r in blood_requests:
        if r["id"] == req_id:
            r["status"] = "Approved"
            break
    save_data()
    flash("Request approved", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/delete_request/<int:req_id>")
def delete_request(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    blood_requests[:] = [r for r in blood_requests if r["id"] != req_id]
    save_data()
    flash("Request deleted", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/update_inventory", methods=["POST"])
def update_inventory():
    if "admin" not in session:
        return {"error": "Unauthorized"}, 401
    blood_group = request.form.get("blood_group")
    units = int(request.form.get("units"))
    location = request.form.get("location")
    # Find or add item
    item = next((i for i in blood_inventory if i["blood_group"] == blood_group and i["location"] == location), None)
    if item:
        item["units"] = units
    else:
        blood_inventory.append({"blood_group": blood_group, "units": units, "location": location})
    save_data()
    return {"message": "Inventory updated successfully"}

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    user = next((u for u in users if u["id"] == session["user"]["id"]), None)
    user_notifications = [n for n in notifications if n.get("user_id") == user["id"]]
    enriched_requests = []
    for req in blood_requests:
        enriched_requests.append({
            "request": req,
            "inventory": get_available_inventory(req["blood_group"]),
            "donors": get_matching_donors(req["blood_group"], req["location"])
        })
    user_appointments = [a for a in appointments if a["user_id"] == user["id"]]
    
    # Handle search
    available_donors = []
    if request.method == "POST":
        blood_type = request.form.get('blood_type')
        if blood_type:
            compatible_types = blood_compatibility.get(blood_type, [])
            available_donors = [
                {'id': u['id'], 'name': u['name'], 'phone': u['phone'], 'blood_group': u['blood_group'], 'address': u['address']}
                for u in users
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

    # ✅ INVENTORY MATCH
    inventory_results = [
        i for i in blood_inventory
        if i["blood_group"] in compatible_types
        and i["units"] > 0
        and (not location or location in i["location"].lower())
    ]

    # ✅ DONOR MATCH
    donor_results = [
        {
            "name": u["name"],
            "phone": u["phone"],
            "blood_group": u["blood_group"],
            "address": u["address"]
        }
        for u in users
        if u["blood_group"] in compatible_types
        and can_donate(u["id"])
        and (not location or location in u["address"].lower())
    ]

    return {
        "inventory": inventory_results,
        "donors": donor_results
    }

@app.route("/request_blood", methods=["GET", "POST"])
def request_blood():
    if "user" not in session:
        return redirect(url_for("login"))

    # ✅ SHOW PAGE
    if request.method == "GET":
        return render_template("request_blood.html")

    # ✅ HANDLE FORM SUBMIT
    request_id = len(blood_requests) + 1
    new_request = {
        "id": request_id,
        "blood_group": request.form["blood_group"],
        "units": request.form["units"],
        "priority": request.form["priority"],
        "location": request.form["location"],
        "requested_by": session["user"]["email"],
        "status": "Pending"
    }

    blood_requests.append(new_request)

    # Notify donors
    for u in users:
        if u["email"] == session["user"]["email"]:
            continue
        if new_request["blood_group"] in blood_compatibility.get(u["blood_group"], []) and can_donate(u["id"]):
            notifications.append({
                "donor_id": u["id"],
                "request_id": request_id,
                "message": f"Urgent {new_request['blood_group']} blood needed at {new_request['location']}"
            })

    save_data()
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

        donation_history.append({
            "user_id": session["user"]["id"],
            "blood_group": blood_group,
            "location": location,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "request_id": request_id
        })

        for r in blood_requests:
            if str(r["id"]) == str(request_id):
                r["status"] = "Completed"

        save_data()
        flash("Thank you for donating blood!", "success")
        return redirect(url_for("dashboard"))

    # GET request → just show page
    return render_template("donate.html")

@app.route("/add_appointment", methods=["POST"])
def add_appointment():
    if "user" not in session:
        return redirect(url_for("login"))
    appointments.append({
        "user_id": session["user"]["id"],
        "date": request.form["date"],
        "location": "Community Center"
    })
    save_data()
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

        # Treat as inventory REQUEST (not direct update)
        notifications.append({
    "id": len(notifications) + 1,
    "type": "inventory_request",
    "blood_group": blood_group,
    "units": int(units),
    "location": location,
    "requested_by": session["user"]["email"],
    "status": "Pending"
})

        save_data()
        flash("Inventory request submitted successfully", "success")
        return redirect(url_for("dashboard"))

    return render_template("inventory.html", inventory=blood_inventory)
@app.route("/approve_inventory/<int:req_id>")
def approve_inventory(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    for n in notifications:
       if n.get("id") == req_id and n["status"] == "Pending":
            n["status"] = "Approved"

            # Update inventory
            item = next(
                (i for i in blood_inventory
                 if i["blood_group"] == n["blood_group"]
                 and i["location"] == n["location"]),
                None
            )

            if item:
                item["units"] += n["units"]
            else:
                blood_inventory.append({
                    "blood_group": n["blood_group"],
                    "units": n["units"],
                    "location": n["location"]
                })
            break

    save_data()
    flash("Inventory request approved", "success")
    return redirect(url_for("admin_dashboard"))
@app.route("/reject_inventory/<int:req_id>")
def reject_inventory(req_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    for n in notifications:
        if n.get("id") == req_id:
            n["status"] = "Rejected"
            break

    save_data()
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

# -------------------------
# Run App
# -------------------------
if __name__ == '__main__':
    load_data()
    app.run(host="0.0.0.0", port=5000, debug=True)