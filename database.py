"""Demo project database (SQLite) and the business functions the agent can call.

The data describes a fictional project "P24017 Airport BHS – Line 3" with two
control cabinets. It is made up for this demo. Two cables are deliberately
under-sized so the protection check has something to find.
"""
import math
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "project.db"
PROJECT = "P24017 Airport BHS – Line 3"
FUNCTION = "=BHS3"

# House values: max. protective device rating per copper cross-section (mm² -> A).
# Same table as in the companion RAG demo (DAS-EL-02). Simplified demo values.
MAX_PROTECTION_A = {0.75: 6, 1.0: 10, 1.5: 16, 2.5: 20, 4.0: 25, 6.0: 32, 10.0: 50, 16.0: 63}
VOLTAGE_DROP_LIMIT_PCT = 3.0
COPPER_CONDUCTIVITY = 56.0  # m / (ohm * mm²)
COS_PHI = 0.85

PARTS = [
    # part_number, description, category, rated_current_a, voltage, unit_price_eur, stock
    ("DP-MS-63", "Main switch 3P 63 A, door handle", "main switch", 63, "400V AC", 118.00, 6),
    ("DP-MCB-B2-1P", "Circuit breaker 1P B2", "circuit breaker", 2, "230V AC/24V DC", 9.40, 120),
    ("DP-MCB-B4-1P", "Circuit breaker 1P B4", "circuit breaker", 4, "230V AC/24V DC", 9.40, 95),
    ("DP-MCB-B6-1P", "Circuit breaker 1P B6", "circuit breaker", 6, "230V AC", 9.40, 80),
    ("DP-MCB-C16-3P", "Circuit breaker 3P C16", "circuit breaker", 16, "400V AC", 31.50, 40),
    ("DP-MCB-C20-3P", "Circuit breaker 3P C20", "circuit breaker", 20, "400V AC", 32.80, 25),
    ("DP-MCB-C25-3P", "Circuit breaker 3P C25", "circuit breaker", 25, "400V AC", 34.10, 18),
    ("DP-MPS-4.0", "Motor protection switch 2.5–4.0 A", "motor protection", 4.0, "400V AC", 48.90, 30),
    ("DP-MPS-6.3", "Motor protection switch 4.0–6.3 A", "motor protection", 6.3, "400V AC", 49.90, 22),
    ("DP-CON-9-24DC", "Contactor 9 A AC-3, coil 24 V DC", "contactor", 9, "400V AC", 27.60, 60),
    ("DP-VFD-1.5", "Frequency inverter 1.5 kW, 4.1 A out, STO", "frequency inverter", 4.1, "400V AC", 389.00, 12),
    ("DP-VFD-3.0", "Frequency inverter 3.0 kW, 7.3 A out, STO", "frequency inverter", 7.3, "400V AC", 512.00, 7),
    ("DP-PSU-24-10", "Power supply 24 V DC 10 A", "power supply", 10, "230V AC in", 142.00, 15),
    ("DP-PLC-CPU", "PLC CPU with PROFINET", "plc", None, "24V DC", 895.00, 4),
    ("DP-DI-16", "Digital input module 16 x 24 V DC", "plc io", None, "24V DC", 168.00, 20),
    ("DP-DO-16", "Digital output module 16 x 24 V DC 0.5 A", "plc io", None, "24V DC", 189.00, 18),
    ("DP-SAFE-RLY", "Safety relay for emergency stop, 2 channels", "safety", None, "24V DC", 214.00, 9),
    ("DP-REL-24", "Coupling relay 24 V DC, 1 changeover 6 A", "relay", 6, "24V DC", 11.80, 150),
    ("DP-MOT-1.5", "Gear motor 1.5 kW 400 V, 3.4 A", "motor", 3.4, "400V AC", 610.00, 5),
    ("DP-MOT-3.0", "Gear motor 3.0 kW 400 V, 6.2 A", "motor", 6.2, "400V AC", 845.00, 3),
    ("DP-MOT-0.75", "Gear motor 0.75 kW 400 V, 1.9 A", "motor", 1.9, "400V AC", 455.00, 8),
    ("DP-SOCK-16-3P", "Maintenance socket outlet CEE 16 A 400 V", "socket outlet", 16, "400V AC", 64.00, 10),
    ("DP-SUBD-32", "Field sub-distribution box 32 A", "distribution", 32, "400V AC", 289.00, 3),
]

DEVICES = [
    # tag, description, part_number, cabinet, page
    ("-Q1", "Main switch cabinet 1", "DP-MS-63", "CAB1", 10),
    ("-F11", "Supply inverter conveyor CONV01 (merge)", "DP-MCB-C20-3P", "CAB1", 11),
    ("-T11", "Inverter conveyor CONV01 (merge)", "DP-VFD-3.0", "CAB1", 11),
    ("-M11", "Drive motor CONV01 (merge)", "DP-MOT-3.0", "FIELD", 11),
    ("-F12", "Motor protection CONV02, set to 1.9 A", "DP-MPS-4.0", "CAB1", 12),
    ("-Q12", "Motor contactor CONV02", "DP-CON-9-24DC", "CAB1", 12),
    ("-M12", "Drive motor CONV02 (transport, direct-on-line)", "DP-MOT-0.75", "FIELD", 12),
    ("-F13", "Supply inverter conveyor CONV03", "DP-MCB-C16-3P", "CAB1", 13),
    ("-T13", "Inverter conveyor CONV03", "DP-VFD-1.5", "CAB1", 13),
    ("-M13", "Drive motor CONV03", "DP-MOT-1.5", "FIELD", 13),
    ("-F14", "Supply maintenance socket outlet line 3", "DP-MCB-C20-3P", "CAB1", 14),
    ("-X14", "Maintenance socket outlet line 3", "DP-SOCK-16-3P", "FIELD", 14),
    ("-F21", "Supply 24 V power supply", "DP-MCB-B6-1P", "CAB1", 21),
    ("-T21", "24 V DC power supply", "DP-PSU-24-10", "CAB1", 21),
    ("-F22", "24 V field sensors group 1", "DP-MCB-B2-1P", "CAB1", 22),
    ("-F23", "24 V PLC outputs group 1", "DP-MCB-B4-1P", "CAB1", 22),
    ("-A1", "PLC CPU line 3", "DP-PLC-CPU", "CAB1", 30),
    ("-A2", "Digital inputs 1", "DP-DI-16", "CAB1", 31),
    ("-A3", "Digital outputs 1", "DP-DO-16", "CAB1", 32),
    ("-A4", "Safety relay emergency stop zone 3", "DP-SAFE-RLY", "CAB1", 35),
    ("-K32", "Coupling relay release CONV02", "DP-REL-24", "CAB1", 32),
    ("-K33", "Coupling relay fault lamp", "DP-REL-24", "CAB1", 32),
    ("-F51", "Supply inverter sorter infeed CONV05", "DP-MCB-C20-3P", "CAB2", 51),
    ("-T51", "Inverter sorter infeed CONV05", "DP-VFD-3.0", "CAB2", 51),
    ("-M51", "Drive motor sorter infeed CONV05", "DP-MOT-3.0", "FIELD", 51),
    ("-F52", "Supply field sub-distribution line 3", "DP-MCB-C25-3P", "CAB2", 52),
    ("-X52", "Field sub-distribution line 3", "DP-SUBD-32", "FIELD", 52),
]

CABLES = [
    # tag, from, to, protected_by, cross_section_mm2, cores, shielded, length_m
    ("-W11", "-T11", "-M11", "-T11", 1.5, "4G1.5", 1, 35),
    ("-W12", "-Q12", "-M12", "-F12", 1.5, "4G1.5", 0, 28),
    ("-W13", "-T13", "-M13", "-T13", 1.5, "4G1.5", 1, 62),
    ("-W14", "-F14", "-X14", "-F14", 1.5, "5G1.5", 0, 40),   # error: 20 A on 1.5 mm²
    ("-W22", "-F22", "FIELD sensors", "-F22", 0.75, "3G0.75", 0, 55),
    ("-W51", "-T51", "-M51", "-T51", 1.5, "4G1.5", 1, 48),
    ("-W52", "-F52", "-X52", "-F52", 2.5, "5G2.5", 0, 30),   # error: 25 A on 2.5 mm²
]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset=False):
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS parts (part_number TEXT PRIMARY KEY, description TEXT, category TEXT,
                rated_current_a REAL, voltage TEXT, unit_price_eur REAL, stock INTEGER);
            CREATE TABLE IF NOT EXISTS devices (tag TEXT PRIMARY KEY, description TEXT,
                part_number TEXT REFERENCES parts(part_number), cabinet TEXT, page INTEGER);
            CREATE TABLE IF NOT EXISTS cables (tag TEXT PRIMARY KEY, from_tag TEXT, to_tag TEXT,
                protected_by TEXT, cross_section_mm2 REAL, type TEXT, shielded INTEGER, length_m REAL);
            CREATE TABLE IF NOT EXISTS change_requests (id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, description TEXT, affected_tags TEXT, status TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        if c.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 0:
            c.executemany("INSERT INTO parts VALUES (?,?,?,?,?,?,?)", PARTS)
            c.executemany("INSERT INTO devices VALUES (?,?,?,?,?)", DEVICES)
            c.executemany("INSERT INTO cables VALUES (?,?,?,?,?,?,?,?)", CABLES)


# ---------- helpers ----------

def normalize_tag(tag):
    """Accept 'F14', '-F14', '=BHS3+CAB1-F14' or '-f14' and return '-F14'."""
    tag = str(tag).strip().upper()
    m = re.search(r"-?([A-Z]+\d+)$", tag)
    return f"-{m.group(1)}" if m else tag


def full_designation(tag, cabinet):
    return f"{FUNCTION}+{cabinet}{tag}"


# ---------- tools ----------

def search_parts(query="", category=None, min_rated_current_a=None):
    sql = "SELECT * FROM parts WHERE (description LIKE ? OR part_number LIKE ? OR category LIKE ?)"
    args = [f"%{query}%"] * 3
    if category:
        sql += " AND category LIKE ?"
        args.append(f"%{category}%")
    if min_rated_current_a is not None:
        sql += " AND rated_current_a >= ?"
        args.append(min_rated_current_a)
    with connect() as c:
        rows = [dict(r) for r in c.execute(sql + " ORDER BY category, rated_current_a LIMIT 15", args)]
    return {"count": len(rows), "parts": rows}


def get_device(tag):
    tag = normalize_tag(tag)
    with connect() as c:
        d = c.execute("""SELECT d.*, p.description AS part_description, p.category, p.rated_current_a,
                                p.unit_price_eur FROM devices d JOIN parts p USING(part_number)
                         WHERE d.tag = ?""", (tag,)).fetchone()
        if not d:
            return {"found": False, "message": f"Device {tag} does not exist in project {PROJECT}."}
        cables = [dict(r) for r in c.execute(
            "SELECT tag, from_tag, to_tag, type, length_m FROM cables WHERE from_tag=? OR to_tag=? OR protected_by=?",
            (tag, tag, tag))]
    d = dict(d)
    d["full_designation"] = full_designation(tag, d["cabinet"] if d["cabinet"] != "FIELD" else "FIELD")
    return {"found": True, "device": d, "connected_cables": cables}


def list_cabinet_devices(cabinet):
    cabinet = cabinet.strip().upper().replace(" ", "")
    if cabinet.isdigit():
        cabinet = f"CAB{cabinet}"
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT tag, description, part_number, page FROM devices WHERE cabinet=? ORDER BY page, tag",
            (cabinet,))]
    if not rows:
        return {"found": False, "message": f"No devices found for location {cabinet}. Known: CAB1, CAB2, FIELD."}
    return {"cabinet": cabinet, "count": len(rows), "devices": rows}


def _check_cable(c, cable):
    dev = c.execute("""SELECT d.tag, p.description, p.category, p.rated_current_a FROM devices d
                       JOIN parts p USING(part_number) WHERE d.tag=?""", (cable["protected_by"],)).fetchone()
    limit = MAX_PROTECTION_A.get(cable["cross_section_mm2"])
    rating = dev["rated_current_a"]
    ok = limit is not None and rating is not None and rating <= limit
    result = {
        "cable": cable["tag"], "type": cable["type"], "cross_section_mm2": cable["cross_section_mm2"],
        "protected_by": dev["tag"], "protective_device": dev["description"],
        "protection_rating_a": rating, "max_allowed_a_for_cross_section": limit,
        "result": "OK" if ok else "NOT OK",
    }
    if not ok and limit is not None:
        needed = min((cs for cs, a in MAX_PROTECTION_A.items() if a >= rating), default=None)
        result["suggestion"] = (
            f"Either increase the cross-section to at least {needed:g} mm² or reduce the protective "
            f"device to max. {limit} A (if the load allows it)."
        )
    return result


def check_cable_protection(cable_tag=None):
    with connect() as c:
        if cable_tag:
            row = c.execute("SELECT * FROM cables WHERE tag=?", (normalize_tag(cable_tag),)).fetchone()
            if not row:
                return {"found": False, "message": f"Cable {normalize_tag(cable_tag)} does not exist."}
            return _check_cable(c, row)
        results = [_check_cable(c, r) for r in c.execute("SELECT * FROM cables ORDER BY tag")]
    problems = [r for r in results if r["result"] != "OK"]
    return {"rule": "DAS-EL-02 house table (demo values)", "cables_checked": len(results),
            "problems_found": len(problems), "problems": problems,
            "ok_cables": [r["cable"] for r in results if r["result"] == "OK"]}


def calculate_voltage_drop(cable_tag, current_a=None):
    with connect() as c:
        cable = c.execute("SELECT * FROM cables WHERE tag=?", (normalize_tag(cable_tag),)).fetchone()
        if not cable:
            return {"found": False, "message": f"Cable {normalize_tag(cable_tag)} does not exist."}
        if current_a is None:
            # assume the load current = rating of the protecting device (worst case)
            current_a = c.execute("""SELECT p.rated_current_a FROM devices d JOIN parts p USING(part_number)
                                     WHERE d.tag=?""", (cable["protected_by"],)).fetchone()[0]
    u_drop = math.sqrt(3) * current_a * cable["length_m"] * COS_PHI / (COPPER_CONDUCTIVITY * cable["cross_section_mm2"])
    pct = 100 * u_drop / 400
    return {
        "cable": cable["tag"], "length_m": cable["length_m"], "cross_section_mm2": cable["cross_section_mm2"],
        "current_a": current_a, "voltage_drop_v": round(u_drop, 2), "voltage_drop_pct": round(pct, 2),
        "limit_pct": VOLTAGE_DROP_LIMIT_PCT, "result": "OK" if pct <= VOLTAGE_DROP_LIMIT_PCT else "NOT OK",
        "formula": "ΔU = √3 · I · L · cosφ / (κ · A), κ = 56 m/(Ω·mm²), cosφ = 0.85, 400 V three-phase",
    }


def generate_bom(cabinet=None):
    sql = """SELECT d.part_number, p.description, COUNT(*) AS quantity, p.unit_price_eur,
                    ROUND(COUNT(*) * p.unit_price_eur, 2) AS total_eur, GROUP_CONCAT(d.tag, ', ') AS tags
             FROM devices d JOIN parts p USING(part_number)"""
    args = []
    if cabinet:
        cabinet = cabinet.strip().upper().replace(" ", "")
        sql += " WHERE d.cabinet = ?"
        args.append(cabinet if not cabinet.isdigit() else f"CAB{cabinet}")
    sql += " GROUP BY d.part_number ORDER BY p.category"
    with connect() as c:
        rows = [dict(r) for r in c.execute(sql, args)]
    return {"project": PROJECT, "scope": cabinet or "whole project", "positions": rows,
            "total_eur": round(sum(r["total_eur"] for r in rows), 2)}


def create_change_request(title, description, affected_tags):
    tags = [normalize_tag(t) for t in affected_tags]
    with connect() as c:
        known = {r[0] for r in c.execute("SELECT tag FROM devices UNION SELECT tag FROM cables")}
        unknown = [t for t in tags if t not in known]
        if unknown:
            return {"created": False, "message": f"Unknown tags: {', '.join(unknown)}. Nothing was created."}
        cur = c.execute(
            "INSERT INTO change_requests(title, description, affected_tags, status) VALUES (?,?,?,?)",
            (title, description, ", ".join(tags), "DRAFT – needs approval by an engineer"))
    return {"created": True, "change_request_id": f"CR-{cur.lastrowid:03d}", "status": "DRAFT – needs approval by an engineer"}


def list_change_requests():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM change_requests ORDER BY id DESC")]
