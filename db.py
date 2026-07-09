import sqlite3

import os

DB_NAME = "bank.db"

TOLL_RATES = {

    "MOTORCYCLE": 100.00,

    "BIKE": 100.00,

    "CAR_JEEP": 750.00,

    "CAR": 750.00,

    "SEDAN": 750.00,

    "SUV": 750.00,

    "PICKUP": 1200.00,

    "MICROBUS": 1300.00,

    "MINIBUS": 1400.00,

    "MEDIUM_BUS": 2000.00,

    "LARGE_BUS": 2400.00,

    "BUS": 2400.00,

    "SMALL_TRUCK": 1600.00,

    "MEDIUM_TRUCK_5_8T": 2100.00,

    "MEDIUM_TRUCK_8_11T": 2800.00,

    "LARGE_TRUCK": 5500.00,

    "TRUCK": 5500.00,

    "TRAILER_4_AXLE": 6000.00,

    "TRAILER_5_AXLE": 7500.00

}

def get_db_path():

    current_dir = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(current_dir, DB_NAME)

def get_connection():

    db_path = get_db_path()

    conn = sqlite3.connect(db_path)

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON;")

    return conn

def init_db():

    db_path = get_db_path()

    if os.path.exists(db_path):

        conn = sqlite3.connect(db_path)

        cursor = conn.cursor()

        try:

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts';")

            if cursor.fetchone():

                conn.close()

                os.remove(db_path)

                print("Old schema 'accounts' detected and deleted.")

            else:

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vehicles';")

                if cursor.fetchone():

                    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE vehicle_type = 'SEDAN';")

                    if cursor.fetchone()[0] > 0:

                        conn.close()

                        os.remove(db_path)

                        print("Legacy vehicle types ('SEDAN') detected. Database wiped for fresh seeding.")

                    else:

                        conn.close()

                else:

                    conn.close()

        except Exception as e:

            print(f"Migration check warning: {e}")

            try:

                conn.close()

            except:

                pass

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT UNIQUE NOT NULL,
            owner_name TEXT NOT NULL,
            balance REAL DEFAULT 0.0 CHECK(balance >= 0.0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_reg TEXT UNIQUE NOT NULL,
            rfid_tag TEXT UNIQUE,
            vehicle_type TEXT NOT NULL,
            bank_account_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            car_reg TEXT,
            type TEXT NOT NULL, -- 'DEPOSIT', 'TOLL_PAYMENT'
            amount REAL NOT NULL,
            toll_booth TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
        );
    """)

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM bank_accounts;")

    if cursor.fetchone()[0] == 0:

        print("Seeding database with default bank account and demo vehicles...")

        cursor.execute(

            "INSERT INTO bank_accounts (account_number, owner_name, balance) VALUES ('ACC-1001', 'IoT Lab Demo Account', 10000.0);"

        )

        acc_id = cursor.lastrowid

        cursor.execute(

            "INSERT INTO transactions (account_id, car_reg, type, amount, toll_booth) VALUES (?, NULL, 'DEPOSIT', 10000.0, 'INITIAL SEPOSIT SEED');",

            (acc_id,)

        )

        demo_vehicles = [

            ("DHAKA-METRO-T-55-6666", "RFID-TRUCK-888", "LARGE_TRUCK", acc_id),

            ("DHAKA-METRO-HA-11-2222", "RFID-BUS-777", "LARGE_BUS", acc_id),

            ("DHAKA-METRO-G-33-4444", "RFID-CAR-111", "CAR_JEEP", acc_id),

            ("DHAKA-L-12-3456", "RFID-BIKE-999", "MOTORCYCLE", acc_id),

        ]

        for plate, tag, v_type, link_id in demo_vehicles:

            cursor.execute(

                "INSERT INTO vehicles (car_reg, rfid_tag, vehicle_type, bank_account_id) VALUES (?, ?, ?, ?);",

                (plate, tag, v_type, link_id)

            )

        conn.commit()

        print("Database seeding completed.")

    conn.close()

def create_bank_account(owner_name, initial_balance=0.0):

    owner_name = owner_name.strip()

    if initial_balance < 0.0:

        raise ValueError("Initial balance cannot be negative.")

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute("SELECT MAX(id) FROM bank_accounts;")

        max_id = cursor.fetchone()[0] or 1000

        account_number = f"ACC-{max_id + 1}"

        cursor.execute(

            "INSERT INTO bank_accounts (account_number, owner_name, balance) VALUES (?, ?, ?);",

            (account_number, owner_name, initial_balance)

        )

        account_id = cursor.lastrowid

        if initial_balance > 0.0:

            cursor.execute(

                "INSERT INTO transactions (account_id, car_reg, type, amount, toll_booth) VALUES (?, NULL, 'DEPOSIT', ?, 'INITIAL DEPOSIT');",

                (account_id, initial_balance)

            )

        conn.commit()

        return {

            "id": account_id,

            "account_number": account_number,

            "owner_name": owner_name,

            "balance": initial_balance

        }

    except Exception as e:

        conn.rollback()

        raise e

    finally:

        conn.close()

def register_vehicle(car_reg, vehicle_type, rfid_tag=None, bank_account_id=None):

    car_reg = car_reg.strip().upper()

    vehicle_type = vehicle_type.strip().upper()

    if rfid_tag:

        rfid_clean = rfid_tag.strip().upper()

        rfid_tag = None if rfid_clean in ("", "NONE") else rfid_clean

    else:

        rfid_tag = None

    if vehicle_type not in TOLL_RATES:

        raise ValueError(f"Invalid vehicle type '{vehicle_type}'. Must be one of: {list(TOLL_RATES.keys())}")

    if not bank_account_id:

        raise ValueError("A bank account must be linked to register a vehicle.")

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute("SELECT id FROM bank_accounts WHERE id = ?;", (bank_account_id,))

        acc = cursor.fetchone()

        if not acc:

            raise ValueError("Linked bank account does not exist.")

        cursor.execute(

            "INSERT INTO vehicles (car_reg, rfid_tag, vehicle_type, bank_account_id) VALUES (?, ?, ?, ?);",

            (car_reg, rfid_tag, vehicle_type, bank_account_id)

        )

        conn.commit()

        return cursor.lastrowid

    except sqlite3.IntegrityError as e:

        conn.rollback()

        raise ValueError(f"Vehicle plate '{car_reg}' or RFID '{rfid_tag}' is already registered.") from e

    finally:

        conn.close()

def get_accounts():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bank_accounts ORDER BY id DESC;")

    rows = cursor.fetchall()

    accounts = [dict(row) for row in rows]

    conn.close()

    return accounts

def get_vehicles():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.*, a.account_number, a.owner_name, a.balance
        FROM vehicles v
        JOIN bank_accounts a ON v.bank_account_id = a.id
        ORDER BY v.id DESC;
    """)

    rows = cursor.fetchall()

    vehicles = [dict(row) for row in rows]

    conn.close()

    return vehicles

def get_account_by_number(acc_num):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bank_accounts WHERE UPPER(account_number) = ?;", (acc_num.strip().upper(),))

    row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None

def get_vehicle_by_identifier(identifier):

    val = identifier.strip().upper()

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.*, a.account_number, a.balance, a.owner_name
        FROM vehicles v
        JOIN bank_accounts a ON v.bank_account_id = a.id
        WHERE UPPER(v.car_reg) = ? OR UPPER(v.rfid_tag) = ?;
    """, (val, val))

    row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None

import re

def clean_plate_string(text):

    if not text:

        return ""

    return re.sub(r'[^A-Z0-9]', '', text.strip().upper())

def get_vehicle_by_normalized_plate(ocr_text):

    clean_ocr = clean_plate_string(ocr_text)

    if not clean_ocr:

        return None

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT v.*, a.account_number, a.balance, a.owner_name
            FROM vehicles v
            JOIN bank_accounts a ON v.bank_account_id = a.id;
        """)

        rows = cursor.fetchall()

        for row in rows:

            veh = dict(row)

            clean_db_plate = clean_plate_string(veh['car_reg'])

            clean_db_rfid = clean_plate_string(veh['rfid_tag']) if veh['rfid_tag'] else ""

            if clean_ocr == clean_db_plate or (clean_db_rfid and clean_ocr == clean_db_rfid):

                return veh

        return None

    finally:

        conn.close()

def deposit_money(identifier, amount):

    if amount <= 0.0:

        raise ValueError("Deposit amount must be greater than zero.")

    conn = get_connection()

    cursor = conn.cursor()

    try:

        account = get_account_by_number(identifier)

        if not account:

            vehicle = get_vehicle_by_identifier(identifier)

            if vehicle:

                account = get_account_by_number(vehicle['account_number'])

        if not account:

            raise ValueError(f"No account or vehicle found matching identifier '{identifier}'.")

        cursor.execute(

            "UPDATE bank_accounts SET balance = balance + ? WHERE id = ?;",

            (amount, account['id'])

        )

        cursor.execute(

            "INSERT INTO transactions (account_id, car_reg, type, amount, toll_booth) VALUES (?, NULL, 'DEPOSIT', ?, 'BANK_DEPOSIT');",

            (account['id'], amount)

        )

        conn.commit()

        cursor.execute("SELECT balance, account_number FROM bank_accounts WHERE id = ?;", (account['id'],))

        row = cursor.fetchone()

        return {

            "account_number": row['account_number'],

            "new_balance": row['balance']

        }

    except Exception as e:

        conn.rollback()

        raise e

    finally:

        conn.close()

def charge_toll(identifier, amount=None, toll_booth="MAIN_PLAZA"):

    conn = get_connection()

    conn.isolation_level = 'EXCLUSIVE'

    cursor = conn.cursor()

    try:

        val = identifier.strip().upper()

        cursor.execute("""
            SELECT v.id as vehicle_id, v.car_reg, v.vehicle_type, a.id as account_id, a.account_number, a.balance
            FROM vehicles v
            JOIN bank_accounts a ON v.bank_account_id = a.id
            WHERE UPPER(v.car_reg) = ? OR UPPER(v.rfid_tag) = ?;
        """, (val, val))

        vehicle = cursor.fetchone()

        if not vehicle:

            raise ValueError(f"Vehicle registration or RFID '{identifier}' is not registered.")

        v_type = vehicle['vehicle_type']

        car_reg = vehicle['car_reg']

        account_id = vehicle['account_id']

        balance = vehicle['balance']

        acc_num = vehicle['account_number']

        toll_fee = amount

        if toll_fee is None:

            toll_fee = TOLL_RATES.get(v_type, 15.00)

        if toll_fee <= 0.0:

            raise ValueError("Toll fee must be greater than zero.")

        if balance < toll_fee:

            raise ValueError(f"Insufficient funds for car {car_reg}. Balance: {balance:.2f}, Required: {toll_fee:.2f}")

        cursor.execute(

            "UPDATE bank_accounts SET balance = balance - ? WHERE id = ?;",

            (toll_fee, account_id)

        )

        cursor.execute(

            "INSERT INTO transactions (account_id, car_reg, type, amount, toll_booth) VALUES (?, ?, 'TOLL_PAYMENT', ?, ?);",

            (account_id, car_reg, toll_fee, toll_booth)

        )

        conn.commit()

        cursor.execute("SELECT balance FROM bank_accounts WHERE id = ?;", (account_id,))

        new_balance = cursor.fetchone()[0]

        return {

            "car_reg": car_reg,

            "vehicle_type": v_type,

            "account_number": acc_num,

            "previous_balance": balance,

            "new_balance": new_balance,

            "deducted_amount": toll_fee

        }

    except Exception as e:

        conn.rollback()

        raise e

    finally:

        conn.close()

def get_transactions(car_reg=None):

    conn = get_connection()

    cursor = conn.cursor()

    if car_reg:

        val = car_reg.strip().upper()

        cursor.execute("""
            SELECT t.*, a.account_number, a.owner_name
            FROM transactions t
            JOIN bank_accounts a ON t.account_id = a.id
            WHERE UPPER(t.car_reg) = ?
            ORDER BY t.timestamp DESC;
        """, (val,))

    else:

        cursor.execute("""
            SELECT t.*, a.account_number, a.owner_name
            FROM transactions t
            JOIN bank_accounts a ON t.account_id = a.id
            ORDER BY t.timestamp DESC;
        """)

    rows = cursor.fetchall()

    transactions = [dict(row) for row in rows]

    conn.close()

    return transactions
