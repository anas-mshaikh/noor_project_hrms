"""
aligners package

Aligners should implement FaceAligner from base.py.
"""

from app.face_system.aligners.base import FaceAligner
from app.face_system.aligners.opencv_lbf import OpenCVLBFFaceAligner

__all__ = ["FaceAligner", "OpenCVLBFFaceAligner"]

