import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from fpdf import FPDF
import os
import base64

# ---------- Database Setup ----------
conn = sqlite3.connect("user_transactions.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        type TEXT,
        description TEXT,
        timestamp TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

conn.commit()

ADMIN_EMAIL = "admin@example.com"

# ---------- Helper Functions ----------
def add_user(name, email, password):
    try:
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
        conn.commit()
        st.success("User added successfully.")
    except sqlite3.IntegrityError:
        st.warning("User with this email already exists.")

def delete_user(user_id):
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
    conn.commit()
    st.success("User and their transactions deleted successfully.")

def authenticate_user(email, password):
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
    return cursor.fetchone()

def add_transaction(user_id, amount, type_, description):
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO transactions (user_id, amount, type, description, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, type_, description, timestamp)
    )
    conn.commit()
    st.success("Transaction added successfully.")

def delete_transaction(user_id, transaction_id):
    cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (transaction_id, user_id))
    conn.commit()
    st.success("Transaction deleted successfully.")

def get_transactions(user_id):
    cursor.execute("SELECT id, amount, type, description, timestamp FROM transactions WHERE user_id = ?", (user_id,))
    return cursor.fetchall()

def export_pdf(user):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    today = datetime.today()
    if today.day >= 13:
        bill_start = today.replace(day=13)
    else:
        if today.month == 1:
            bill_start = today.replace(year=today.year - 1, month=12, day=13)
        else:
            bill_start = today.replace(month=today.month - 1, day=13)

    next_month = bill_start.month % 12 + 1
    year = bill_start.year + (1 if next_month == 1 else 0)
    bill_end = datetime(year=year, month=next_month, day=12)
    due_date = bill_start + timedelta(days=50)

    cursor.execute('''
        SELECT amount, type, description, timestamp FROM transactions
        WHERE user_id = ? AND timestamp BETWEEN ? AND ?
    ''', (user[0], bill_start.isoformat(), bill_end.isoformat()))

    transactions = cursor.fetchall()
    total_due = sum(t[0] for t in transactions if t[1] == 'debit')

    pdf.cell(200, 10, txt=f"Statement for {user[1]} ({user[2]})", ln=True)
    pdf.cell(200, 10, txt=f"Billing Period: {bill_start.date()} to {bill_end.date()}", ln=True)
    pdf.cell(200, 10, txt=f"Due Date: {due_date.date()}", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Date", 1)
    pdf.cell(30, 10, "Type", 1)
    pdf.cell(40, 10, "Amount", 1)
    pdf.cell(70, 10, "Description", 1)
    pdf.ln()

    pdf.set_font("Arial", size=12)
    for t in transactions:
        description = (t[2][:30] + '...') if len(t[2]) > 33 else t[2]
        pdf.cell(50, 10, t[3][:19], 1)
        pdf.cell(30, 10, t[1].upper(), 1)
        pdf.cell(40, 10, f"Rs.{t[0]:.2f}", 1)
        pdf.cell(70, 10, description, 1)
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"TOTAL DUE (to be paid by {due_date.date()}): Rs.{total_due:.2f}", ln=True)

    filename = f"{user[1].replace(' ', '_')}_due_{due_date.date()}.pdf"
    pdf.output(filename)

    with open(filename, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<a href="data:application/octet-stream;base64,{base64_pdf}" download="{filename}">Download PDF Statement</a>'
        st.markdown(pdf_display, unsafe_allow_html=True)

    os.remove(filename)

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Transaction Manager", layout="centered")
st.title("📑 User Transaction Manager")

email = st.text_input("Enter your email")
password = st.text_input("Enter your password", type="password")

if email and password:
    user = authenticate_user(email, password)
    is_admin = (email == ADMIN_EMAIL and user)

    if not user:
        st.warning("Invalid email or password.")
    else:
        st.success(f"Welcome, {user[1]}")

        if is_admin:
            tabs = st.tabs([
                "➕ Add User", "👥 Delete User", "💰 Add Transaction",
                "📄 View Statement", "🗑 Delete Transaction",
                "📤 Export as PDF", "🔒 Change Password", "📋 View All Users"
            ])

            with tabs[0]:
                name = st.text_input("Name")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
                if st.button("Add User"):
                    add_user(name, new_email, new_password)

            with tabs[1]:
                user_list = cursor.execute("SELECT id, name, email FROM users WHERE email != ?", (ADMIN_EMAIL,)).fetchall()
                selected_user = st.selectbox("Select User to Delete", options=user_list, format_func=lambda x: x[1])
                if st.button("Delete User"):
                    delete_user(selected_user[0])

            with tabs[2]:
                user_list = cursor.execute("SELECT id, name, email FROM users").fetchall()
                selected_user = st.selectbox("Select User", options=user_list, format_func=lambda x: x[1])
                amount = st.number_input("Amount", min_value=0.0, format="%.2f")
                type_ = st.radio("Type", ["credit", "debit"])
                description = st.text_input("Description")
                if st.button("Submit Transaction"):
                    add_transaction(selected_user[0], amount, type_, description)

            with tabs[3]:
                user_list = cursor.execute("SELECT id, name, email FROM users").fetchall()
                selected_user = st.selectbox("Select User to View", options=user_list, format_func=lambda x: x[1])
                transactions = get_transactions(selected_user[0])
                st.subheader("Transaction History")
                if transactions:
                    st.dataframe(transactions, use_container_width=True)
                else:
                    st.info("No transactions found.")

            with tabs[4]:
                user_list = cursor.execute("SELECT id, name, email FROM users").fetchall()
                selected_user = st.selectbox("Select User to Delete From", options=user_list, format_func=lambda x: x[1])
                transactions = get_transactions(selected_user[0])
                trans_ids = {f"{t[0]} | {t[4][:16]} | {t[2]} ₹{t[1]}": t[0] for t in transactions}
                selected = st.selectbox("Select Transaction to Delete", list(trans_ids.keys()))
                if st.button("Delete Transaction"):
                    delete_transaction(selected_user[0], trans_ids[selected])

            with tabs[5]:
                user_list = cursor.execute("SELECT id, name, email FROM users").fetchall()
                selected_user = st.selectbox("Select User to Export PDF", options=user_list, format_func=lambda x: x[1])
                export_pdf(selected_user)

            with tabs[6]:
                st.subheader("Change Password")
                current_password = st.text_input("Current Password", type="password")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")

                if st.button("Update Password"):
                    if current_password != user[3]:
                        st.error("Current password is incorrect.")
                    elif new_password != confirm_password:
                        st.error("New passwords do not match.")
                    elif new_password == "":
                        st.error("New password cannot be empty.")
                    else:
                        cursor.execute("UPDATE users SET password = ? WHERE email = ?", (new_password, email))
                        conn.commit()
                        st.success("Password updated successfully.")

            with tabs[7]:
                st.subheader("All Registered Users")
                users = cursor.execute("SELECT id, name, email FROM users").fetchall()
                user_data = []
                for u in users:
                    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN type='credit' THEN amount ELSE 0 END), SUM(CASE WHEN type='debit' THEN amount ELSE 0 END) FROM transactions WHERE user_id = ?", (u[0],))
                    count, total_credit, total_debit = cursor.fetchone()
                    user_data.append({
                        "User ID": u[0],
                        "Name": u[1],
                        "Email": u[2],
                        "Transactions": count,
                        "Total Credit": f"Rs.{total_credit:.2f}" if total_credit else "Rs.0.00",
                        "Total Debit": f"Rs.{total_debit:.2f}" if total_debit else "Rs.0.00"
                    })
                st.dataframe(user_data, use_container_width=True)

        else:
            tabs = st.tabs(["📄 View Statement", "📤 Export as PDF", "🔒 Change Password"])
            with tabs[0]:
                transactions = get_transactions(user[0])
                st.subheader("Transaction History")
                if transactions:
                    st.dataframe(transactions, use_container_width=True)
                else:
                    st.info("No transactions found.")

            with tabs[1]:
                export_pdf(user)

            with tabs[2]:
                st.subheader("Change Password")
                current_password = st.text_input("Current Password", type="password")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")

                if st.button("Update Password"):
                    if current_password != user[3]:
                        st.error("Current password is incorrect.")
                    elif new_password != confirm_password:
                        st.error("New passwords do not match.")
                    elif new_password == "":
                        st.error("New password cannot be empty.")
                    else:
                        cursor.execute("UPDATE users SET password = ? WHERE email = ?", (new_password, email))
                        conn.commit()
                        st.success("Password updated successfully.")
