"""Final-table analysis modules for EASE 2026."""

from ease2026.analysis.figures import FinalFigureGenerator
from ease2026.analysis.rq1 import Rq1Analyzer
from ease2026.analysis.rq2 import Rq2Analyzer
from ease2026.analysis.rq3 import Rq3Analyzer
from ease2026.analysis.rq3_inferential import Rq3InferentialAnalyzer

__all__ = [
    "FinalFigureGenerator",
    "Rq1Analyzer",
    "Rq2Analyzer",
    "Rq3Analyzer",
    "Rq3InferentialAnalyzer",
]
