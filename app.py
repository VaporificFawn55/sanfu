import os
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import date
from psycopg2.extras import Json

# Load environment variables from .env file
load_dotenv()
app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def get_all_members():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM members ORDER BY created_at;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_member_id_by_name(name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM members WHERE name = %s", (name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def add_offering(member_id, amount, note=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO offerings (member_id, amount, note)
        VALUES (%s, %s, %s)
        RETURNING id, donated_at;
        """,
        (member_id, amount, note)
    )
    offering = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return offering

# Example: get donation log


def get_offerings_for_member(member_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, amount, currency, donated_at, note
        FROM offerings
        WHERE member_id = %s
        ORDER BY donated_at DESC;
        """,
        (member_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def delete_member(member_id: str):
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Delete related offerings first
        cur.execute("DELETE FROM offerings WHERE member_id = %s", (member_id,))

        # Then delete the member
        cur.execute("DELETE FROM members WHERE id = %s", (member_id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Error deleting member:", e)
    finally:
        cur.close()
        conn.close()
        print("delete done")


def create_member(name: str,
                  level_code: str,
                  status_code: str,
                  *,
                  gender: str | None = None,
                  birthdate: date | None = None,
                  phone: str | None = None,
                  email: str | None = None,
                  basic_info: dict | None = None):
    """
    Insert a member using codes from the lookup tables.
    Returns tuple: (id, name, membership_level_id, interview_status_id)
    """

    conn = get_connection()
    cur = conn.cursor()
    try:
        # --- Resolve membership level code -> id
        cur.execute(
            "SELECT id FROM membership_levels WHERE code = %s", (level_code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unknown membership level code: {level_code!r}")
        membership_level_id = row[0]

        # --- Resolve interview status code -> id
        cur.execute(
            "SELECT id FROM interview_statuses WHERE code = %s", (status_code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unknown interview status code: {status_code!r}")
        interview_status_id = row[0]

        # --- Insert member
        cur.execute(
            """
            INSERT INTO members
              (name, membership_level_id, interview_status_id, gender, birthdate, phone, email, basic_info)
            VALUES
              (%s,   %s,                   %s,                  %s,     %s,        %s,    %s,    %s)
            RETURNING id, name, membership_level_id, interview_status_id;
            """,
            (name, membership_level_id, interview_status_id, gender, birthdate, phone,
             email, psycopg2.extras.Json(basic_info) if basic_info is not None else None)
        )
        new_member = cur.fetchone()  # (id, name, membership_level_id, interview_status_id)
        conn.commit()
        return new_member

    except Exception as e:
        conn.rollback()
        print("Error creating member:", e)
        return None
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    print("Members:", get_all_members())  # testing get all
    print("ID: ", get_member_id_by_name("王小明"))  # testing search funciton
    # delete_member("8552b3f4-c2fd-4af4-b7c9-cd9fb197c079") # testing delete which will
    # testing the create
    result = create_member(
        name="王明",
        level_code="participant",
        status_code="undecided",
        gender="M",
        phone="555-1234",
        basic_info={"city": "Bellevue"}
    )

if result:
    member_id, member_name, level_id, status_id = result
    print("Created:", member_id, member_name, level_id, status_id)
    # Test donation (replace with a real UUID from your members table)
    # offering = add_offering("8bc9f775-a66a-47ea-bfdf-13fa3373a125", 1000, "測試奉獻")
    # print("Added offering:", offering)
    # print("Offerings:", get_offerings_for_member("8bc9f775-a66a-47ea-bfdf-13fa3373a125"))

# ---- Request body schema for creating a member ----


class MemberCreate(BaseModel):
    name: str
    membership_level: str
    interview_status: str

# ---- API endpoints ----


@app.get("/members")
def api_get_members():
    return get_all_members()


@app.get("/members/by-name/{name}")
def api_get_member_id(name: str):
    return {"id": get_member_id_by_name(name)}


@app.post("/members")
def api_add_member(member: MemberCreate):
    return create_member(member.name, member.membership_level, member.interview_status)


@app.delete("/members/{member_id}")
def api_delete_member(member_id: str):
    delete_member(member_id)
    return {"status": "deleted"}
