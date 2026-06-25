"""
model.py — Data blueprints for the ShiftIQ.

Job      — an income source (salary, hourly, gig, etc.)
Expense  — a recurring cost (rent, food, transport, etc.)

Both support a frequency field: Daily, Weekly, Biweekly, Monthly.
weekly_income() and weekly_amount() convert to a weekly number automatically
so the rest of the app always works in consistent weekly units.
"""

FREQ_TO_WEEKLY: dict[str, float] = {
    "Daily":    7.0,
    "Weekly":   1.0,
    "Biweekly": 0.5,
    "Monthly":  12 / 52,   # ≈ 0.2308
}

FREQUENCIES: list[str] = ["Daily", "Weekly", "Biweekly", "Monthly"]


class Job:
    """An income source — could be hourly, salaried, gig, freelance, etc."""

    def __init__(self, name: str, amount: float, frequency: str = "Weekly") -> None:
        self.name      = name
        self.amount    = amount       # amount earned per frequency period
        self.frequency = frequency    # Daily / Weekly / Biweekly / Monthly

    def weekly_income(self) -> float:
        """Convert the income amount to a weekly equivalent."""
        return self.amount * FREQ_TO_WEEKLY.get(self.frequency, 1.0)

    def to_dict(self) -> dict:
        return {"name": self.name, "amount": self.amount, "frequency": self.frequency}

    @staticmethod
    def from_dict(data: dict) -> "Job":
        return Job(data["name"], data["amount"], data.get("frequency", "Weekly"))

    def __repr__(self) -> str:
        return f"Job({self.name!r}, ${self.amount}/{self.frequency})"


class Expense:
    """A recurring expense — rent, groceries, subscriptions, etc."""

    def __init__(
        self,
        name:      str,
        amount:    float,
        category:  str,
        date:      str,
        frequency: str = "Monthly",
    ) -> None:
        self.name      = name
        self.amount    = amount       # amount paid per frequency period
        self.category  = category
        self.date      = date
        self.frequency = frequency    # Daily / Weekly / Biweekly / Monthly

    def weekly_amount(self) -> float:
        """Convert the expense amount to a weekly equivalent."""
        return self.amount * FREQ_TO_WEEKLY.get(self.frequency, 1.0)

    def to_dict(self) -> dict:
        return {
            "name":      self.name,
            "amount":    self.amount,
            "category":  self.category,
            "date":      self.date,
            "frequency": self.frequency,
        }

    @staticmethod
    def from_dict(data: dict) -> "Expense":
        return Expense(
            data["name"], data["amount"], data["category"],
            data["date"], data.get("frequency", "Monthly"),
        )

    def __repr__(self) -> str:
        return f"Expense({self.name!r}, ${self.amount}/{self.frequency}, {self.category!r})"
