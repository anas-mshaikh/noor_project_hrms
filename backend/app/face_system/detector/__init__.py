"""
detector package

Face detectors should implement the FaceDetector interface from base.py.
"""

from app.face_system.detector.base import FaceDetection, FaceDetector
from app.face_system.detector.opencv_yn import OpenCVYNFaceDetector

__all__ = ["FaceDetection", "FaceDetector", "OpenCVYNFaceDetector"]

