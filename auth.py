"""
auth.py
-------
Authentication module for the Streamlit Personnel Welfare Monitoring System.
Connects to: personnel_welfare.db (same SQLite file used by your other modules)
"""

import sqlite3
import secrets
import re
import bcrypt
import streamlit as st

DB_PATH = "personnel_welfare.db"

# --- DB Auto-Initialization --------------------------------------------------
def ensure_auth_db_initialized():
    """Ensure all auth tables and default admin exist in the shared database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Users table (Personnel)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            personnel_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Administrators table (Welfare Officers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS administrators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'welfare_officer',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT NOT NULL,
            token TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_time DATETIME
        )
    """)

    # 4. Audit logs table (compatible with both app.py and auth.py)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            officer_action TEXT,
            target_personnel_id TEXT
        )
    """)

    # Seed a default administrator if none exist
    # Force reset/guarantee known credentials for COMMAND-99
    hashed_admin_pwd = bcrypt.hashpw("AdminPass@123".encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    cursor.execute("""
        INSERT INTO administrators (officer_id, name, email, password_hash, role)
        VALUES ('COMMAND-99', 'HQ Welfare Officer', 'welfare.hq@defence.mil', ?, 'welfare_officer')
        ON CONFLICT(officer_id) DO UPDATE SET password_hash = excluded.password_hash
    """, (hashed_admin_pwd,))

    conn.commit()
    conn.close()

# Run immediately when auth.py is imported
ensure_auth_db_initialized()


# --- DB connection -----------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# --- password helpers ---------------------------------------------------------
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _is_strong_password(password: str):
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain a number."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must contain a special character."
    return True, ""


# --- CRUD: users ---------------------------------------------------------------
def get_user_by_personnel_id(personnel_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE personnel_id = ?", (personnel_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(full_name, personnel_id, email, department, password_hash):
    conn = get_connection()
    conn.execute(
        """INSERT INTO users (full_name, personnel_id, email, department, password_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (full_name, personnel_id, email, department, password_hash),
    )
    
    # Sync with personnel_records using matching columns
    try:
        conn.execute(
            """INSERT OR IGNORE INTO personnel_records 
               (personnel_id, continuous_duty_days, leave_due_days, overtime_hours_30d, posting_type)
               VALUES (?, 0, 0, 0.0, ?)""",
            (personnel_id, department),
        )
    except sqlite3.OperationalError:
        # Fallback in case table uses alternate naming scheme
        try:
            conn.execute(
                """INSERT OR IGNORE INTO personnel_records 
                   (personnel_id, continuous_duty_days, leave_days_due, overtime_hours_last_30d, posting_type)
                   VALUES (?, 0, 0, 0.0, ?)""",
                (personnel_id, department),
            )
        except Exception:
            pass

    conn.commit()
    conn.close()


# --- CRUD: administrators --------------------------------------------------------
def get_admin_by_officer_id(officer_id: str):
    conn = get_connection()
    row = None
    try:
        # Check standard officer_id column
        row = conn.execute("SELECT * FROM administrators WHERE officer_id = ?", (officer_id,)).fetchone()
    except sqlite3.OperationalError:
        try:
            # Fallback for alternative column naming (username or admin_id)
            row = conn.execute("SELECT * FROM administrators WHERE username = ?", (officer_id,)).fetchone()
        except sqlite3.OperationalError:
            try:
                row = conn.execute("SELECT * FROM administrators WHERE admin_id = ?", (officer_id,)).fetchone()
            except sqlite3.OperationalError:
                pass
    conn.close()
    return dict(row) if row else None


def create_admin(officer_id, name, email, password_hash, role="welfare_officer"):
    conn = get_connection()
    conn.execute(
        """INSERT INTO administrators (officer_id, name, email, password_hash, role)
           VALUES (?, ?, ?, ?, ?)""",
        (officer_id, name, email, password_hash, role),
    )
    conn.commit()
    conn.close()


# --- CRUD: sessions / audit_logs -----------------------------------------------
def record_login_session(principal_id, role):
    token = secrets.token_hex(32)
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (user_id, role, token) VALUES (?, ?, ?)",
        (principal_id, role, token),
    )
    conn.commit()
    conn.close()
    return token


def close_login_session(principal_id, role):
    conn = get_connection()
    row = conn.execute(
        """SELECT id FROM sessions WHERE user_id = ? AND role = ? AND is_active = 1
           ORDER BY login_time DESC LIMIT 1""",
        (principal_id, role),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE sessions SET logout_time = CURRENT_TIMESTAMP, is_active = 0 WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
    conn.close()


def insert_audit_log(officer_id, action):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_logs (officer_action, target_personnel_id) VALUES (?, ?)", 
        (action, officer_id)
    )
    conn.commit()
    conn.close()


# --- business logic: register / login / logout ----------------------------------
def register_user(full_name, personnel_id, email, department, password, confirm_password):
    if not all([full_name, personnel_id, email, department, password, confirm_password]):
        return False, "All fields are required."
    if password != confirm_password:
        return False, "Passwords do not match."
    strong, msg = _is_strong_password(password)
    if not strong:
        return False, msg
    if get_user_by_personnel_id(personnel_id):
        return False, "That Personnel ID is already registered."
    if get_user_by_email(email):
        return False, "That email address is already registered."
    create_user(full_name, personnel_id, email, department, _hash_password(password))
    return True, "Account created successfully. Please log in."


def login_user(personnel_id, password):
    user = get_user_by_personnel_id(personnel_id)
    if not user or not _verify_password(password, user["password_hash"]):
        return False, "Invalid Personnel ID or password."
    token = record_login_session(user["id"], "user")
    st.session_state.auth = {
        "role": "user",
        "id": user["id"],
        "identifier": user["personnel_id"],
        "full_name": user["full_name"],
        "department": user["department"],
        "token": token,
    }
    return True, "Login successful."


def login_admin(officer_id, password):
    admin = get_admin_by_officer_id(officer_id)
    if not admin:
        return False, "Invalid Officer ID or password."
    
    # Retrieve password hash safely regardless of column naming
    pwd_hash = admin.get("password_hash") or admin.get("password")
    if not pwd_hash or not _verify_password(password, pwd_hash):
        return False, "Invalid Officer ID or password."

    admin_pk = admin.get("id") or 1
    token = record_login_session(admin_pk, "administrator")
    st.session_state.auth = {
        "role": "administrator",
        "id": admin_pk,
        "identifier": officer_id,
        "name": admin.get("name") or admin.get("full_name") or "HQ Welfare Officer",
        "token": token,
    }
    insert_audit_log(officer_id, "Logged in")
    return True, "Login successful."

def logout():
    auth_state = st.session_state.get("auth")
    if not auth_state:
        return
    close_login_session(auth_state["id"], auth_state["role"])
    if auth_state["role"] == "administrator":
        insert_audit_log(auth_state["identifier"], "Logged out")
    del st.session_state["auth"]
    st.session_state.auth_view = "role_selection"


# --- session-state helpers -----------------------------------------------------
def is_authenticated():
    return "auth" in st.session_state


def current_role():
    return st.session_state.get("auth", {}).get("role")


def require_role(role_name):
    """Call as the FIRST line inside view runners.
    Halts the script if the session isn't authenticated with the right role."""
    if not is_authenticated():
        st.warning("Please log in to continue.")
        st.stop()
    if current_role() != role_name:
        st.error("You are not authorized to view this page.")
        st.stop()


# --- UI screens (Role Selection / Login / Signup) -------------------------------
def _apply_theme():
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(135deg, #1e2530, #11141a); }
        div.stButton > button { border-radius: 8px; font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_role_selection():
    _apply_theme()
    st.markdown("<h1 style='text-align:center;'>Personnel Welfare Monitoring System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Select operational role to continue</p>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 👤 Personnel")
        st.caption("Confidential Wellness Self Check-In")
        if st.button("Continue as Personnel", use_container_width=True):
            st.session_state.auth_view = "user_login"
            st.rerun()
    with col2:
        st.markdown("### 🛡️ Administrator")
        st.caption("Welfare Officer Supervisory Dashboard")
        if st.button("Continue as Administrator", use_container_width=True):
            st.session_state.auth_view = "admin_login"
            st.rerun()


def render_user_login():
    _apply_theme()
    st.markdown("### 👤 Personnel Login")
    with st.form("user_login_form"):
        personnel_id = st.text_input("Personnel ID (e.g., CRP-1001)")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)
    if submitted:
        success, message = login_user(personnel_id.strip(), password)
        (st.success if success else st.error)(message)
        if success:
            st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("⬅ Back"):
        st.session_state.auth_view = "role_selection"
        st.rerun()
    if c2.button("Create an account"):
        st.session_state.auth_view = "user_signup"
        st.rerun()


def render_user_signup():
    _apply_theme()
    st.markdown("### 👤 Create Personnel Account")
    with st.form("user_signup_form"):
        full_name = st.text_input("Full Name")
        personnel_id = st.text_input("Personnel ID (e.g., CRP-1018)")
        email = st.text_input("Email")
        department = st.text_input("Unit / Department")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register", use_container_width=True)
    if submitted:
        success, message = register_user(
            full_name.strip(), personnel_id.strip(), email.strip().lower(),
            department.strip(), password, confirm_password,
        )
        (st.success if success else st.error)(message)
        if success:
            st.session_state.auth_view = "user_login"
            st.rerun()
    if st.button("⬅ Back to login"):
        st.session_state.auth_view = "user_login"
        st.rerun()


def render_admin_login():
    _apply_theme()
    st.markdown("### 🛡️ Administrator Login")
    with st.form("admin_login_form"):
        officer_id = st.text_input("Officer ID (Default: COMMAND-99)")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)
    if submitted:
        success, message = login_admin(officer_id.strip(), password)
        (st.success if success else st.error)(message)
        if success:
            st.rerun()
    if st.button("⬅ Back"):
        st.session_state.auth_view = "role_selection"
        st.rerun()