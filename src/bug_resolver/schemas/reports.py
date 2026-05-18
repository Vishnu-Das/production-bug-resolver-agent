from pathlib import Path

from pydantic import BaseModel, Field


class ReportSaveResult(BaseModel):
    incident_id: str = Field(..., description="Incident id for which the report was saved")
    markdown_path: Path = Field(..., description="Path to the saved Markdown RCA report")
    json_path: Path = Field(..., description="Path to the saved JSON RCA report")
    report_dir: Path = Field(..., description="Directory where report files were saved")