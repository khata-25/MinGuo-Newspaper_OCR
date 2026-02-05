from layout.base import LayoutRegion

class PPStructureLayoutDetector:
    def __init__(self, config):
        pass
    def is_available(self):
        return False
    def detect(self, image):
        return []

class SimpleFallbackDetector:
    def __init__(self, rows=3, cols=4):
        self.rows = rows
        self.cols = cols
    
    def detect(self, image):
        return []
