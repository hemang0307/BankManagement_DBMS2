"""Bank Management System - Flask application (CAM 5 assignment).

Every page runs real SQL queries on MySQL through the helpers in db.py.
All SQL uses %s placeholders (parameterized queries). Sort columns come
from fixed whitelists, so user input is never pasted into SQL text.
"""
import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

import db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-local-demo-key")

# Fixed lists of allowed values (also used to build dropdown menus)
ACCOUNT_TYPES = ["Savings", "Current", "Fixed Deposit"]
LOAN_TYPES = ["Home", "Personal", "Education", "Vehicle", "Business"]
LOCKER_SIZES = ["Small", "Medium", "Large"]
TRANSACTION_TYPES = ["Deposit", "Withdrawal"]


# ---------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------
@app.template_filter("money")
def money(value):
    """Format a number as Indian rupees with 2 decimals."""
    if value is None:
        return "-"
    return "Rs. {:,.2f}".format(value)


# ---------------------------------------------------------------------
# Validation helpers (server-side checks of form input)
# ---------------------------------------------------------------------
class FormError(Exception):
    """Raised when form input is invalid; the message is shown to the user."""


def clean_text(form, name, label, max_len):
    value = form.get(name, "").strip()
    if not value:
        raise FormError(f"{label} is required.")
    if len(value) > max_len:
        raise FormError(f"{label} must be at most {max_len} characters.")
    return value


def clean_int(form, name, label, minimum=1):
    raw = form.get(name, "").strip()
    if raw == "":
        raise FormError(f"{label} is required.")
    try:
        number = int(raw)
    except ValueError:
        raise FormError(f"{label} must be a whole number.")
    if number < minimum:
        raise FormError(f"{label} must be at least {minimum}.")
    if number > 9999999999999:
        raise FormError(f"{label} is too large.")
    return number


def clean_optional_int(form, name, label):
    """Return None when the field is blank, otherwise a validated integer."""
    if form.get(name, "").strip() == "":
        return None
    return clean_int(form, name, label)


def clean_decimal(form, name, label, positive=False, digits=12):
    """Validate a money-like value with at most 2 decimal places."""
    raw = form.get(name, "").strip()
    if raw == "":
        raise FormError(f"{label} is required.")
    try:
        number = Decimal(raw)
    except InvalidOperation:
        raise FormError(f"{label} must be a number.")
    if not number.is_finite():
        raise FormError(f"{label} must be a number.")
    if number.as_tuple().exponent < -2:
        raise FormError(f"{label} can have at most 2 decimal places.")
    if positive and number <= 0:
        raise FormError(f"{label} must be greater than zero.")
    if number < 0:
        raise FormError(f"{label} cannot be negative.")
    if number >= Decimal(10) ** (digits - 2):
        raise FormError(f"{label} is too large.")
    return number


def clean_date(form, name, label, allow_future=True):
    raw = form.get(name, "").strip()
    if raw == "":
        raise FormError(f"{label} is required.")
    try:
        value = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise FormError(f"{label} must be a valid date (YYYY-MM-DD).")
    if not allow_future and value > date.today():
        raise FormError(f"{label} cannot be in the future.")
    return value


def clean_choice(form, name, label, allowed):
    value = form.get(name, "").strip()
    if value not in allowed:
        raise FormError(f"{label} must be one of: {', '.join(allowed)}.")
    return value


def clean_phone(form, name="phone"):
    value = form.get(name, "").strip()
    if not re.fullmatch(r"\+?[0-9 \-]{7,15}", value):
        raise FormError("Phone must be 7 to 15 characters: digits, spaces, '-' or a leading '+'.")
    return value


def clean_id_list(form, name, label):
    """Read a multi-select field (e.g. several customers) as a list of ints."""
    values = form.getlist(name)
    if not values:
        raise FormError(f"Select at least one {label}.")
    try:
        return sorted({int(v) for v in values})
    except ValueError:
        raise FormError(f"Invalid {label} selection.")


def db_error_message(err):
    """Turn a MySQL error into a message a normal user can understand."""
    code = getattr(err, "errno", None)
    if code == 1062:
        return "That ID / number already exists. Please use a different one."
    if code == 1451:
        return ("This record cannot be deleted or changed because other records "
                "still refer to it (for example accounts, loans, employees, "
                "transactions or lockers).")
    if code == 1452:
        return "The selected bank, branch, customer, account or employee does not exist."
    if code == 3819:
        return "A value is outside the allowed range (for example a negative amount)."
    if code in (1264, 1406):
        return "A value is too large or too long for its database column."
    return f"Database error: {getattr(err, 'msg', err)}"


def build_order(sort, order, allowed, default):
    """Build a safe ORDER BY text using a whitelist of columns."""
    column = allowed.get(sort, allowed[default])
    direction = "DESC" if order == "desc" else "ASC"
    return f"{column} {direction}"


def arg_decimal(name, label):
    """Read an optional numeric filter from the URL (e.g. minimum balance)."""
    raw = request.args.get(name, "").strip()
    if raw == "":
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite():
            raise InvalidOperation
        return value
    except InvalidOperation:
        flash(f"{label} must be a number, so that filter was ignored.", "error")
        return None


def arg_date(name, label):
    raw = request.args.get(name, "").strip()
    if raw == "":
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        flash(f"{label} must be a valid date, so that filter was ignored.", "error")
        return None


def arg_int(name):
    raw = request.args.get(name, "").strip()
    return int(raw) if raw.isdigit() else None


def delete_record(sql, params, label, endpoint):
    """Run a DELETE; show a friendly message if other records still use it."""
    try:
        count = db.execute(sql, params)
        if count:
            flash(f"{label} deleted.", "success")
        else:
            flash(f"{label} was not found.", "error")
    except mysql.connector.Error as err:
        flash(db_error_message(err), "error")
    return redirect(url_for(endpoint))


# ---------------------------------------------------------------------
# Dropdown data (always read from MySQL)
# ---------------------------------------------------------------------
def get_banks():
    return db.fetch_all("SELECT bank_code, bank_name FROM banks ORDER BY bank_name")


def get_branches():
    return db.fetch_all("SELECT branch_code, branch_location FROM branches ORDER BY branch_code")


def get_customers():
    return db.fetch_all("SELECT customer_id, customer_name FROM customers ORDER BY customer_name")


def get_employees():
    return db.fetch_all(
        "SELECT e.employee_id, e.employee_name, e.designation, e.branch_code "
        "FROM employees e ORDER BY e.employee_name")


# ---------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------
@app.errorhandler(mysql.connector.Error)
def handle_database_error(err):
    """Shown when MySQL is down, the password is wrong or schema.sql was not run."""
    code = getattr(err, "errno", None)
    if code in (2002, 2003, 2013):
        message = ("Cannot connect to the MySQL server. Make sure MySQL is running "
                   "and that DB_HOST and DB_PORT in your .env file are correct.")
    elif code == 1045:
        message = "MySQL rejected the user name or password. Check DB_USER and DB_PASSWORD in your .env file."
    elif code == 1049:
        message = "The database does not exist yet. Run schema.sql in MySQL first (see README.md)."
    elif code == 1146:
        message = "A table is missing. Run schema.sql in MySQL first (see README.md)."
    else:
        message = db_error_message(err)
    return render_template("error.html", title="Database problem", message=message), 500


@app.errorhandler(404)
def handle_not_found(err):
    return render_template("error.html", title="Page not found",
                           message="That page does not exist."), 404


# ---------------------------------------------------------------------
# A. Home page / dashboard
# ---------------------------------------------------------------------
@app.route("/")
def index():
    # Aggregation: COUNT() and SUM() over several tables
    stats = db.fetch_one(
        "SELECT (SELECT COUNT(*) FROM customers) AS total_customers, "
        "       (SELECT COUNT(*) FROM branches)  AS total_branches, "
        "       (SELECT COUNT(*) FROM employees) AS total_employees, "
        "       (SELECT COUNT(*) FROM accounts)  AS total_accounts, "
        "       (SELECT COUNT(*) FROM loans)     AS total_loans, "
        "       (SELECT COALESCE(SUM(balance), 0) FROM accounts) AS total_balance")
    # Join + sorting: latest 5 transactions, newest first
    latest = db.fetch_all(
        "SELECT t.trans_no, t.account_no, a.account_type, t.trans_date, t.amount, t.trans_type "
        "FROM bank_transactions t "
        "JOIN accounts a ON a.account_no = t.account_no "
        "ORDER BY t.trans_date DESC, t.trans_no DESC LIMIT 5")
    return render_template("index.html", stats=stats, latest=latest)


# ---------------------------------------------------------------------
# B. Customers
# ---------------------------------------------------------------------
CUSTOMER_SORTS = {"customer_id": "customer_id",
                  "customer_name": "customer_name",
                  "date_of_birth": "date_of_birth"}


@app.route("/customers")
def customers():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "customer_name")
    order = request.args.get("order", "asc")
    # Projection: only the columns we need; filtering: search by ID or name
    sql = "SELECT customer_id, customer_name, address, date_of_birth, phone FROM customers"
    params = []
    if q:
        sql += " WHERE CAST(customer_id AS CHAR) LIKE %s OR customer_name LIKE %s"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY " + build_order(sort, order, CUSTOMER_SORTS, "customer_name")
    rows = db.fetch_all(sql, params)
    sort_options = [("customer_name", "Name"), ("customer_id", "Customer ID"),
                    ("date_of_birth", "Date of birth")]
    return render_template("customers.html", rows=rows, q=q, sort=sort, order=order,
                           sort_options=sort_options)


@app.route("/customers/<int:customer_id>")
def customer_view(customer_id):
    # Selection: one customer by exact ID
    customer = db.fetch_one(
        "SELECT customer_id, customer_name, address, date_of_birth, phone "
        "FROM customers WHERE customer_id = %s", (customer_id,))
    if customer is None:
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))
    # Join through the junction tables
    accounts_of = db.fetch_all(
        "SELECT a.account_no, a.account_type, a.balance, a.open_date "
        "FROM accounts a JOIN customer_accounts ca ON ca.account_no = a.account_no "
        "WHERE ca.customer_id = %s ORDER BY a.account_no", (customer_id,))
    loans_of = db.fetch_all(
        "SELECT l.loan_no, l.loan_type, l.amount, l.rate, l.loan_date "
        "FROM loans l JOIN customer_loans cl ON cl.loan_no = l.loan_no "
        "WHERE cl.customer_id = %s ORDER BY l.loan_no", (customer_id,))
    lockers_of = db.fetch_all(
        "SELECT locker_no, size, rent FROM lockers WHERE customer_id = %s ORDER BY locker_no",
        (customer_id,))
    return render_template("customer_detail.html", customer=customer, accounts_of=accounts_of,
                           loans_of=loans_of, lockers_of=lockers_of)


def read_customer_form(form):
    return {
        "customer_name": clean_text(form, "customer_name", "Customer name", 100),
        "address": clean_text(form, "address", "Address", 255),
        "date_of_birth": clean_date(form, "date_of_birth", "Date of birth", allow_future=False),
        "phone": clean_phone(form),
    }


@app.route("/customers/add", methods=["GET", "POST"])
def customer_add():
    if request.method == "POST":
        try:
            customer_id = clean_int(request.form, "customer_id", "Customer ID")
            data = read_customer_form(request.form)
            db.execute(
                "INSERT INTO customers (customer_id, customer_name, address, date_of_birth, phone) "
                "VALUES (%s, %s, %s, %s, %s)",
                (customer_id, data["customer_name"], data["address"],
                 data["date_of_birth"], data["phone"]))
            flash("Customer added successfully.", "success")
            return redirect(url_for("customers"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        return render_template("customer_form.html", mode="add", item=request.form.to_dict())
    return render_template("customer_form.html", mode="add", item={})


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
def customer_edit(customer_id):
    customer = db.fetch_one(
        "SELECT customer_id, customer_name, address, date_of_birth, phone "
        "FROM customers WHERE customer_id = %s", (customer_id,))
    if customer is None:
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))
    if request.method == "POST":
        try:
            data = read_customer_form(request.form)
            db.execute(
                "UPDATE customers SET customer_name = %s, address = %s, "
                "date_of_birth = %s, phone = %s WHERE customer_id = %s",
                (data["customer_name"], data["address"], data["date_of_birth"],
                 data["phone"], customer_id))
            flash("Customer updated successfully.", "success")
            return redirect(url_for("customers"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        item = request.form.to_dict()
        item["customer_id"] = customer_id
        return render_template("customer_form.html", mode="edit", item=item)
    return render_template("customer_form.html", mode="edit", item=customer)


@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
def customer_delete(customer_id):
    return delete_record("DELETE FROM customers WHERE customer_id = %s", (customer_id,),
                         "Customer", "customers")


# ---------------------------------------------------------------------
# C. Branches
# ---------------------------------------------------------------------
BRANCH_SORTS = {"branch_code": "b.branch_code", "branch_location": "b.branch_location"}


@app.route("/branches")
def branches():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "branch_code")
    order = request.args.get("order", "asc")
    # Join: branches with banks
    sql = ("SELECT b.branch_code, b.branch_location, k.bank_code, k.bank_name "
           "FROM branches b JOIN banks k ON k.bank_code = b.bank_code")
    params = []
    if q:
        sql += " WHERE CAST(b.branch_code AS CHAR) LIKE %s OR b.branch_location LIKE %s"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY " + build_order(sort, order, BRANCH_SORTS, "branch_code")
    rows = db.fetch_all(sql, params)
    sort_options = [("branch_code", "Branch code"), ("branch_location", "Location")]
    return render_template("branches.html", rows=rows, q=q, sort=sort, order=order,
                           sort_options=sort_options)


def read_branch_form(form):
    return {
        "branch_location": clean_text(form, "branch_location", "Branch location", 150),
        "bank_code": clean_int(form, "bank_code", "Bank"),
    }


@app.route("/branches/add", methods=["GET", "POST"])
def branch_add():
    if request.method == "POST":
        try:
            branch_code = clean_int(request.form, "branch_code", "Branch code")
            data = read_branch_form(request.form)
            db.execute(
                "INSERT INTO branches (branch_code, branch_location, bank_code) VALUES (%s, %s, %s)",
                (branch_code, data["branch_location"], data["bank_code"]))
            flash("Branch added successfully.", "success")
            return redirect(url_for("branches"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        return render_template("branch_form.html", mode="add", item=request.form.to_dict(),
                               banks=get_banks())
    return render_template("branch_form.html", mode="add", item={}, banks=get_banks())


@app.route("/branches/<int:branch_code>/edit", methods=["GET", "POST"])
def branch_edit(branch_code):
    branch = db.fetch_one(
        "SELECT branch_code, branch_location, bank_code FROM branches WHERE branch_code = %s",
        (branch_code,))
    if branch is None:
        flash("Branch not found.", "error")
        return redirect(url_for("branches"))
    if request.method == "POST":
        try:
            data = read_branch_form(request.form)
            db.execute("UPDATE branches SET branch_location = %s, bank_code = %s WHERE branch_code = %s",
                       (data["branch_location"], data["bank_code"], branch_code))
            flash("Branch updated successfully.", "success")
            return redirect(url_for("branches"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        item = request.form.to_dict()
        item["branch_code"] = branch_code
        return render_template("branch_form.html", mode="edit", item=item, banks=get_banks())
    return render_template("branch_form.html", mode="edit", item=branch, banks=get_banks())


@app.route("/branches/<int:branch_code>/delete", methods=["POST"])
def branch_delete(branch_code):
    return delete_record("DELETE FROM branches WHERE branch_code = %s", (branch_code,),
                         "Branch", "branches")


# ---------------------------------------------------------------------
# D. Employees
# ---------------------------------------------------------------------
EMPLOYEE_SORTS = {"employee_id": "e.employee_id", "employee_name": "e.employee_name",
                  "salary": "e.salary"}


@app.route("/employees")
def employees():
    q = request.args.get("q", "").strip()
    branch = arg_int("branch")
    designation = request.args.get("designation", "").strip()
    sort = request.args.get("sort", "employee_name")
    order = request.args.get("order", "asc")
    # Join: employees with branches
    sql = ("SELECT e.employee_id, e.employee_name, e.designation, e.salary, "
           "       b.branch_code, b.branch_location "
           "FROM employees e JOIN branches b ON b.branch_code = e.branch_code")
    conditions, params = [], []
    if q:
        conditions.append("(CAST(e.employee_id AS CHAR) LIKE %s OR e.employee_name LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if branch is not None:
        conditions.append("e.branch_code = %s")
        params.append(branch)
    if designation:
        conditions.append("e.designation = %s")
        params.append(designation)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY " + build_order(sort, order, EMPLOYEE_SORTS, "employee_name")
    rows = db.fetch_all(sql, params)
    designations = [r["designation"] for r in
                    db.fetch_all("SELECT DISTINCT designation FROM employees ORDER BY designation")]
    sort_options = [("employee_name", "Name"), ("employee_id", "Employee ID"), ("salary", "Salary")]
    return render_template("employees.html", rows=rows, q=q, branch=branch,
                           designation=designation, designations=designations,
                           branch_list=get_branches(), sort=sort, order=order,
                           sort_options=sort_options)


def read_employee_form(form):
    return {
        "employee_name": clean_text(form, "employee_name", "Employee name", 100),
        "designation": clean_text(form, "designation", "Designation", 50),
        "salary": clean_decimal(form, "salary", "Salary", digits=10),
        "branch_code": clean_int(form, "branch_code", "Branch"),
    }


@app.route("/employees/add", methods=["GET", "POST"])
def employee_add():
    if request.method == "POST":
        try:
            employee_id = clean_int(request.form, "employee_id", "Employee ID")
            data = read_employee_form(request.form)
            db.execute(
                "INSERT INTO employees (employee_id, employee_name, designation, salary, branch_code) "
                "VALUES (%s, %s, %s, %s, %s)",
                (employee_id, data["employee_name"], data["designation"], data["salary"],
                 data["branch_code"]))
            flash("Employee added successfully.", "success")
            return redirect(url_for("employees"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        return render_template("employee_form.html", mode="add", item=request.form.to_dict(),
                               branch_list=get_branches())
    return render_template("employee_form.html", mode="add", item={}, branch_list=get_branches())


@app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
def employee_edit(employee_id):
    employee = db.fetch_one(
        "SELECT employee_id, employee_name, designation, salary, branch_code "
        "FROM employees WHERE employee_id = %s", (employee_id,))
    if employee is None:
        flash("Employee not found.", "error")
        return redirect(url_for("employees"))
    if request.method == "POST":
        try:
            data = read_employee_form(request.form)
            db.execute(
                "UPDATE employees SET employee_name = %s, designation = %s, salary = %s, "
                "branch_code = %s WHERE employee_id = %s",
                (data["employee_name"], data["designation"], data["salary"],
                 data["branch_code"], employee_id))
            flash("Employee updated successfully.", "success")
            return redirect(url_for("employees"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        item = request.form.to_dict()
        item["employee_id"] = employee_id
        return render_template("employee_form.html", mode="edit", item=item,
                               branch_list=get_branches())
    return render_template("employee_form.html", mode="edit", item=employee,
                           branch_list=get_branches())


@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
def employee_delete(employee_id):
    return delete_record("DELETE FROM employees WHERE employee_id = %s", (employee_id,),
                         "Employee", "employees")


# ---------------------------------------------------------------------
# E. Accounts
# ---------------------------------------------------------------------
ACCOUNT_SORTS = {"account_no": "a.account_no", "balance": "a.balance", "open_date": "a.open_date"}


@app.route("/accounts")
def accounts():
    q = request.args.get("q", "").strip()
    account_type = request.args.get("account_type", "").strip()
    branch = arg_int("branch")
    min_balance = arg_decimal("min_balance", "Minimum balance")
    sort = request.args.get("sort", "account_no")
    order = request.args.get("order", "asc")
    # Joins: accounts + branches + customer_accounts + customers.
    # GROUP_CONCAT shows all owners of a joint account in ONE row.
    sql = ("SELECT a.account_no, a.account_type, a.balance, a.open_date, "
           "       b.branch_code, b.branch_location, "
           "       GROUP_CONCAT(c.customer_name ORDER BY c.customer_name SEPARATOR ', ') AS owners "
           "FROM accounts a "
           "JOIN branches b ON b.branch_code = a.branch_code "
           "LEFT JOIN customer_accounts ca ON ca.account_no = a.account_no "
           "LEFT JOIN customers c ON c.customer_id = ca.customer_id")
    conditions, params = [], []
    if q:
        conditions.append("CAST(a.account_no AS CHAR) LIKE %s")
        params.append(f"%{q}%")
    if account_type in ACCOUNT_TYPES:
        conditions.append("a.account_type = %s")
        params.append(account_type)
    if branch is not None:
        conditions.append("a.branch_code = %s")
        params.append(branch)
    if min_balance is not None:
        conditions.append("a.balance > %s")  # accounts above a specified balance
        params.append(min_balance)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += (" GROUP BY a.account_no, a.account_type, a.balance, a.open_date, "
            "b.branch_code, b.branch_location")
    sql += " ORDER BY " + build_order(sort, order, ACCOUNT_SORTS, "account_no")
    rows = db.fetch_all(sql, params)
    sort_options = [("account_no", "Account number"), ("balance", "Balance"),
                    ("open_date", "Opening date")]
    return render_template("accounts.html", rows=rows, q=q, account_type=account_type,
                           branch=branch, min_balance=request.args.get("min_balance", ""),
                           account_types=ACCOUNT_TYPES, branch_list=get_branches(),
                           sort=sort, order=order, sort_options=sort_options)


@app.route("/accounts/<int:account_no>")
def account_view(account_no):
    # Selection: the details of one specific account
    account = db.fetch_one(
        "SELECT a.account_no, a.account_type, a.balance, a.open_date, "
        "       b.branch_code, b.branch_location "
        "FROM accounts a JOIN branches b ON b.branch_code = a.branch_code "
        "WHERE a.account_no = %s", (account_no,))
    if account is None:
        flash("Account not found.", "error")
        return redirect(url_for("accounts"))
    owners = db.fetch_all(
        "SELECT c.customer_id, c.customer_name, c.phone "
        "FROM customers c JOIN customer_accounts ca ON ca.customer_id = c.customer_id "
        "WHERE ca.account_no = %s ORDER BY c.customer_name", (account_no,))
    history = db.fetch_all(
        "SELECT trans_no, trans_date, amount, trans_type FROM bank_transactions "
        "WHERE account_no = %s ORDER BY trans_date DESC, trans_no DESC LIMIT 20", (account_no,))
    return render_template("account_detail.html", account=account, owners=owners, history=history)


def read_account_form(form):
    return {
        "account_type": clean_choice(form, "account_type", "Account type", ACCOUNT_TYPES),
        "open_date": clean_date(form, "open_date", "Opening date", allow_future=False),
        "branch_code": clean_int(form, "branch_code", "Branch"),
        "customer_ids": clean_id_list(form, "customer_ids", "customer"),
    }


@app.route("/accounts/add", methods=["GET", "POST"])
def account_add():
    if request.method == "POST":
        try:
            account_no = clean_int(request.form, "account_no", "Account number")
            balance = clean_decimal(request.form, "balance", "Opening balance")
            data = read_account_form(request.form)

            def work(cursor):
                cursor.execute(
                    "INSERT INTO accounts (account_no, account_type, balance, open_date, branch_code) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (account_no, data["account_type"], balance, data["open_date"], data["branch_code"]))
                for customer_id in data["customer_ids"]:
                    cursor.execute(
                        "INSERT INTO customer_accounts (customer_id, account_no) VALUES (%s, %s)",
                        (customer_id, account_no))

            db.run_transaction(work)  # account + owner links saved together
            flash("Account added successfully.", "success")
            return redirect(url_for("accounts"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        return render_template("account_form.html", mode="add", item=request.form.to_dict(),
                               selected=request.form.getlist("customer_ids"),
                               account_types=ACCOUNT_TYPES, branch_list=get_branches(),
                               customer_list=get_customers())
    return render_template("account_form.html", mode="add", item={}, selected=[],
                           account_types=ACCOUNT_TYPES, branch_list=get_branches(),
                           customer_list=get_customers())


@app.route("/accounts/<int:account_no>/edit", methods=["GET", "POST"])
def account_edit(account_no):
    account = db.fetch_one(
        "SELECT account_no, account_type, balance, open_date, branch_code "
        "FROM accounts WHERE account_no = %s", (account_no,))
    if account is None:
        flash("Account not found.", "error")
        return redirect(url_for("accounts"))
    current_owners = [str(r["customer_id"]) for r in db.fetch_all(
        "SELECT customer_id FROM customer_accounts WHERE account_no = %s", (account_no,))]
    if request.method == "POST":
        try:
            data = read_account_form(request.form)

            def work(cursor):
                # The balance is NOT edited here; it only changes through transactions.
                cursor.execute(
                    "UPDATE accounts SET account_type = %s, open_date = %s, branch_code = %s "
                    "WHERE account_no = %s",
                    (data["account_type"], data["open_date"], data["branch_code"], account_no))
                cursor.execute("DELETE FROM customer_accounts WHERE account_no = %s", (account_no,))
                for customer_id in data["customer_ids"]:
                    cursor.execute(
                        "INSERT INTO customer_accounts (customer_id, account_no) VALUES (%s, %s)",
                        (customer_id, account_no))

            db.run_transaction(work)
            flash("Account updated successfully.", "success")
            return redirect(url_for("accounts"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        item = request.form.to_dict()
        item["account_no"] = account_no
        item["balance"] = account["balance"]
        return render_template("account_form.html", mode="edit", item=item,
                               selected=request.form.getlist("customer_ids"),
                               account_types=ACCOUNT_TYPES, branch_list=get_branches(),
                               customer_list=get_customers())
    return render_template("account_form.html", mode="edit", item=account, selected=current_owners,
                           account_types=ACCOUNT_TYPES, branch_list=get_branches(),
                           customer_list=get_customers())


@app.route("/accounts/<int:account_no>/delete", methods=["POST"])
def account_delete(account_no):
    # Blocked automatically (foreign key) if the account has transactions
    return delete_record("DELETE FROM accounts WHERE account_no = %s", (account_no,),
                         "Account", "accounts")


# ---------------------------------------------------------------------
# F. Loans
# ---------------------------------------------------------------------
LOAN_SORTS = {"loan_no": "l.loan_no", "amount": "l.amount", "loan_date": "l.loan_date"}


@app.route("/loans")
def loans():
    q = request.args.get("q", "").strip()
    loan_type = request.args.get("loan_type", "").strip()
    branch = arg_int("branch")
    min_amount = arg_decimal("min_amount", "Minimum amount")
    sort = request.args.get("sort", "loan_no")
    order = request.args.get("order", "asc")
    # Joins: loans + branches + customer_loans + customers (+ optional employee)
    sql = ("SELECT l.loan_no, l.loan_date, l.amount, l.rate, l.loan_type, "
           "       b.branch_code, b.branch_location, e.employee_name, "
           "       GROUP_CONCAT(c.customer_name ORDER BY c.customer_name SEPARATOR ', ') AS borrowers "
           "FROM loans l "
           "JOIN branches b ON b.branch_code = l.branch_code "
           "LEFT JOIN employees e ON e.employee_id = l.employee_id "
           "LEFT JOIN customer_loans cl ON cl.loan_no = l.loan_no "
           "LEFT JOIN customers c ON c.customer_id = cl.customer_id")
    conditions, params = [], []
    if q:
        conditions.append("CAST(l.loan_no AS CHAR) LIKE %s")
        params.append(f"%{q}%")
    if loan_type in LOAN_TYPES:
        conditions.append("l.loan_type = %s")
        params.append(loan_type)
    if branch is not None:
        conditions.append("l.branch_code = %s")
        params.append(branch)
    if min_amount is not None:
        conditions.append("l.amount > %s")  # loans above a specified amount
        params.append(min_amount)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += (" GROUP BY l.loan_no, l.loan_date, l.amount, l.rate, l.loan_type, "
            "b.branch_code, b.branch_location, e.employee_name")
    sql += " ORDER BY " + build_order(sort, order, LOAN_SORTS, "loan_no")
    rows = db.fetch_all(sql, params)
    sort_options = [("loan_no", "Loan number"), ("amount", "Amount"), ("loan_date", "Loan date")]
    return render_template("loans.html", rows=rows, q=q, loan_type=loan_type, branch=branch,
                           min_amount=request.args.get("min_amount", ""), loan_types=LOAN_TYPES,
                           branch_list=get_branches(), sort=sort, order=order,
                           sort_options=sort_options)


def read_loan_form(form):
    rate = clean_decimal(form, "rate", "Interest rate", digits=5)
    if rate > 100:
        raise FormError("Interest rate cannot be more than 100.")
    return {
        "loan_date": clean_date(form, "loan_date", "Loan date"),
        "amount": clean_decimal(form, "amount", "Loan amount", positive=True),
        "rate": rate,
        "loan_type": clean_choice(form, "loan_type", "Loan type", LOAN_TYPES),
        "branch_code": clean_int(form, "branch_code", "Branch"),
        "employee_id": clean_optional_int(form, "employee_id", "Employee"),
        "customer_ids": clean_id_list(form, "customer_ids", "borrower"),
    }


def loan_form_page(mode, item, selected):
    return render_template("loan_form.html", mode=mode, item=item, selected=selected,
                           loan_types=LOAN_TYPES, branch_list=get_branches(),
                           employee_list=get_employees(), customer_list=get_customers())


@app.route("/loans/add", methods=["GET", "POST"])
def loan_add():
    if request.method == "POST":
        try:
            loan_no = clean_int(request.form, "loan_no", "Loan number")
            data = read_loan_form(request.form)

            def work(cursor):
                cursor.execute(
                    "INSERT INTO loans (loan_no, loan_date, amount, rate, loan_type, branch_code, employee_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (loan_no, data["loan_date"], data["amount"], data["rate"], data["loan_type"],
                     data["branch_code"], data["employee_id"]))
                for customer_id in data["customer_ids"]:
                    cursor.execute(
                        "INSERT INTO customer_loans (customer_id, loan_no) VALUES (%s, %s)",
                        (customer_id, loan_no))

            db.run_transaction(work)
            flash("Loan added successfully.", "success")
            return redirect(url_for("loans"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        return loan_form_page("add", request.form.to_dict(), request.form.getlist("customer_ids"))
    return loan_form_page("add", {}, [])


@app.route("/loans/<int:loan_no>/edit", methods=["GET", "POST"])
def loan_edit(loan_no):
    loan = db.fetch_one(
        "SELECT loan_no, loan_date, amount, rate, loan_type, branch_code, employee_id "
        "FROM loans WHERE loan_no = %s", (loan_no,))
    if loan is None:
        flash("Loan not found.", "error")
        return redirect(url_for("loans"))
    current = [str(r["customer_id"]) for r in db.fetch_all(
        "SELECT customer_id FROM customer_loans WHERE loan_no = %s", (loan_no,))]
    if request.method == "POST":
        try:
            data = read_loan_form(request.form)

            def work(cursor):
                cursor.execute(
                    "UPDATE loans SET loan_date = %s, amount = %s, rate = %s, loan_type = %s, "
                    "branch_code = %s, employee_id = %s WHERE loan_no = %s",
                    (data["loan_date"], data["amount"], data["rate"], data["loan_type"],
                     data["branch_code"], data["employee_id"], loan_no))
                cursor.execute("DELETE FROM customer_loans WHERE loan_no = %s", (loan_no,))
                for customer_id in data["customer_ids"]:
                    cursor.execute(
                        "INSERT INTO customer_loans (customer_id, loan_no) VALUES (%s, %s)",
                        (customer_id, loan_no))

            db.run_transaction(work)
            flash("Loan updated successfully.", "success")
            return redirect(url_for("loans"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        item = request.form.to_dict()
        item["loan_no"] = loan_no
        return loan_form_page("edit", item, request.form.getlist("customer_ids"))
    return loan_form_page("edit", loan, current)


@app.route("/loans/<int:loan_no>/delete", methods=["POST"])
def loan_delete(loan_no):
    return delete_record("DELETE FROM loans WHERE loan_no = %s", (loan_no,), "Loan", "loans")


# ---------------------------------------------------------------------
# G. Transactions
# ---------------------------------------------------------------------
TRANSACTION_SORTS = {"trans_date": "t.trans_date", "amount": "t.amount", "trans_no": "t.trans_no"}


@app.route("/transactions")
def transactions():
    q = request.args.get("q", "").strip()
    trans_type = request.args.get("trans_type", "").strip()
    date_from = arg_date("date_from", "From date")
    date_to = arg_date("date_to", "To date")
    sort = request.args.get("sort", "trans_date")
    order = request.args.get("order", "desc")  # newest first by default
    # Join: transactions with accounts
    sql = ("SELECT t.trans_no, t.account_no, a.account_type, t.trans_date, t.amount, t.trans_type "
           "FROM bank_transactions t JOIN accounts a ON a.account_no = t.account_no")
    conditions, params = [], []
    if q:
        conditions.append("(CAST(t.trans_no AS CHAR) LIKE %s OR CAST(t.account_no AS CHAR) LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if trans_type in TRANSACTION_TYPES:
        conditions.append("t.trans_type = %s")
        params.append(trans_type)
    if date_from is not None:
        conditions.append("DATE(t.trans_date) >= %s")
        params.append(date_from)
    if date_to is not None:
        conditions.append("DATE(t.trans_date) <= %s")
        params.append(date_to)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY " + build_order(sort, order, TRANSACTION_SORTS, "trans_date") + ", t.trans_no DESC"
    rows = db.fetch_all(sql, params)
    account_list = db.fetch_all(
        "SELECT account_no, account_type, balance FROM accounts ORDER BY account_no")
    sort_options = [("trans_date", "Date"), ("amount", "Amount"), ("trans_no", "Transaction number")]
    return render_template("transactions.html", rows=rows, q=q, trans_type=trans_type,
                           date_from=request.args.get("date_from", ""),
                           date_to=request.args.get("date_to", ""),
                           transaction_types=TRANSACTION_TYPES, account_list=account_list,
                           prefill=arg_int("prefill"), sort=sort, order=order,
                           sort_options=sort_options)


def record_transaction(trans_type):
    """Deposit or withdraw. The balance update and the transaction record
    are saved in ONE MySQL transaction: both succeed or both are rolled back."""
    try:
        account_no = clean_int(request.form, "account_no", "Account")
        amount = clean_decimal(request.form, "amount", "Amount", positive=True)

        def work(cursor):
            # FOR UPDATE locks the account row so two users cannot change it at once
            cursor.execute("SELECT balance FROM accounts WHERE account_no = %s FOR UPDATE",
                           (account_no,))
            row = cursor.fetchone()
            if row is None:
                raise FormError("Account not found.")
            if trans_type == "Withdrawal":
                if row["balance"] < amount:
                    raise FormError(
                        f"Insufficient balance. Available balance is {money(row['balance'])}.")
                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_no = %s",
                               (amount, account_no))
            else:
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_no = %s",
                               (amount, account_no))
            cursor.execute(
                "INSERT INTO bank_transactions (account_no, trans_date, amount, trans_type) "
                "VALUES (%s, NOW(), %s, %s)", (account_no, amount, trans_type))

        db.run_transaction(work)
        flash(f"{trans_type} of {money(amount)} recorded for account {account_no}.", "success")
    except FormError as err:
        flash(str(err), "error")
    except mysql.connector.Error as err:
        flash(db_error_message(err), "error")
    return redirect(url_for("transactions"))


@app.route("/transactions/deposit", methods=["POST"])
def deposit():
    return record_transaction("Deposit")


@app.route("/transactions/withdraw", methods=["POST"])
def withdraw():
    return record_transaction("Withdrawal")


# ---------------------------------------------------------------------
# H. Lockers
# ---------------------------------------------------------------------
LOCKER_SORTS = {"locker_no": "l.locker_no", "rent": "l.rent", "size": "l.size"}


@app.route("/lockers")
def lockers():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "locker_no")
    order = request.args.get("order", "asc")
    # LEFT JOIN keeps unassigned lockers (customer_id is NULL)
    sql = ("SELECT l.locker_no, l.size, l.rent, c.customer_id, c.customer_name "
           "FROM lockers l LEFT JOIN customers c ON c.customer_id = l.customer_id")
    conditions, params = [], []
    if q:
        conditions.append("(CAST(l.locker_no AS CHAR) LIKE %s OR l.size LIKE %s OR c.customer_name LIKE %s)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if status == "assigned":
        conditions.append("l.customer_id IS NOT NULL")
    elif status == "available":
        conditions.append("l.customer_id IS NULL")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY " + build_order(sort, order, LOCKER_SORTS, "locker_no")
    rows = db.fetch_all(sql, params)
    sort_options = [("locker_no", "Locker number"), ("rent", "Rent"), ("size", "Size")]
    return render_template("lockers.html", rows=rows, q=q, status=status, sort=sort, order=order,
                           sort_options=sort_options)


def read_locker_form(form):
    return {
        "size": clean_choice(form, "size", "Size", LOCKER_SIZES),
        "rent": clean_decimal(form, "rent", "Rent", digits=8),
        "customer_id": clean_optional_int(form, "customer_id", "Customer"),
    }


def locker_form_page(mode, item):
    return render_template("locker_form.html", mode=mode, item=item, locker_sizes=LOCKER_SIZES,
                           customer_list=get_customers())


@app.route("/lockers/add", methods=["GET", "POST"])
def locker_add():
    if request.method == "POST":
        try:
            locker_no = clean_int(request.form, "locker_no", "Locker number")
            data = read_locker_form(request.form)
            db.execute("INSERT INTO lockers (locker_no, size, rent, customer_id) VALUES (%s, %s, %s, %s)",
                       (locker_no, data["size"], data["rent"], data["customer_id"]))
            flash("Locker added successfully.", "success")
            return redirect(url_for("lockers"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        return locker_form_page("add", request.form.to_dict())
    return locker_form_page("add", {})


@app.route("/lockers/<int:locker_no>/edit", methods=["GET", "POST"])
def locker_edit(locker_no):
    locker = db.fetch_one(
        "SELECT locker_no, size, rent, customer_id FROM lockers WHERE locker_no = %s", (locker_no,))
    if locker is None:
        flash("Locker not found.", "error")
        return redirect(url_for("lockers"))
    if request.method == "POST":
        try:
            data = read_locker_form(request.form)
            db.execute("UPDATE lockers SET size = %s, rent = %s, customer_id = %s WHERE locker_no = %s",
                       (data["size"], data["rent"], data["customer_id"], locker_no))
            flash("Locker updated successfully.", "success")
            return redirect(url_for("lockers"))
        except FormError as err:
            flash(str(err), "error")
        except mysql.connector.Error as err:
            flash(db_error_message(err), "error")
        item = request.form.to_dict()
        item["locker_no"] = locker_no
        return locker_form_page("edit", item)
    return locker_form_page("edit", locker)


@app.route("/lockers/<int:locker_no>/delete", methods=["POST"])
def locker_delete(locker_no):
    return delete_record("DELETE FROM lockers WHERE locker_no = %s", (locker_no,),
                         "Locker", "lockers")


# ---------------------------------------------------------------------
# I. Reports (SQL aggregation: COUNT, SUM, GROUP BY)
# ---------------------------------------------------------------------
@app.route("/reports")
def reports():
    customer_count = db.fetch_one("SELECT COUNT(*) AS total FROM customers")["total"]
    accounts_by_type = db.fetch_all(
        "SELECT account_type, COUNT(*) AS total_accounts FROM accounts "
        "GROUP BY account_type ORDER BY account_type")
    by_branch = db.fetch_all(
        "SELECT b.branch_code, b.branch_location, COUNT(a.account_no) AS total_accounts, "
        "       COALESCE(SUM(a.balance), 0) AS total_balance "
        "FROM branches b LEFT JOIN accounts a ON a.branch_code = b.branch_code "
        "GROUP BY b.branch_code, b.branch_location ORDER BY b.branch_code")
    loans_by_type = db.fetch_all(
        "SELECT loan_type, COUNT(*) AS total_loans, SUM(amount) AS total_amount "
        "FROM loans GROUP BY loan_type ORDER BY total_amount DESC")
    money_totals = db.fetch_one(
        "SELECT COALESCE(SUM(CASE WHEN trans_type = 'Deposit' THEN amount END), 0) AS total_deposits, "
        "       COALESCE(SUM(CASE WHEN trans_type = 'Withdrawal' THEN amount END), 0) AS total_withdrawals "
        "FROM bank_transactions")
    trans_by_type = db.fetch_all(
        "SELECT trans_type, COUNT(*) AS total_transactions FROM bank_transactions "
        "GROUP BY trans_type ORDER BY trans_type")
    return render_template("reports.html", customer_count=customer_count,
                           accounts_by_type=accounts_by_type, by_branch=by_branch,
                           loans_by_type=loans_by_type, money_totals=money_totals,
                           trans_by_type=trans_by_type)


if __name__ == "__main__":
    # Port 5001 because macOS uses port 5000 for AirPlay Receiver
    app.run(host="127.0.0.1", port=5001, debug=True)
