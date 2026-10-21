-- =====================================================================
-- Bank Management System - CAM 5 assignment
-- Database creation script + fictional sample data
-- Requires MySQL 8.0.16 or newer (CHECK constraints are enforced).
-- WARNING: this script drops and re-creates the tables, so running it
-- again resets the demo data to its original state.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS bank_management_db;
USE bank_management_db;

-- Drop tables in reverse dependency order so the script can be re-run
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS bank_transactions;
DROP TABLE IF EXISTS lockers;
DROP TABLE IF EXISTS customer_loans;
DROP TABLE IF EXISTS customer_accounts;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS branches;
DROP TABLE IF EXISTS banks;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Bank            (ER: Code -> bank_code, BName -> bank_name)
-- ---------------------------------------------------------------------
CREATE TABLE banks (
    bank_code INT          NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (bank_code)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Branch          (ER: BCode -> branch_code, BLocation -> branch_location)
-- Relationship: one bank has many branches
-- ---------------------------------------------------------------------
CREATE TABLE branches (
    branch_code     INT          NOT NULL,
    branch_location VARCHAR(150) NOT NULL,
    bank_code       INT          NOT NULL,
    PRIMARY KEY (branch_code),
    CONSTRAINT fk_branch_bank FOREIGN KEY (bank_code)
        REFERENCES banks (bank_code) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Employee        (ER: Eid -> employee_id, Ename -> employee_name,
--                  Designation -> designation, Salary -> salary)
-- Relationship: one branch employs many employees
-- ---------------------------------------------------------------------
CREATE TABLE employees (
    employee_id   INT           NOT NULL,
    employee_name VARCHAR(100)  NOT NULL,
    designation   VARCHAR(50)   NOT NULL,
    salary        DECIMAL(10,2) NOT NULL,
    branch_code   INT           NOT NULL,
    PRIMARY KEY (employee_id),
    CONSTRAINT chk_employee_salary CHECK (salary >= 0),
    CONSTRAINT fk_employee_branch FOREIGN KEY (branch_code)
        REFERENCES branches (branch_code) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Customer        (ER: Cid -> customer_id, CName -> customer_name,
--                  Address -> address, DoB -> date_of_birth, Phone -> phone)
-- ---------------------------------------------------------------------
CREATE TABLE customers (
    customer_id   INT          NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    address       VARCHAR(255) NOT NULL,
    date_of_birth DATE         NOT NULL,
    phone         VARCHAR(15)  NOT NULL,
    PRIMARY KEY (customer_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Account         (ER: Acc_No -> account_no, Type -> account_type,
--                  Balance -> balance, Open_Date -> open_date)
-- Relationship: one branch maintains many accounts
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- Loan            (ER: Loan_No -> loan_no, Loan_Date -> loan_date,
--                  Amount -> amount, Rate -> rate, Loan_Type -> loan_type)
-- Relationship: one branch issues many loans.
-- Assumption: employee_id is an OPTIONAL reference to the employee
-- who handles the loan (the ER model does not fully specify this).
-- ---------------------------------------------------------------------
CREATE TABLE loans (
    loan_no     INT           NOT NULL,
    loan_date   DATE          NOT NULL,
    amount      DECIMAL(12,2) NOT NULL,
    rate        DECIMAL(5,2)  NOT NULL,
    loan_type   VARCHAR(30)   NOT NULL,
    branch_code INT           NOT NULL,
    employee_id INT           NULL,
    PRIMARY KEY (loan_no),
    CONSTRAINT chk_loan_amount CHECK (amount > 0),
    CONSTRAINT chk_loan_rate CHECK (rate >= 0 AND rate <= 100),
    CONSTRAINT fk_loan_branch FOREIGN KEY (branch_code)
        REFERENCES branches (branch_code) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_loan_employee FOREIGN KEY (employee_id)
        REFERENCES employees (employee_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Junction table: Customer <-> Account (many-to-many, joint accounts)
-- A customer cannot be deleted while linked to an account (RESTRICT).
-- If an account is deleted, only its link rows are removed (CASCADE).
-- ---------------------------------------------------------------------
CREATE TABLE customer_accounts (
    customer_id INT    NOT NULL,
    account_no  BIGINT NOT NULL,
    PRIMARY KEY (customer_id, account_no),
    CONSTRAINT fk_ca_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ca_account FOREIGN KEY (account_no)
        REFERENCES accounts (account_no) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Junction table: Customer <-> Loan (many-to-many, co-borrowers)
-- ---------------------------------------------------------------------
CREATE TABLE customer_loans (
    customer_id INT NOT NULL,
    loan_no     INT NOT NULL,
    PRIMARY KEY (customer_id, loan_no),
    CONSTRAINT fk_cl_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cl_loan FOREIGN KEY (loan_no)
        REFERENCES loans (loan_no) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Locker          (ER: Locker_No -> locker_no, Size -> size, Rent -> rent)
-- customer_id is NULL when the locker is unassigned.
-- Assumption: no UNIQUE on customer_id, so one customer may hold
-- more than one locker (the ER model does not fix the maximum).
-- ---------------------------------------------------------------------
CREATE TABLE lockers (
    locker_no   INT           NOT NULL,
    size        ENUM('Small','Medium','Large') NOT NULL,
    rent        DECIMAL(8,2)  NOT NULL,
    customer_id INT           NULL,
    PRIMARY KEY (locker_no),
    CONSTRAINT chk_locker_rent CHECK (rent >= 0),
    CONSTRAINT fk_locker_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Transaction     (ER: Trans_No -> trans_no, Trans_Date -> trans_date,
--                  Amount -> amount, Trans_Type -> trans_type)
-- Named bank_transactions to avoid clashing with the SQL word TRANSACTION.
-- Relationship: one account has many transactions
-- ---------------------------------------------------------------------
CREATE TABLE bank_transactions (
    trans_no   INT           NOT NULL AUTO_INCREMENT,
    account_no BIGINT        NOT NULL,
    trans_date DATETIME      NOT NULL,
    amount     DECIMAL(12,2) NOT NULL,
    trans_type ENUM('Deposit','Withdrawal') NOT NULL,
    PRIMARY KEY (trans_no),
    CONSTRAINT chk_trans_amount CHECK (amount > 0),
    CONSTRAINT fk_trans_account FOREIGN KEY (account_no)
        REFERENCES accounts (account_no) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Indexes for searching and filtering
-- (primary keys and foreign keys are already indexed automatically)
-- ---------------------------------------------------------------------
CREATE INDEX idx_customer_name     ON customers (customer_name);
CREATE INDEX idx_employee_name     ON employees (employee_name);
CREATE INDEX idx_employee_desig    ON employees (designation);
CREATE INDEX idx_account_type      ON accounts (account_type);
CREATE INDEX idx_loan_type         ON loans (loan_type);
CREATE INDEX idx_trans_date        ON bank_transactions (trans_date);
CREATE INDEX idx_trans_type        ON bank_transactions (trans_type);

-- =====================================================================
-- SAMPLE DATA (all fictional)
-- =====================================================================

INSERT INTO banks (bank_code, bank_name) VALUES
(1, 'Demo National Bank');

INSERT INTO branches (branch_code, branch_location, bank_code) VALUES
(101, 'T. Nagar, Chennai, Tamil Nadu', 1),
(102, 'Anna Nagar, Chennai, Tamil Nadu', 1),
(103, 'Adyar, Chennai, Tamil Nadu', 1),
(104, 'Koramangala, Bengaluru, Karnataka', 1);

INSERT INTO employees (employee_id, employee_name, designation, salary, branch_code) VALUES
(1, 'Ramesh Iyer',         'Branch Manager', 95000.00, 101),
(2, 'Lakshmi Narayanan',   'Loan Officer',   62000.00, 101),
(3, 'Karthik Subramanian', 'Cashier',        38000.00, 102),
(4, 'Meena Krishnan',      'Branch Manager', 92000.00, 103),
(5, 'Arjun Nair',          'Clerk',          32000.00, 102),
(6, 'Divya Menon',         'Loan Officer',   60000.00, 104);

INSERT INTO customers (customer_id, customer_name, address, date_of_birth, phone) VALUES
(1001, 'Aarav Sharma',    '12, Gandhi Street, T. Nagar, Chennai 600017',        '1990-04-12', '9000010001'),
(1002, 'Priya Venkatesh', '45, Lake View Road, Adyar, Chennai 600020',          '1985-09-23', '9000010002'),
(1003, 'Suresh Kumar',    '7, 2nd Main Road, Anna Nagar, Chennai 600040',       '1978-01-05', '9000010003'),
(1004, 'Anitha Rajan',    '22, Temple Street, Mylapore, Chennai 600004',        '1992-11-30', '9000010004'),
(1005, 'Vikram Reddy',    '101, MG Road, Koramangala, Bengaluru 560034',        '1988-06-18', '9000010005'),
(1006, 'Kavya Pillai',    '9, Beach Road, Besant Nagar, Chennai 600090',        '1995-02-14', '9000010006'),
(1007, 'Mohan Das',       '33, Nehru Nagar, Velachery, Chennai 600042',         '1970-07-27', '9000010007'),
(1008, 'Sneha Iyer',      '18, Park Avenue, Anna Nagar, Chennai 600040',        '1998-12-09', '9000010008'),
(1009, 'Rahul Menon',     '56, Residency Road, Bengaluru 560025',               '1983-03-21', '9000010009');

-- These balances are the CURRENT balances. The seeded transactions below
-- are recent history that is ALREADY included in these balances.
INSERT INTO accounts (account_no, account_type, balance, open_date, branch_code) VALUES
(5000000001, 'Savings',       45250.00, '2019-03-15', 101),
(5000000002, 'Savings',      128900.50, '2018-07-01', 103),
(5000000003, 'Current',      350000.00, '2020-01-20', 102),
(5000000004, 'Savings',       15750.00, '2021-05-10', 102),
(5000000005, 'Fixed Deposit', 500000.00, '2022-02-28', 101),
(5000000006, 'Savings',       62300.75, '2017-11-11', 104),
(5000000007, 'Current',      210500.00, '2019-09-09', 104),
(5000000008, 'Savings',        8900.00, '2023-01-05', 103),
(5000000009, 'Savings',       33450.25, '2020-08-17', 101),
(5000000010, 'Fixed Deposit', 250000.00, '2021-12-01', 103),
(5000000011, 'Savings',        5000.00, '2024-06-10', 102);

-- Joint accounts: 5000000001, 5000000003 and 5000000006 have two owners
INSERT INTO customer_accounts (customer_id, account_no) VALUES
(1001, 5000000001), (1004, 5000000001),
(1001, 5000000005),
(1002, 5000000002),
(1003, 5000000003), (1007, 5000000003),
(1004, 5000000004),
(1005, 5000000006), (1009, 5000000006),
(1005, 5000000007),
(1006, 5000000008),
(1003, 5000000009),
(1007, 5000000010),
(1008, 5000000011);

INSERT INTO loans (loan_no, loan_date, amount, rate, loan_type, branch_code, employee_id) VALUES
(9001, '2022-04-10', 1500000.00,  8.50, 'Home',      101, 2),
(9002, '2023-06-15',  300000.00, 11.25, 'Personal',  102, NULL),
(9003, '2021-08-01',  800000.00,  9.75, 'Education', 103, 4),
(9004, '2024-01-20',  450000.00, 10.50, 'Vehicle',   104, 6),
(9005, '2023-11-05', 1200000.00, 12.00, 'Business',  101, 2);

-- Co-borrowers: loans 9001, 9004 and 9005 have two borrowers
INSERT INTO customer_loans (customer_id, loan_no) VALUES
(1001, 9001), (1004, 9001),
(1003, 9002),
(1002, 9003),
(1005, 9004), (1009, 9004),
(1003, 9005), (1007, 9005);

-- Lockers 4 and 5 are unassigned (customer_id is NULL)
INSERT INTO lockers (locker_no, size, rent, customer_id) VALUES
(1, 'Small',  1500.00, 1001),
(2, 'Medium', 2500.00, 1002),
(3, 'Large',  4000.00, 1005),
(4, 'Small',  1500.00, NULL),
(5, 'Medium', 2500.00, NULL);

INSERT INTO bank_transactions (trans_no, account_no, trans_date, amount, trans_type) VALUES
(1,  5000000001, '2026-10-01 09:30:00', 10000.00, 'Deposit'),
(2,  5000000001, '2026-10-05 11:15:00',  2500.00, 'Withdrawal'),
(3,  5000000002, '2026-10-02 10:00:00', 25000.00, 'Deposit'),
(4,  5000000003, '2026-10-03 14:45:00', 75000.00, 'Deposit'),
(5,  5000000003, '2026-10-08 16:20:00', 20000.00, 'Withdrawal'),
(6,  5000000004, '2026-10-09 12:10:00',  3000.00, 'Deposit'),
(7,  5000000006, '2026-10-10 10:40:00', 12000.00, 'Deposit'),
(8,  5000000007, '2026-10-12 15:05:00', 40000.00, 'Withdrawal'),
(9,  5000000008, '2026-10-14 09:55:00',  1500.00, 'Withdrawal'),
(10, 5000000009, '2026-10-15 13:30:00',  6000.00, 'Deposit'),
(11, 5000000011, '2026-10-17 11:00:00',  5000.00, 'Deposit'),
(12, 5000000002, '2026-10-19 17:25:00',  8000.00, 'Withdrawal');
