class TCGPlayerSDKException(Exception):
    def __init__(self, response):
        self.response = response
        try:
            self.error = response.json()
        except:
            self.error = None

    def __str__(self):
        if self.error is None:
            return self.response.text
        else:
            return self.error.get('messageDetail', str(self.error))

    def __repr__(self):
        return repr(self.response)