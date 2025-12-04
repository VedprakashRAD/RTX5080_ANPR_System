"""
API Package
Contains all API endpoints
"""

from .license_plate import router as license_plate_router

__all__ = ['license_plate_router']
