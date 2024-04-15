class Capture:
    def __init__(self, last_cap_time, cap_amount, is_captured):
        self.last_cap_time = last_cap_time
        self.cap_amount = cap_amount
        self.is_captured = is_captured

    def to_string(self):
        return f'last_cap_time: {self.last_cap_time}, ' \
               f'cap_amount: {self.cap_amount}, is_captured: {self.is_captured}'
