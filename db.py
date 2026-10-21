"""Database helper functions.

All SQL in this project goes through these helpers, which use
mysql-connector-python and always close their cursors/connections.
"""
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()  # read the .env file


def get_connection():
    """Open a new MySQL connection using settings from the .env file."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "bank_management_db"),
    )


def fetch_all(sql, params=None):
    """Run a SELECT and return all rows as a list of dictionaries."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        conn.close()


def fetch_one(sql, params=None):
    """Run a SELECT and return the first row (or None if nothing found)."""
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run one INSERT/UPDATE/DELETE and commit it."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()
    finally:
        conn.close()


def run_transaction(work):
    """Run several statements as ONE MySQL transaction.

    `work` is a function that receives a cursor. If it finishes normally
    everything is committed; if any exception happens, everything is
    rolled back so the database is never left half-updated.
    """
    conn = get_connection()
    try:
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        try:
            result = work(cursor)
        finally:
            cursor.close()
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
