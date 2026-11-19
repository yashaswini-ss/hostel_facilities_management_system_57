
# Hostel Facilities Complaint Management System

## Project Overview

This is a Python-based hostel facilities complaint
management system.

It uses an LLM to classify student complaints and
automatically generates maintenance work orders.

## Features

- LLM complaint classification
- Room number validation
- Urgency detection
- Electrical safety net
- Automatic team assignment
- Duplicate complaint detection
- Automatic due date calculation
- CSV report generation
- Human review by hostel warden

## Technologies Used

- Python
- OpenAI API
- CSV
- JSON
- datetime
- Git and GitHub

## Installation

1. Install Python.
2. Clone this repository.
3. Install dependencies:

pip install -r requirements.txt

4. Create a .env file.

Add:

OPENAI_API_KEY=your_api_key

5. Run the program:

python main.py

## Testing

Run:

python -m unittest test_system.py -v

The testing file contains five evaluation cases
and three red-team tests.

## Input Files

- complaints.csv
- open_tickets.csv

## Output Files

- outputs/work_orders.csv
- outputs/results.csv
- outputs/needs_info.csv
- outputs/summary.txt

## Human Oversight

The system does not close tickets.

The warden reviews urgent tickets, assigns work
and closes all maintenance tasks.

## Security

API keys are stored in .env.
The .gitignore file prevents accidental upload
of the API key.

## Author

Yashaswini S.S

## Project

Individual Assessment 5
Week 15 Showcase


## Project Workflow

1. Read student complaints from complaints.csv.
2. Send each complaint to the LLM.
3. Extract room, issue, urgency and summary.
4. Validate room numbers using Python.
5. Apply the safety net for urgent complaints.
6. Assign the correct maintenance team.
7. Detect duplicate complaints.
8. Calculate ticket due dates.
9. Generate four output reports.

## Error Handling

If the API is unavailable or returns invalid JSON,
the system uses a fallback classification.

Invalid room numbers are sent to needs_info.csv.

## Ticket Management

Repeated complaints are joined to existing tickets.
The warden is responsible for assigning and closing work.

