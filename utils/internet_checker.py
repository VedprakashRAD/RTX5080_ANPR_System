import urllib.request

def check_internet_connection():
    """
    Check if internet connection is available
    Returns:
        bool: True if internet is available, False otherwise
    """
    try:
        # Try to open a URL
        urllib.request.urlopen('http://google.com', timeout=3)
        return True
    except:
        pass
    
    return False