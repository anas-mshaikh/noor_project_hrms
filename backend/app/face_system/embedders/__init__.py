"""
embedders package

Embedders should implement FaceEmbedder from base.py.
"""

from app.face_system.embedders.base import FaceEmbedder
from app.face_system.embedders.insightface_arcface import ONNXArcFaceEmbedder

__all__ = ["FaceEmbedder", "ONNXArcFaceEmbedder"]

