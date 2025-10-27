import os
from typing import Any, Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, date

import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


# ---------- connection ----------
def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


# ---------- helpers ----------
def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, Decimal):
        return float(x)
    return x  # already a float or numeric


def _member_row_to_dict(row: Tuple[Any, ...]) -> Dict[str, Any]:
    # row = (id, name)
    return {"id": row[0], "name": row[1]}


def _offering_row_to_dict(row: Tuple[Any, ...]) -> Dict[str, Any]:
    # row = (id, amount, currency, donated_at, note)
    return {
        "id": row[0],
        "amount": _to_float(row[1]),
        "currency": row[2],
        "donated_at": row[3],  # FastAPI serializes datetimes
        "note": row[4],
    }


def _resolve_lookup_id(
    cur,
    table: str,
    value: Optional[Union[int, str]],
) -> Optional[int]:
    """
    Accept either a numeric ID or a code string and return the row id.
    Returns None if value is None.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    # treat as code (text)
    cur.execute(f"SELECT id FROM {table} WHERE code = %s", (value,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown code in {table}: {value!r}")
    return int(row[0])


# ---------- members ----------
def get_all_members() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM members ORDER BY created_at;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_member_row_to_dict(r) for r in rows]


def search_members_by_name(term: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name FROM members WHERE name ILIKE %s ORDER BY name",
        (f"%{term}%",),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_member_row_to_dict(r) for r in rows]


def get_member_id_by_name(name: str) -> Optional[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM members WHERE name = %s", (name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def create_member(
    name: str,
    membership_level: Optional[Union[int, str]],
    interview_status: Optional[Union[int, str]],
    *,
    gender: Optional[str] = None,
    birthdate: Optional[date] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    basic_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a member. membership_level / interview_status can be either:
      - an integer FK id (e.g., 2), or
      - a string code (e.g., 'participant', 'undecided'), or
      - None
    Returns: {"id": uuid, "name": str}
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        level_id = _resolve_lookup_id(cur, "membership_levels", membership_level)
        status_id = _resolve_lookup_id(cur, "interview_statuses", interview_status)

        cur.execute(
            """
            INSERT INTO members
              (name, membership_level_id, interview_status_id, gender, birthdate, phone, email, basic_info)
            VALUES
              (%s,   %s,                  %s,                  %s,     %s,        %s,    %s,    %s)
            RETURNING id, name;
            """,
            (
                name,
                level_id,
                status_id,
                gender,
                birthdate,
                phone,
                email,
                Json(basic_info) if basic_info is not None else None,
            ),
        )
        new_id, new_name = cur.fetchone()
        conn.commit()
        return {"id": new_id, "name": new_name}

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def delete_member(member_id: str) -> int:
    """
    Deletes a member and their offerings.
    Returns the number of deleted members (0 or 1).
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM offerings WHERE member_id = %s", (member_id,))
        cur.execute("DELETE FROM members WHERE id = %s", (member_id,))
        deleted = cur.rowcount
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------- offerings ----------
def add_offering(
    member_id: str,
    amount: Union[int, float, Decimal],
    *,
    note: str = "",
    donated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        if donated_at is None:
            cur.execute(
                """
                INSERT INTO offerings (member_id, amount, note)
                VALUES (%s, %s, %s)
                RETURNING id, amount, currency, donated_at, note;
                """,
                (member_id, amount, note),
            )
        else:
            cur.execute(
                """
                INSERT INTO offerings (member_id, amount, note, donated_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id, amount, currency, donated_at, note;
                """,
                (member_id, amount, note, donated_at),
            )
        row = cur.fetchone()
        conn.commit()
        return _offering_row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_offerings_for_member(member_id: str) -> Dict[str, Any]:
    """
    Returns {"member_id": str, "total": float, "log": [ {offering...}, ... ]}
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, amount, currency, donated_at, note
            FROM offerings
            WHERE member_id = %s
            ORDER BY donated_at DESC;
            """,
            (member_id,),
        )
        rows = cur.fetchall()
        log = [_offering_row_to_dict(r) for r in rows]
        total = round(sum(o["amount"] or 0 for o in log), 2)
        return {"member_id": member_id, "total": total, "log": log}
    finally:
        cur.close()
        conn.close()
