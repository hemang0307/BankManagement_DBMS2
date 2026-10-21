# Bank Management System (CAM 5 Assignment)

A simple database-driven web application built with **Python Flask**, **MySQL**,
**HTML5/CSS3** and **Jinja2** templates. It is a simulated academic project:
all names, phone numbers and balances are fictional.

## 1. Project files

```
bank_management_system/
├── app.py            Flask routes, validation and SQL queries
├── db.py             MySQL connection helper functions
├── schema.sql        Creates bank_management_db, tables, indexes and sample data
├── requirements.txt  Python packages
├── .env.example      Template for your database settings
├── README.md         This file
├── CAM5_Report.md    Report for the assignment (export to PDF)
├── templates/        HTML (Jinja2) pages; base.html holds the shared header and menu
└── static/style.css  The small stylesheet
```

Extra templates beyond the suggested list: `macros.html` (shared sort box and delete button),
`customer_detail.html` and `account_detail.html` (view one customer / one account).

## 2. Setup on macOS (step by step)

Run every command in the **Terminal** app unless it says otherwise.

### Step 1 - Install Python 3 and MySQL (skip what you already have)

Check first:

```bash
python3 --version
mysql --version
```

If a command is not found, install it. With Homebrew (install it from https://brew.sh if needed):

```bash
brew install python
brew install mysql
brew services start mysql
```

Alternatively download the **MySQL Community Server** and **MySQL Workbench** installers from
https://dev.mysql.com/downloads/ . You need **MySQL 8.0.16 or newer**. During the installer you
choose a password for the `root` user. Remember it.

### Step 2 - Open the project folder in Terminal

```bash
cd ~/Downloads/bank_management_system
```

(Change the path to wherever you unzipped the project.)

### Step 3 - Create a virtual environment (in the project folder)

```bash
python3 -m venv venv
```

### Step 4 - Activate it

```bash
source venv/bin/activate
```

Your prompt now starts with `(venv)`.

### Step 5 - Install the dependencies

```bash
pip install -r requirements.txt
```

### Step 6 - Create your `.env` file

```bash
cp .env.example .env
```

### Step 7 - Enter your MySQL password

Open `.env` in any text editor (for example `open -e .env`) and set your own password:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_own_mysql_password
DB_NAME=bank_management_db
FLASK_SECRET_KEY=change-this-local-demo-key
```

Never share or submit your real `.env` file. If you installed MySQL with Homebrew and never set
a password, `DB_PASSWORD` may be empty.

### Step 8 - Create the database and sample data

**Option A: MySQL command line** (run in Terminal, inside the project folder):

```bash
mysql -u root -p < schema.sql
```

Type your MySQL password when asked.

**Option B: MySQL Workbench**

1. Open MySQL Workbench and connect to your local server.
2. Choose **File > Open SQL Script...** and select `schema.sql`.
3. Click the lightning-bolt button (Execute).
4. Refresh the Schemas panel; you should see `bank_management_db` with 10 tables.

Running `schema.sql` again deletes and recreates the tables, which resets the demo data.

### Step 9 - Start the Flask application (Terminal, venv active)

```bash
python app.py
```

### Step 10 - Open the website

Open **http://127.0.0.1:5001** in your browser. (Port 5001 is used because macOS reserves
port 5000 for AirPlay Receiver.)

### Step 11 - Test the main features

| Page | What to try | Expected result |
|------|-------------|-----------------|
| Home | Open the page | Counts, total balance and latest 5 transactions come from MySQL |
| Customers | Search `Priya`; search `1003`; sort by date of birth; click View | Matching rows only; the View page shows accounts, loans, lockers |
| Customers | Add customer ID `1010` with valid data | Success message; customer appears in the list |
| Customers | Add customer ID `1001` again | Error: ID already exists |
| Customers | Delete customer `1001` | Error: other records still refer to it |
| Branches | Search `Adyar`; add branch `105`; edit its location | Bank name shown for each branch |
| Employees | Filter by branch and designation; add and edit an employee | Table updates |
| Accounts | Filter type `Savings`; balance above `50000`; sort by balance | Filtered and sorted rows |
| Accounts | Open account `5000000001` | Shows two customers (joint account) and its transactions |
| Accounts | Add an account with two customers selected (Ctrl/Cmd-click) | One account row, both names listed |
| Loans | Filter type `Home`; amount above `500000` | Filtered rows with all borrowers |
| Transactions | Deposit 1000 into `5000000008` | Balance rises by 1000; new row at the top of history |
| Transactions | Withdraw 999999999 from `5000000008` | Error: insufficient balance; nothing changes |
| Transactions | Deposit `0` or `-5` | Error: amount must be greater than zero |
| Transactions | Filter by type or date range | Only matching rows |
| Lockers | Filter `available`; edit a locker and choose "Unassigned" | Status changes to Available |
| Reports | Open the page | Aggregate tables (counts and sums) |

### Step 12 - Stop the server

Click in the Terminal window and press **Ctrl + C**. Then leave the virtual environment:

```bash
deactivate
```

## 3. Note for Windows users

Use **Command Prompt** or **PowerShell** in the project folder:

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

(In PowerShell, if activation is blocked, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first.)
Edit `.env` in Notepad, run `schema.sql` in MySQL Workbench (or
`mysql -u root -p < schema.sql` from a prompt where `mysql` is on the PATH), then run
`python app.py` and open http://127.0.0.1:5001 .

## 4. Troubleshooting

| Message / problem | Fix |
|-------------------|-----|
| "Cannot connect to the MySQL server" | Start MySQL (`brew services start mysql`, or start the service from System Settings / Services). Check `DB_HOST` and `DB_PORT`. |
| "MySQL rejected the user name or password" | Correct `DB_USER` / `DB_PASSWORD` in `.env`, then restart `python app.py`. |
| "The database does not exist yet" or "A table is missing" | Run `schema.sql` (Step 8). |
| `ModuleNotFoundError` | Activate the venv (Step 4) and run `pip install -r requirements.txt`. |
| Page does not load | Make sure you opened port **5001**, not 5000. |

## 5. Implementation assumptions

1. **Column names.** SQL names are more readable than the ER names:

| Entity | ER attribute | SQL column |
|--------|--------------|-----------|
| Bank (`banks`) | Code, BName | `bank_code`, `bank_name` |
| Branch (`branches`) | BCode, BLocation | `branch_code`, `branch_location` (+ FK `bank_code`) |
| Employee (`employees`) | Eid, Ename, Designation, Salary | `employee_id`, `employee_name`, `designation`, `salary` (+ FK `branch_code`) |
| Customer (`customers`) | Cid, CName, Address, DoB, Phone | `customer_id`, `customer_name`, `address`, `date_of_birth`, `phone` |
| Account (`accounts`) | Acc_No, Type, Balance, Open_Date | `account_no`, `account_type`, `balance`, `open_date` (+ FK `branch_code`) |
| Loan (`loans`) | Loan_No, Loan_Date, Amount, Rate, Loan_Type | `loan_no`, `loan_date`, `amount`, `rate`, `loan_type` (+ FK `branch_code`, optional `employee_id`) |
| Transaction (`bank_transactions`) | Trans_No, Trans_Date, Amount, Trans_Type | `trans_no`, `trans_date`, `amount`, `trans_type` (+ FK `account_no`) |
| Locker (`lockers`) | Locker_No, Size, Rent | `locker_no`, `size`, `rent` (+ nullable FK `customer_id`) |

2. **Customer-locker.** `lockers.customer_id` may be NULL (unassigned). The ER model does not
   state a maximum, so no UNIQUE rule is added: one customer may hold several lockers.
3. **Employee-loan.** The ER diagram suggests an association but gives no details. It is
   implemented as an optional `loans.employee_id` (the employee handling the loan).
4. **Seeded transactions.** The balances in `accounts` are the *current* balances. The 12 seeded
   transactions are recent history that is **already included** in those balances. New deposits and
   withdrawals made through the website change the balance and add a new transaction row.
5. **Account balance edits.** The balance is entered only when an account is created. Afterwards it
   changes only through deposits and withdrawals, so balance and history stay consistent.
6. **Deleting.** Foreign keys use `RESTRICT` where records must be protected (for example a
   customer who still owns an account, or an account that has transactions). The application shows a
   message instead of crashing. Deleting an account or loan that has no transactions also removes
   its owner/borrower link rows in the junction tables.
7. **Phone numbers** are stored as text (VARCHAR) so leading zeros and `+` are kept.

## 6. What has and has not been tested

The files were created in a sandbox that has **no MySQL server and no internet access**, so the
following was verified there:

- Every Python file compiles.
- Every page template renders (all list, form, detail, report and error pages), the search/filter/sort
  URLs are accepted, form validation rejects bad input, and the "database is down" error page works.
  This was done with a **fake database layer**, not with real MySQL.

**Not yet run (you must run these on your computer):** `schema.sql` against real MySQL, the real SQL
queries, the deposit/withdrawal rollback behaviour, and foreign-key error messages. Follow the table
in Step 11 and note any problem.

## 7. Checklist for your computer

- [ ] Install Python 3 and MySQL 8; create the virtual environment and install `requirements.txt`.
- [ ] Copy `.env.example` to `.env` and enter your own MySQL password.
- [ ] Run `schema.sql` (command line or Workbench).
- [ ] Run `python app.py`; open http://127.0.0.1:5001 .
- [ ] Work through the test table in Step 11 and fix anything that fails.
- [ ] Take real screenshots: Home, Customers search result, Accounts list, a deposit/withdrawal
      (before and after), Reports page. Save them as PNG files.
- [ ] Paste the screenshots into `CAM5_Report.md` (see the screenshot section), fill in your name and
      details, and update the "Testing results" table with what actually happened.
- [ ] Export the report to PDF (see the end of `CAM5_Report.md`) and check the PDF opens correctly.
- [ ] Submit the PDF, and the project folder (without `venv` and without your `.env`) if required.
