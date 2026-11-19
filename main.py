
import csv
import json
import re
import os

from datetime import datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# ------------------------------------------
# 1. INITIAL SETTINGS
# ------------------------------------------

load_dotenv()

client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)

ISSUES = [
    "electrical",
    "plumbing",
    "carpentry",
    "cleaning",
    "internet",
    "other"
]

# Issue-to-team dictionary

TEAM_MAP = {
    "electrical": "Electrician",
    "plumbing": "Plumber",
    "carpentry": "Carpenter",
    "cleaning": "Housekeeping",
    "internet": "IT Support",
    "other": "Facilities Office"
}

# Dictionary for duplicate detection

ticket_lookup = {}

# All tickets are stored here

tickets = []


# ------------------------------------------
# 2. LOAD SYSTEM PROMPT
# ------------------------------------------

def load_prompt():
    """Read the LLM system prompt."""

    prompt_file = BASE_DIR / "system_prompt.txt"

    with open(prompt_file, "r", encoding="utf-8") as file:
        return file.read()


# ------------------------------------------
# 3. ROOM EXTRACTION
# ------------------------------------------

def check_room(complaint, llm_room):
    """
    Check whether the room exists in the complaint.
    The LLM cannot invent or correct room numbers.
    """

    pattern = r"(?<![A-Z0-9])([A-D])[- ]?([1-4][0-9]{2})(?![0-9])"

    matches = re.findall(pattern, complaint.upper())

    if not matches:
        return None

    if llm_room is None:
        return None

    llm_room = str(llm_room).upper().replace("-", "").replace(" ", "")

    for block, number in matches:

        room = block + number

        floor = int(number[0])
        room_number = int(number[1:])

        if floor not in range(1, 5):
            continue

        if room_number not in range(1, 21):
            continue

        if room == llm_room:
            return room

    return None


# ------------------------------------------
# 4. VALIDATE LLM JSON
# ------------------------------------------

def is_valid(data):
    """Check the LLM response structure and values."""

    if not isinstance(data, dict):
        return False

    required = {"room", "issue", "urgent", "summary"}

    if set(data.keys()) != required:
        return False

    if data["room"] is not None and not isinstance(data["room"], str):
        return False

    if data["issue"] not in ISSUES:
        return False

    if not isinstance(data["urgent"], bool):
        return False

    if not isinstance(data["summary"], str):
        return False

    if len(data["summary"].split()) > 10:
        return False

    return True


# ------------------------------------------
# 5. FALLBACK CLASSIFICATION
# ------------------------------------------

def fallback_classify(complaint):
    """
    Safe fallback if the API fails or returns
    invalid JSON.

    The issue is marked other for manual review.
    """

    pattern = r"(?<![A-Z0-9])([A-D])[- ]?([1-4][0-9]{2})(?![0-9])"

    matches = re.findall(pattern, complaint.upper())

    room = None

    if matches:
        block, number = matches[0]

        if int(number[1:]) in range(1, 21):
            room = block + number

    return {
        "room": room,
        "issue": "other",
        "urgent": False,
        "summary": "Requires manual classification"
    }


# ------------------------------------------
# 6. LLM CLASSIFICATION
# ------------------------------------------

def classify(complaint):
    """Send a complaint to the LLM and get JSON."""

    if client is None:
        print("API key missing. Using fallback.")
        return fallback_classify(complaint)

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",

            messages=[
                {
                    "role": "system",
                    "content": load_prompt()
                },
                {
                    "role": "user",
                    "content": "Classify this complaint:\n" + complaint
                }
            ],

            response_format={"type": "json_object"},
            temperature=0
        )

        result = response.choices[0].message.content

        data = json.loads(result)

        if is_valid(data):
            return data

        print("Invalid LLM response. Using fallback.")

        return fallback_classify(complaint)

    except Exception as error:

        print("LLM error:", error)

        return fallback_classify(complaint)


# ------------------------------------------
# 7. PYTHON SAFETY NET
# ------------------------------------------

def apply_safety_net(complaint, data):
    """
    Python can increase urgency but never
    reduce urgency assigned by the LLM.
    """

    text = complaint.lower()

    safety_words = [
        "spark",
        "shock",
        "overflowing",
        "near the switch",
        "flood",
        "burning smell"
    ]

    if any(word in text for word in safety_words):
        data["urgent"] = True

    # Water near electrical fittings is electrical.

    water_words = ["water", "leak", "flood", "overflow"]

    electrical_words = [
        "electrical fitting",
        "switchboard",
        "switch",
        "socket",
        "wiring"
    ]

    has_water = any(word in text for word in water_words)

    has_electrical = any(
        word in text for word in electrical_words
    )

    if has_water and has_electrical:
        data["issue"] = "electrical"
        data["urgent"] = True

    return data


# ------------------------------------------
# 8. ASSIGN MAINTENANCE TEAM
# ------------------------------------------

def assign(issue):
    """Find the correct team for an issue."""

    return TEAM_MAP.get(issue, "Facilities Office")


# ------------------------------------------
# 9. CALCULATE DUE DATE
# ------------------------------------------

def due_date(complaint_date, urgent):
    """Urgent: same day. Normal: within two days."""

    date = datetime.strptime(
        complaint_date, "%Y-%m-%d"
    ).date()

    if urgent:
        return date

    return date + timedelta(days=2)


# ------------------------------------------
# 10. LOAD EXISTING TICKETS
# ------------------------------------------

def load_open_tickets():
    """Load previously opened tickets."""

    filename = BASE_DIR / "open_tickets.csv"

    with open(filename, "r", newline="", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        for row in reader:

            ticket = {
                "ticket": row["ticket"],
                "room": row["room"].upper(),
                "issue": row["issue"].lower(),
                "opened": row["opened"],
                "due": "",
                "urgent": False,
                "team": assign(row["issue"].lower()),
                "complaints": [],
                "summaries": []
            }

            tickets.append(ticket)

            key = (ticket["room"], ticket["issue"])

            ticket_lookup[key] = ticket


# ------------------------------------------
# 11. CREATE NEW TICKET ID
# ------------------------------------------

def next_ticket_id():
    """Generate the next ticket number."""

    numbers = []

    for ticket in tickets:

        match = re.search(r"(\d+)$", ticket["ticket"])

        if match:
            numbers.append(int(match.group(1)))

    next_number = max(numbers, default=0) + 1

    return f"T{next_number:03d}"


# ------------------------------------------
# 12. PROCESS ONE COMPLAINT
# ------------------------------------------

def process_complaint(row):
    """Classify, validate and route one complaint."""

    complaint_id = row["id"]
    complaint_date = row["date"]
    complaint = row["complaint"]

    data = classify(complaint)

    data = apply_safety_net(complaint, data)

    # Validate room independently using the complaint text.

    room = check_room(complaint, data["room"])

    if room is None:

        return {
            "id": complaint_id,
            "room": "",
            "issue": data["issue"],
            "urgent": data["urgent"],
            "status": "needs more info",
            "ticket": ""
        }

    issue = data["issue"]

    key = (room, issue)

    # Check whether the ticket already exists.

    if key in ticket_lookup:

        ticket = ticket_lookup[key]

        ticket["complaints"].append(complaint_id)
        ticket["summaries"].append(data["summary"])

        # An urgent repeat makes the ticket urgent.

        ticket["urgent"] = (
            ticket["urgent"] or data["urgent"]
        )

        if ticket["urgent"]:
            ticket["due"] = due_date(
                complaint_date, True
            ).isoformat()

        return {
            "id": complaint_id,
            "room": room,
            "issue": issue,
            "urgent": data["urgent"],
            "status": "duplicate",
            "ticket": ticket["ticket"]
        }

    # Create a new ticket.

    ticket = {
        "ticket": next_ticket_id(),
        "room": room,
        "issue": issue,
        "opened": complaint_date,
        "due": due_date(
            complaint_date, data["urgent"]
        ).isoformat(),
        "urgent": data["urgent"],
        "team": assign(issue),
        "complaints": [complaint_id],
        "summaries": [data["summary"]]
    }

    tickets.append(ticket)

    ticket_lookup[key] = ticket

    return {
        "id": complaint_id,
        "room": room,
        "issue": issue,
        "urgent": data["urgent"],
        "status": "new ticket",
        "ticket": ticket["ticket"]
    }


# ------------------------------------------
# 13. WRITE ALL REPORTS
# ------------------------------------------

def write_reports(results, needs_info):
    """Write the four required output files."""

    # Sort: urgent tickets first, then by team.

    sorted_tickets = sorted(
        tickets,
        key=lambda t: (
            not t["urgent"],
            t["team"]
        )
    )

    # WORK ORDERS CSV

    with open(
        OUTPUT_DIR / "work_orders.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        fields = [
            "ticket",
            "room",
            "issue",
            "team",
            "urgent",
            "opened",
            "due_date",
            "complaint_ids",
            "summaries"
        ]

        writer = csv.DictWriter(
            file, fieldnames=fields
        )

        writer.writeheader()

        for ticket in sorted_tickets:

            writer.writerow({
                "ticket": ticket["ticket"],
                "room": ticket["room"],
                "issue": ticket["issue"],
                "team": ticket["team"],
                "urgent": ticket["urgent"],
                "opened": ticket["opened"],
                "due_date": ticket["due"],
                "complaint_ids": "; ".join(
                    ticket["complaints"]
                ),
                "summaries": "; ".join(
                    ticket["summaries"]
                )
            })

    # RESULTS CSV

    with open(
        OUTPUT_DIR / "results.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        fields = [
            "id",
            "room",
            "issue",
            "urgent",
            "status",
            "ticket"
        ]

        writer = csv.DictWriter(
            file, fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)

    # NEEDS INFO CSV

    with open(
        OUTPUT_DIR / "needs_info.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=["id", "date", "complaint"]
        )

        writer.writeheader()
        writer.writerows(needs_info)

    # SUMMARY TXT

    with open(
        OUTPUT_DIR / "summary.txt",
        "w",
        encoding="utf-8"
    ) as file:

        file.write("HOSTEL FACILITIES SUMMARY\n")
        file.write("=========================\n\n")

        file.write("TICKETS BY TEAM\n")

        team_counts = Counter(
            t["team"] for t in tickets
        )

        for team, count in sorted(team_counts.items()):
            file.write(f"{team}: {count}\n")

        file.write("\nTICKETS BY BLOCK\n")

        block_counts = Counter(
            t["room"][0]
            for t in tickets
            if t["room"]
        )

        for block, count in sorted(block_counts.items()):
            file.write(f"Block {block}: {count}\n")

        file.write("\nROOMS WITH REPEAT COMPLAINTS\n")

        repeat_rooms = defaultdict(int)

        for ticket in tickets:

            if len(ticket["complaints"]) > 1:
                repeat_rooms[ticket["room"]] += (
                    len(ticket["complaints"]) - 1
                )

        if repeat_rooms:

            for room, count in sorted(repeat_rooms.items()):
                file.write(f"{room}: {count} repeat complaints\n")

        else:
            file.write("No repeat complaints found.\n")

        file.write("\nURGENT TICKETS\n")

        for ticket in sorted_tickets:

            if ticket["urgent"]:
                file.write(
                    f'{ticket["ticket"]} - '
                    f'{ticket["room"]} - '
                    f'{ticket["team"]}\n'
                )


# ------------------------------------------
# 14. MAIN PROGRAM
# ------------------------------------------

def main():

    print("\nHOSTEL FACILITIES MANAGEMENT SYSTEM")
    print("------------------------------------")

    try:

        load_open_tickets()

        results = []
        needs_info = []

        filename = BASE_DIR / "complaints.csv"

        with open(
            filename,
            "r",
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                print(
                    "\nProcessing:",
                    row["id"],
                    row["complaint"]
                )

                result = process_complaint(row)

                results.append(result)

                if result["status"] == "needs more info":

                    needs_info.append(row)

                print("Result:", result["status"])
                print("Ticket:", result["ticket"])

        write_reports(results, needs_info)

        print("\n------------------------------------")
        print("PROCESSING COMPLETED")
        print("Total complaints:", len(results))
        print("Total tickets:", len(tickets))
        print("Needs more information:", len(needs_info))

        print("\nFour reports created inside outputs/")

    except FileNotFoundError as error:

        print("File not found:", error)

    except Exception as error:

        print("Unexpected error:", error)


if __name__ == "__main__":
    main()
