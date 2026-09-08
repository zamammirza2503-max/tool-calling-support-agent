import sqlite3
from pathlib import Path

DB_PATH = Path("support.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                item TEXT NOT NULL,
                status TEXT NOT NULL,
                eta TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                issue TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)

        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                [
                    ("1001", "C001", "Wireless Headphones", "shipped", "2026-09-10"),
                    ("1002", "C001", "USB-C Dock", "delivered", "2026-09-05"),
                    ("1003", "C002", "Mechanical Keyboard", "processing", "2026-09-12"),
                ],
            )


def get_order_status(order_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT order_id, item, status, eta FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    if not row:
        return {"found": False, "message": f"Order {order_id} was not found."}
    return {
        "found": True,
        "order_id": row[0],
        "item": row[1],
        "status": row[2],
        "eta": row[3],
    }


def get_customer_orders(customer_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT order_id, item, status, eta FROM orders WHERE customer_id = ?",
            (customer_id,),
        ).fetchall()
    return [
        {"order_id": r[0], "item": r[1], "status": r[2], "eta": r[3]}
        for r in rows
    ]


def create_support_ticket(customer_id, issue):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tickets(customer_id, issue, status) VALUES (?, ?, ?)",
            (customer_id, issue, "open"),
        )
        ticket_id = cursor.lastrowid
    return {"ticket_id": ticket_id, "status": "open"}
