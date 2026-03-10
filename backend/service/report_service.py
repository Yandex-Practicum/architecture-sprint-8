from fastapi import HTTPException, status
from repository.report_repository import ReportRepository
from models.report_models import ReportItem, ReportResponse

class ReportService:
    def __init__(self):
        self.repository = ReportRepository()

    def get_report(self, user_id: str, from_date, to_date):
        max_date = self.repository.get_max_report_date()
        if to_date > max_date:
            to_date = max_date
        if max_date is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Report data not ready",
            )

        if to_date > max_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reports available only up to {max_date}",
            )

        rows = self.repository.load_report(user_id, from_date, to_date)
        print(rows)
        items = [
            ReportItem(
                report_date=row[0],
                prosthesis_id=row[1],
                total_active_sec=row[2],
                avg_reaction_ms=row[3],
                movements_count=row[4],
                errors_count=row[5],
                battery_avg_pct=row[6],
                crm_country=row[7],
                crm_segment=row[8],
                crm_tariff=row[9],
            )
            for row in rows
        ]

        return ReportResponse(
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            items=items,
        )