from __future__ import annotations

from datetime import date


REPORT_FIXTURES: dict[str, list[dict[str, str]]] = {
    "prothetic1": [
        {"prosthesis_id": "BP-1001", "motion_profile": "precision-grip", "battery_cycles": "18"},
        {"prosthesis_id": "BP-1002", "motion_profile": "pinch", "battery_cycles": "12"},
    ],
    "prothetic2": [
        {"prosthesis_id": "BP-1003", "motion_profile": "power-grip", "battery_cycles": "21"},
    ],
    "prothetic3": [
        {"prosthesis_id": "BP-1004", "motion_profile": "wrist-flex", "battery_cycles": "16"},
    ],
    "john.doe": [
        {"prosthesis_id": "INT-2001", "motion_profile": "adaptive-grip", "battery_cycles": "14"},
    ],
    "alex.johnson": [
        {"prosthesis_id": "INT-2002", "motion_profile": "thumb-flex", "battery_cycles": "9"},
    ],
}


def render_report_csv(username: str, full_name: str | None) -> str:
    rows = REPORT_FIXTURES.get(
        username,
        [{"prosthesis_id": "BP-DEMO", "motion_profile": "demo-profile", "battery_cycles": "0"}],
    )
    header = "generated_at,patient,prosthesis_id,motion_profile,battery_cycles"
    content_rows = [
        ",".join(
            [
                date.today().isoformat(),
                full_name or username,
                row["prosthesis_id"],
                row["motion_profile"],
                row["battery_cycles"],
            ]
        )
        for row in rows
    ]
    return "\n".join([header, *content_rows])

