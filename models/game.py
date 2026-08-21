class Game():
    def __init__(self, game_id, answer, status='in progress'):
        self.game_id = game_id
        self.answer = answer
        self.status = status
        self.rounds = []

    def get_game_object(self, get_answer=False):
        game = {
            "id": self.game_id,
            "status": self.status,
            "rounds": self.rounds
        }

        if get_answer:
            game["answer"] = self.answer

        return game