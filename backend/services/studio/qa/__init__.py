"""Shadow quality checks that run after a render.

They write a report and never change the export, the job status, or the file.
"""
from backend.services.studio.qa.record import record_after_render

__all__ = ['record_after_render']
