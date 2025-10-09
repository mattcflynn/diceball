class Player:
    def __init__(self, name, stats):
        self.name = name
        self.stats = stats

class Pitcher(Player):
    def __init__(self, name, stats, pitches):
        super().__init__(name, stats)
        self.pitches = pitches

class Hitter(Player):
    def __init__(self, name, stats):
        super().__init__(name, stats)
