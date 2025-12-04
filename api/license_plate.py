"""
Clean ANPR API Endpoint
Uses EnhancedVisionService for license plate extraction
"""

from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import os
import time
from datetime import datetime
import tempfile

# Import services
from services.enhanced_vision_service import EnhancedVisionService

# Create router
router = APIRouter()

# Response Models
class VehicleMetadata(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    type: Optional[str] = None

class LicensePlateResponse(BaseModel):
    success: bool
    plate: Optional[str] = None
    vehicle: Optional[VehicleMetadata] = None
    confidence: float = 0.0
    camera_id: Optional[str] = None
    timestamp: str
    processing_time_ms: int
    error: Optional[str] = None

# Initialize vision service
vision_service = EnhancedVisionService()

@router.post("/extract-license-plate", response_model=LicensePlateResponse)
async def extract_license_plate(
    image: UploadFile = File(...),
    camera_id: str = Form(default="UNKNOWN")
):
    """
    Extract license plate and vehicle metadata from image
    
    Args:
        image: Vehicle image file
        camera_id: Camera identifier (e.g., "RAHQ-G1-OUT-02")
    
    Returns:
        JSON with plate, vehicle metadata, camera_id, timestamp
    """
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    
    try:
        # Read image content
        image_content = await image.read()
        
        # Save image with camera_id and timestamp
        os.makedirs('saved_images', exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_filename = f"{camera_id}_{timestamp_str}.jpg"
        image_path = os.path.join('saved_images', image_filename)
        
        # Write image to disk
        with open(image_path, 'wb') as f:
            f.write(image_content)
        
        print(f"✅ Image saved: {image_path}")
        
        # Extract plate and vehicle metadata using EnhancedVisionService
        result = vision_service.extract_vehicle_metadata(image_path)
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Check if extraction was successful
        if result.get('success'):
            # Extract plate (can be null for rear view)
            plate = result.get('plate')
            if plate and plate not in ['UNKNOWN', 'NOT_FOUND', 'ERROR']:
                # Clean plate number
                import re
                plate = re.sub(r'[^A-Z0-9]', '', str(plate).upper())
            else:
                plate = None  # Rear view or plate not visible
            
            # Extract vehicle metadata
            vehicle_data = result.get('vehicle', {})
            vehicle = VehicleMetadata(
                make=vehicle_data.get('make') if vehicle_data.get('make') != 'UNKNOWN' else None,
                model=vehicle_data.get('model') if vehicle_data.get('model') != 'UNKNOWN' else None,
                color=vehicle_data.get('color') if vehicle_data.get('color') != 'UNKNOWN' else None,
                type=vehicle_data.get('type') if vehicle_data.get('type') != 'UNKNOWN' else None
            )
            
            # Check if vehicle was detected
            if not any([vehicle.make, vehicle.model, vehicle.color, vehicle.type]):
                # No vehicle detected
                return LicensePlateResponse(
                    success=False,
                    plate=None,
                    vehicle=None,
                    confidence=0.0,
                    camera_id=camera_id,
                    timestamp=timestamp,
                    processing_time_ms=processing_time_ms,
                    error="No vehicle detected in image"
                )
            
            # Success - return plate (or null) + vehicle metadata
            confidence = result.get('confidence', 0.0)
            
            print(f"✅ Extraction successful: plate={plate}, vehicle={vehicle.make} {vehicle.model}")
            
            return LicensePlateResponse(
                success=True,
                plate=plate,  # Can be null for rear view
                vehicle=vehicle,
                confidence=confidence,
                camera_id=camera_id,
                timestamp=timestamp,
                processing_time_ms=processing_time_ms,
                error=None
            )
        else:
            # Vision service failed
            return LicensePlateResponse(
                success=False,
                plate=None,
                vehicle=None,
                confidence=0.0,
                camera_id=camera_id,
                timestamp=timestamp,
                processing_time_ms=processing_time_ms,
                error=result.get('error', 'Failed to process image')
            )
    
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        print(f"❌ API Error: {str(e)}")
        
        return LicensePlateResponse(
            success=False,
            plate=None,
            vehicle=None,
            confidence=0.0,
            camera_id=camera_id,
            timestamp=timestamp,
            processing_time_ms=processing_time_ms,
            error=str(e)
        )
