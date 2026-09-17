import random


class Event:
    def __init__(self, name, probability, min_impact, max_impact):
        self.name = name
        self.probability = probability
        self.min_impact = min_impact
        self.max_impact = max_impact

    def apply(self):
        if random.random() < self.probability:
            impact = round(random.uniform(self.min_impact, self.max_impact), 2)
            return impact, True
        return 0.0, False


class EventEngine:
    def __init__(self):
        self.events = [
            Event("Extra Shift",       probability=0.15, min_impact=50,   max_impact=200),
            Event("Missed Shift",      probability=0.10, min_impact=-200, max_impact=-50),
            Event("Emergency Expense", probability=0.08, min_impact=-500, max_impact=-100),
            Event("Bonus",             probability=0.05, min_impact=100,  max_impact=500),
            Event("Unexpected Fee",    probability=0.07, min_impact=-150, max_impact=-20),
        ]

    def apply_all_events(self):
        total_impact = 0.0
        triggered = []
        for event in self.events:
            impact, fired = event.apply()
            if fired:
                total_impact += impact
                triggered.append({"event": event.name, "impact": impact})
        return round(total_impact, 2), triggered
