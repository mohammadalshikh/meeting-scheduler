from models.game import Game

class GameService:

    def __init__(self):
        self.games = {}

    def create_game(self, answer):
        game_id = str(len(self.games) + 1)
        new_game = Game(game_id, answer)
        self.games[game_id] = new_game
        return game_id
    
    def get_game(self, id, get_answer=False):
        if id in self.games:
            game = self.games[id]
            is_finished = (game.status == "finished")
            is_finished = is_finished or get_answer
            return self.games[id].get_game_object(get_answer=is_finished)
        return None

    def get_all_games(self):
        result = {}
        for id, game in self.games.items():
            is_finished = (game.status == "finished")
            result[id] = game.get_game_object(get_answer=is_finished)

        return result

    #mehrin

    def calculate_result(self, answer, user_guess):
        exact = 0
        partial = 0
        
        answer = str(answer)
        user_guess = str(user_guess)
        
        for  position in range(len(answer)):
            if user_guess[position] == answer[position]:
                exact += 1
            elif user_guess[position] in answer:
                partial += 1
        
        return f"e:{exact}:p:{partial}"

    def add_guess(self, id, guess):
        if id in self.games:
            print(self.games[id])
            self.games[id].rounds.append(guess)