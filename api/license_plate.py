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
from services.external_api_sync import ExternalAPISync
from services.image_cleanup import ImageCleanupService
from services.vehicle_tracking import VehicleTrackingService

# Create router
router = APIRouter()

# Initialize services
vision_service = EnhancedVisionService()
external_api = ExternalAPISync()
image_cleanup = ImageCleanupService()
vehicle_tracking = VehicleTrackingService()

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
    # Gate verification fields
    verification_required: bool = False
    verification_status: Optional[str] = None  # 'PENDING', 'VERIFIED', or None
    verification_score: Optional[float] = None
    event_id: Optional[str] = None

@router.post("/extract-license-plate", response_model=LicensePlateResponse)
async def extract_license_plate(
    image: UploadFile = File(...),
    camera_id: str = Form(default="UNKNOWN"),
    yolo_vehicle_class: str = Form(default=None),
    yolo_confidence: str = Form(default="0.0")
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
            
            # Use YOLO vehicle class as fallback if vision service returns None
            vehicle_type = vehicle_data.get('type') if vehicle_data.get('type') != 'UNKNOWN' else None
            if not vehicle_type and yolo_vehicle_class:
                # Map YOLO classes to vehicle types
                yolo_to_type = {
                    'car': 'CAR',
                    'motorcycle': 'BIKE',
                    'bus': 'BUS',
                    'truck': 'TRUCK'
                }
                vehicle_type = yolo_to_type.get(yolo_vehicle_class.lower(), yolo_vehicle_class.upper())
                print(f"ℹ️ Using YOLO fallback: {yolo_vehicle_class} → {vehicle_type}")
            
            vehicle = VehicleMetadata(
                make=vehicle_data.get('make') if vehicle_data.get('make') != 'UNKNOWN' else None,
                model=vehicle_data.get('model') if vehicle_data.get('model') != 'UNKNOWN' else None,
                color=vehicle_data.get('color') if vehicle_data.get('color') != 'UNKNOWN' else None,
                type=vehicle_type
            )
            
            # Check if vehicle was detected (only require type, other fields are optional)
            if not vehicle.type:
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
            
            print(f"✅ Extraction successful: plate={plate}, type={vehicle.type}, color={vehicle.color}")
            
            # Register with vehicle tracking service for gate verification
            verification_result = None
            verification_required = False
            verification_status = None
            verification_score = None
            event_id = None
            
            if vehicle_tracking:
                tracking_data = {
                    'plate': plate,
                    'type': vehicle.type,
                    'color': vehicle.color,
                    'confidence': confidence,
                    'image_path': image_path
                }
                
                # Register detection (will use gate verification if camera is paired)
                session = vehicle_tracking.register_detection(camera_id, tracking_data)
                
                if session:
                    # Check if verification was used
                    if hasattr(session, 'verification_status'):
                        verification_required = True
                        verification_status = session.verification_status
                        verification_score = getattr(session, 'verification_score', None)
                        event_id = session.vehicle_id
                        print(f"🔐 Gate verification: status={verification_status}, score={verification_score}")
                else:
                    # Detection is pending verification
                    verification_required = True
                    verification_status = 'PENDING'
                    print(f"⏳ Detection pending verification from paired camera")
            
            # Sync to external API (after successful extraction)
            if external_api.is_enabled():
                api_data = {
                    'camera_id': camera_id,
                    'plate': plate,
                    'vehicle': {
                        'type': vehicle.type,
                        'color': vehicle.color
                    },
                    'timestamp': timestamp,
                    'confidence': confidence,
                    'verification_status': verification_status,
                    'event_id': event_id
                }
                # Mark image for cleanup after successful upload
                if external_api.sync_vehicle_data(api_data, image_path):
                    image_cleanup.mark_image_as_uploaded(image_path)
            
            return LicensePlateResponse(
                success=True,
                plate=plate,  # Can be null for rear view
                vehicle=vehicle,
                confidence=confidence,
                camera_id=camera_id,
                timestamp=timestamp,
                processing_time_ms=processing_time_ms,
                error=None,
                verification_required=verification_required,
                verification_status=verification_status,
                verification_score=verification_score,
                event_id=event_id
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
