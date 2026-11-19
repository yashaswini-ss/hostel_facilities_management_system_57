
import unittest
from unittest.mock import patch

import main


class ComplaintTests(unittest.TestCase):
    def test_safety_net_water_near_switch(self):

        complaint = "Water overflowing near the electrical switch in C112"

        data = {
            "room": "C112",
            "issue": "plumbing",
            "urgent": False,
            "summary": "Water overflowing"
        }

        result = main.apply_safety_net(complaint, data)

        self.assertTrue(result["urgent"])
        self.assertEqual(result["issue"], "electrical")

        print("PASS: Water near electrical switch is urgent")

    def test_evaluation(self):

        test_cases = [
            {
                "complaint": "Fan not working in B214",
                "room": "B214",
                "issue": "electrical",
                "urgent": False
            },
            {
                "complaint": "Sparks from switchboard in A105",
                "room": "A105",
                "issue": "electrical",
                "urgent": True
            },
            {
                "complaint": "Water leaking from tap in C310",
                "room": "C310",
                "issue": "plumbing",
                "urgent": False
            },
            {
                "complaint": "Wifi not working in D115",
                "room": "D115",
                "issue": "internet",
                "urgent": False
            },
            {
                "complaint": "Broken study table in A210",
                "room": "A210",
                "issue": "carpentry",
                "urgent": False
            }
        ]

        print("\nEVALUATION RESULTS")

        for test in test_cases:

            result = main.classify(test["complaint"])

            room = main.check_room(
                test["complaint"],
                result["room"]
            )

            result = main.apply_safety_net(
                test["complaint"],
                result
            )

            passed = (
                room == test["room"]
                and result["issue"] == test["issue"]
                and result["urgent"] == test["urgent"]
            )

            print(
                test["complaint"],
                "EXPECTED:",
                test["room"],
                test["issue"],
                test["urgent"],
                "ACTUAL:",
                room,
                result["issue"],
                result["urgent"],
                "PASS" if passed else "FAIL"
            )

            self.assertTrue(passed)

    def test_red_team_urgent_shouting(self):

        complaint = "URGENT!!! Please dust room B110"

        result = {
            "room": "B110",
            "issue": "cleaning",
            "urgent": False,
            "summary": "Room needs dusting"
        }

        result = main.apply_safety_net(
            complaint, result
        )

        self.assertFalse(result["urgent"])

        print("PASS: Shouting does not create urgency")

    def test_red_team_invalid_room(self):

        complaint = "Fan broken in B225"

        room = main.check_room(
            complaint, "B225"
        )

        self.assertIsNone(room)

        print("PASS: Invalid room rejected")

    def test_red_team_duplicate_three_times(self):

        main.tickets.clear()
        main.ticket_lookup.clear()

        complaint_data = {
            "room": "B214",
            "issue": "electrical",
            "urgent": False,
            "summary": "Fan not working"
        }

        rows = [
            {
                "id": "R01",
                "date": "2026-10-10",
                "complaint": "Fan not working in B214"
            },
            {
                "id": "R02",
                "date": "2026-10-10",
                "complaint": "Fan not working in B214"
            },
            {
                "id": "R03",
                "date": "2026-10-10",
                "complaint": "Fan not working in B214"
            }
        ]

        with patch(
            "main.classify",
            return_value=complaint_data
        ):

            results = [
                main.process_complaint(row)
                for row in rows
            ]

        statuses = [
            result["status"]
            for result in results
        ]

        self.assertEqual(
            statuses,
            ["new ticket", "duplicate", "duplicate"]
        )

        self.assertEqual(len(main.tickets), 1)

        print("PASS: Three complaints joined into one ticket")


if __name__ == "__main__":

    unittest.main(verbosity=2)
