# Indian License Plate Codes
import re

state_codes = ["AP", "AR", "AS", "BR", "CG", "GA", "GJ", "HR", "HP", "JH", "KA", "KL", "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "PB", "RJ", "SK", "TN", "TS", "TR", "UP", "UK", "WB", "AN", "CH", "DN", "DL", "JK", "LA", "LD", "PY"]
bh_series = "BH"  # Bharat Series - National registration

def validate_license_plate(plate):
    """Validate Indian license plate format"""
    plate = plate.upper().replace(" ", "")
    
    # Standard format: AA00AA0000
    standard_pattern = r"^([A-Z]{2})(\d{2})([A-Z]{1,3})(\d{4})$"
    
    # BH Series format: YYBH####XX (YY=Year, BH=Bharat, ####=Random digits, XX=Random letters excluding I,O)
    bh_pattern = r"^(\d{2})(BH)(\d{4})([A-HJ-NP-Z]{2})$"
    
    if re.match(standard_pattern, plate):
        # Check if state code is valid
        state_code = plate[:2]
        if state_code in state_codes:
            return "standard"
        else:
            return "invalid_state"
    elif re.match(bh_pattern, plate):
        # Validate BH series: letters should exclude I and O
        letters = plate[-2:]
        if 'I' not in letters and 'O' not in letters:
            return "bh_series"
        else:
            return "invalid_bh_letters"
    else:
        return "invalid"

def format_license_plate(plate):
    """Format license plate with proper spacing"""
    plate = plate.upper().replace(" ", "")
    validation = validate_license_plate(plate)
    
    if validation == "standard":
        return f"{plate[:2]} {plate[2:4]} {plate[4:-4]} {plate[-4:]}"
    elif validation == "bh_series":
        # Format: YY BH #### XX
        return f"{plate[:2]} {plate[2:4]} {plate[4:8]} {plate[8:]}"
    elif validation == "invalid_state":
        return f"INVALID_STATE: {plate}"
    elif validation == "invalid_bh_letters":
        return f"INVALID_BH_LETTERS: {plate}"
    else:
        return f"INVALID: {plate}"