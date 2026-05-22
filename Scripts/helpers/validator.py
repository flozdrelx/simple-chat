class Validate:
    def __init__(self, str):
        self.str = str

    def is_valid(self):
        if not self.str.strip():
            return False
        
        if ' ' in self.str:
            return False
        
        if not self.str.isprintable():
            return False

        return True