import json

class LexiCalendarManager():

    def __init__(self) -> None:
        self.events = [] 

    def update_calendar_with(self, events):
        # Append retrieved events
        for event in events:
            if event not in self.events:
                self.events.append(event)
        print (events)

    def get_calendar_data(self):
        # Return calendar info
        return json.dumps(self.events)
    
    def create_event(self):
        pass

    def update_event(self):
        pass