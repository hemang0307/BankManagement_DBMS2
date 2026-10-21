# Design and Development of a Database-Driven Web Application

## Project Title: Bank Management System

**Student name:** ____________________  **Register number:** ____________________
**Course:** CAM 5  **Date:** ____________________

---

## 1. Problem Statement

Banks store large amounts of related data: customers, branches, employees, accounts, loans,
transactions and lockers. Keeping this data in paper files or separate spreadsheets causes
duplicate records, slow searching and mistakes in account balances. This project builds a small
web application with a relational database so that bank staff can store, search, update and report
on this data in one place. It is a simulated academic project that uses fictional data only.

## 2. Objectives

1. Convert the DA1 ER design (eight entities) into a working MySQL database.
2. Enforce relationships using primary keys, foreign keys and junction tables.
3. Build a simple Flask web application that performs add, view, edit, search, filter and sort operations.
4. Demonstrate SQL selection, projection, filtering, sorting, aggregation and joins in real pages.
5. Record deposits and withdrawals safely using a MySQL database transaction.
6. Use parameterized queries to prevent SQL injection.

## 3. Technologies Used

| Part | Technology |
|------|-----------|
| Front end | HTML5, CSS3 |
| Templates | Jinja2 (Flask) |
| Back end | Python 3, Flask |
| Database | MySQL 8 |
| Connector | mysql-connector-python (plain SQL, no ORM) |
| Configuration | `.env` file read with python-dotenv |

## 4. Entities and Main Attributes

| Entity | Main attributes (ER name -> SQL column) |
|--------|----------------------------------------|
| Bank | Code -> `bank_code` (PK), BName -> `bank_name` |
| Branch | BCode -> `branch_code` (PK), BLocation -> `branch_location` |
| Employee | Eid -> `employee_id` (PK), Ename, Designation, Salary |
| Customer | Cid -> `customer_id` (PK), CName, Address, DoB -> `date_of_birth`, Phone |
| Account | Acc_No -> `account_no` (PK), Type -> `account_type`, Balance, Open_Date |
| Loan | Loan_No -> `loan_no` (PK), Loan_Date, Amount, Rate, Loan_Type |
| Transaction | Trans_No -> `trans_no` (PK), Trans_Date, Amount, Trans_Type (table `bank_transactions`) |
| Locker | Locker_No -> `locker_no` (PK), Size, Rent |

## 5. Database Schema: Primary Keys and Foreign Keys

| Table | Primary key | Foreign keys |
|-------|-------------|--------------|
| `banks` | `bank_code` | none |
| `branches` | `branch_code` | `bank_code` -> `banks` |
| `employees` | `employee_id` | `branch_code` -> `branches` |
| `customers` | `customer_id` | none |
| `accounts` | `account_no` | `branch_code` -> `branches` |
| `loans` | `loan_no` | `branch_code` -> `branches`; `employee_id` -> `employees` (optional) |
| `customer_accounts` | (`customer_id`, `account_no`) | both columns |
| `customer_loans` | (`customer_id`, `loan_no`) | both columns |
| `lockers` | `locker_no` | `customer_id` -> `customers` (NULL allowed) |
| `bank_transactions` | `trans_no` (auto increment) | `account_no` -> `accounts` |

Example (from `schema.sql`):

```sql
CREATE TABLE accounts (
    account_no   BIGINT        NOT NULL,
    account_type ENUM('Savings','Current','Fixed Deposit') NOT NULL,
    balance      DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    open_date    DATE          NOT NULL,
    branch_code  INT           NOT NULL,
    PRIMARY KEY (account_no),
    CONSTRAINT chk_account_balance CHECK (balance >= 0),
    CONSTRAINT fk_account_branch FOREIGN KEY (branch_code)
        REFERENCES branches (branch_code) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
```

Money uses `DECIMAL`, dates use `DATE` / `DATETIME`, and indexes were added on customer name,
employee name, designation, account type, loan type, transaction date and transaction type.

## 6. Relationships

**One-to-many**

1. One bank has many branches (`branches.bank_code`).
2. One branch employs many employees (`employees.branch_code`).
3. One branch maintains many accounts (`accounts.branch_code`).
4. One branch issues many loans (`loans.branch_code`).
5. One account has many transactions (`bank_transactions.account_no`).
6. One customer may hold lockers; `lockers.customer_id` is nullable so a locker can be unassigned.
   *Assumption:* the ER model gives no maximum, so a customer may hold more than one locker.
7. Optional: `loans.employee_id` records the employee handling a loan. *Assumption:* the ER
   diagram does not give details of this association.

**Many-to-many (junction tables)**

1. Customer - Account: `customer_accounts`. One customer can own many accounts and one account can
   have many customers (joint account) without duplicating the account row.
2. Customer - Loan: `customer_loans`. A loan can have co-borrowers and a customer can have many loans.

## 7. Sample Records and Explanation

`schema.sql` inserts: 1 bank, 4 branches, 6 employees, 9 customers, 11 accounts (3 joint),
5 loans (3 with co-borrowers), 5 lockers (2 unassigned), 8 customer-loan links, 14 customer-account
links and 12 transactions. All names and phone numbers are fictional.

```sql
INSERT INTO customers (customer_id, customer_name, address, date_of_birth, phone) VALUES
(1001, 'Aarav Sharma', '12, Gandhi Street, T. Nagar, Chennai 600017', '1990-04-12', '9000010001');
```

The seeded balances are *current* balances. The seeded transactions are recent activity that is
**already included** in those balances. Transactions made later through the website change the balance.

## 8. SQL Queries Used (selection, projection, filtering, sorting, aggregation, joins)

**Selection and projection** (only the needed columns; exact customer ID):

```sql
SELECT customer_id, customer_name, address, date_of_birth, phone
FROM customers WHERE customer_id = %s;
```

**Filtering** (accounts above a balance, by type; loans above an amount; transactions by type/date):

```sql
SELECT account_no, account_type, balance FROM accounts
WHERE balance > %s AND account_type = %s;

SELECT trans_no, trans_date, amount FROM bank_transactions
WHERE trans_type = %s AND DATE(trans_date) >= %s;
```

**Sorting** (column names come from a fixed whitelist in `app.py`, never straight from the user):

```sql
SELECT customer_name FROM customers ORDER BY customer_name ASC;
SELECT trans_no, trans_date FROM bank_transactions ORDER BY trans_date DESC;
```

**Aggregation** (`COUNT`, `SUM`, `GROUP BY`):

```sql
SELECT account_type, COUNT(*) FROM accounts GROUP BY account_type;
SELECT b.branch_code, COUNT(a.account_no), COALESCE(SUM(a.balance), 0)
FROM branches b LEFT JOIN accounts a ON a.branch_code = b.branch_code
GROUP BY b.branch_code, b.branch_location;
SELECT loan_type, SUM(amount) FROM loans GROUP BY loan_type;
```

**Joins**

```sql
-- branches with banks
SELECT b.branch_code, b.branch_location, k.bank_name
FROM branches b JOIN banks k ON k.bank_code = b.bank_code;

-- accounts with all their customers (joint accounts shown in one row)
SELECT a.account_no, GROUP_CONCAT(c.customer_name SEPARATOR ', ') AS owners
FROM accounts a
LEFT JOIN customer_accounts ca ON ca.account_no = a.account_no
LEFT JOIN customers c ON c.customer_id = ca.customer_id
GROUP BY a.account_no;
```

Employees are joined with branches, loans with customers through `customer_loans`, and transactions
with accounts in the same way. All queries use `%s` placeholders (parameterized queries).

**Transaction handling** (deposit/withdrawal): the balance update and the new transaction row are
executed inside one MySQL transaction. If any step fails (for example insufficient balance), the code
calls `rollback()` and neither change is saved.

```python
cursor.execute("SELECT balance FROM accounts WHERE account_no = %s FOR UPDATE", (account_no,))
# check balance, then:
cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_no = %s", (amount, account_no))
cursor.execute("INSERT INTO bank_transactions (account_no, trans_date, amount, trans_type) "
               "VALUES (%s, NOW(), %s, %s)", (account_no, amount, "Withdrawal"))
```

## 9. Website Pages and Functions

| Page | Functions |
|------|-----------|
| Home | Dashboard counts, total balance and latest transactions (all from MySQL) |
| Customers | List, search by ID/name, sort, add, edit, delete, view details |
| Branches | List with bank name, search, add, edit, delete |
| Employees | List, search, filter by branch/designation, add, edit, delete |
| Accounts | List with all owners, filter by type/branch/balance, sort, add, edit, delete, details |
| Loans | List with borrowers, filter by type/branch/amount, sort, add, edit, delete |
| Transactions | History, search, filter by type/date, record deposit and withdrawal |
| Lockers | List, search, assigned/available status, add, edit, delete |
| Reports | Counts and totals using `COUNT`, `SUM`, `GROUP BY` |

Server-side validation rejects empty fields, wrong numbers and dates, and zero or negative amounts.
Duplicate IDs, invalid references and deletes of records that are still used produce a clear message.

## 10. How Flask Connects to MySQL

`db.py` reads the settings (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) from the `.env`
file using python-dotenv and opens a connection with `mysql.connector.connect(...)`. The helper
functions `fetch_all`, `fetch_one`, `execute` and `run_transaction` run SQL through a cursor and
always close the cursor and connection. Each Flask route in `app.py` calls these helpers, then passes
the rows to a Jinja2 template that displays them in an HTML table. Forms send data with POST; after
a successful change the browser is redirected to the list page to avoid duplicate submission.

## 11. Testing Procedure

Run the tests after following `README.md`. Fill in the last column yourself after you have actually
run each test.

| No. | Test | Sample input | Expected result | Actual result (fill in) |
|-----|------|--------------|-----------------|--------------------------|
| 1 | Dashboard | Open Home | Counts: 9 customers, 4 branches, 6 employees, 11 accounts, 5 loans | |
| 2 | Customer search | `Priya` | Priya Venkatesh only | |
| 3 | Add customer | ID 1010 and valid data | Success message; row in list | |
| 4 | Duplicate ID | ID 1001 | "ID already exists" | |
| 5 | Delete used customer | Delete 1001 | Blocked with message | |
| 6 | Joint account | View account 5000000001 | Two customers shown | |
| 7 | Filter accounts | Type Savings, balance above 50000 | Only matching accounts | |
| 8 | Deposit | 1000 to account 5000000008 | Balance 8900.00 becomes 9900.00; new transaction | |
| 9 | Over-withdrawal | 999999 from account 5000000008 | Error; balance unchanged; no new transaction | |
| 10 | Bad amount | Deposit 0 and -5 | Rejected | |
| 11 | Filter transactions | Type Withdrawal | Only withdrawals | |
| 12 | Locker status | Filter "available" | Lockers 4 and 5 | |
| 13 | Reports | Open Reports | Tables match the data | |

## 12. Conclusion

The project turns the DA1 ER design into a working MySQL database and a simple Flask website. It
demonstrates keys, relationships (including two many-to-many junction tables), parameterized SQL,
joins, aggregation and a safe database transaction for deposits and withdrawals. It is a learning
project, so it has no login system or real banking features. Possible future work: user login,
account statements and a loan repayment schedule.

## 13. Screenshots

Take **real** screenshots after running the website on your computer. Do not use edited images.
Save them in a folder (for example `screenshots/`) and insert them below.

| Figure | What to capture |
|--------|-----------------|
| Figure 1 - Home page | The dashboard with counts, total balance and latest transactions |
| Figure 2 - Customer search | Customers page after searching for a name or ID, showing the search box and result |
| Figure 3 - Account list | Accounts page showing owners (a joint account) and the filter bar |
| Figure 4 - Transaction operation | The Transactions page after a successful deposit or withdrawal (message visible); an extra screenshot of a rejected over-withdrawal is a good addition |
| Figure 5 - Reports page | The full Reports page with all aggregation tables |

```
![Figure 1 - Home page](screenshots/home.png)
![Figure 2 - Customer search](screenshots/customer_search.png)
![Figure 3 - Account list](screenshots/accounts.png)
![Figure 4 - Transaction operation](screenshots/transaction.png)
![Figure 5 - Reports page](screenshots/reports.png)
```

*(Replace this block with the real image lines, without the surrounding code fence.)*

**[Insert Figure 1 here]**  **[Insert Figure 2 here]**  **[Insert Figure 3 here]**
**[Insert Figure 4 here]**  **[Insert Figure 5 here]**

## 14. Exporting this Report to PDF

The assignment requires a PDF. Choose one method:

1. **VS Code:** install the extension "Markdown PDF" (yzane), open `CAM5_Report.md`, press
   Cmd+Shift+P (Ctrl+Shift+P on Windows), and run "Markdown PDF: Export (pdf)". Images must be inserted
   with correct relative paths first.
2. **Browser print:** open the file in a Markdown preview (VS Code: Cmd+Shift+V), then print and choose
   "Save as PDF".
3. **Pandoc** (if installed, with a PDF engine such as LaTeX or wkhtmltopdf):
   ```bash
   pandoc CAM5_Report.md -o CAM5_Report.pdf
   ```
4. **Word or Google Docs:** copy the content in, add the screenshots and use File > Save as / Download > PDF.

Open the PDF afterwards and check that tables, code and all five screenshots appear correctly.
