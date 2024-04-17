class VisibleConstell():

    def __init__(self, db_info, az, alt):
        self.db_info = db_info
        self.az = az
        self.alt = alt
    
    def __repr__(self):
        return self.db_info['name']