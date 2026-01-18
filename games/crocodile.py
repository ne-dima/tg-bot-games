import random
import time
from typing import Dict, Optional, Set, Tuple
from games.words import WORDS


class CrocodileGame:
    """Игра Крокодил - ведущий объясняет слово, остальные отгадывают"""
    
    def __init__(self):
        self.active_games: Dict[int, Dict] = {}  # chat_id -> game_state
    
    def start_game(self, chat_id: int) -> bool:
        """Начинает новую игру в чате"""
        if chat_id in self.active_games:
            return False  # Игра уже активна
        self.active_games[chat_id] = {
            'host_user_id': None,
            'current_word': None,
            'word_lower': None,
            'guessed': False,
            'guesser_user_id': None,
            'round_start_time': None,
            'timeout_seconds': 600  # 10 минут
        }
        return True
    
    def stop_game(self, chat_id: int):
        """Останавливает игру в чате"""
        if chat_id in self.active_games:
            del self.active_games[chat_id]
    
    def is_game_active(self, chat_id: int) -> bool:
        """Проверяет, активна ли игра в чате"""
        return chat_id in self.active_games
    
    def set_host(self, chat_id: int, user_id: int) -> Optional[str]:
        """Устанавливает ведущего и дает ему новое слово"""
        if not self.is_game_active(chat_id):
            return None
        
        word = random.choice(WORDS)
        self.active_games[chat_id]['host_user_id'] = user_id
        self.active_games[chat_id]['current_word'] = word
        self.active_games[chat_id]['word_lower'] = word.lower().strip()
        self.active_games[chat_id]['guessed'] = False
        self.active_games[chat_id]['guesser_user_id'] = None
        self.active_games[chat_id]['round_start_time'] = time.time()  # Засекаем время начала раунда
        
        return word
    
    def get_host_word(self, chat_id: int, user_id: int) -> Optional[str]:
        """Возвращает слово для ведущего"""
        if not self.is_game_active(chat_id):
            return None
        
        game = self.active_games[chat_id]
        if game['host_user_id'] == user_id:
            return game['current_word']
        return None
    
    def check_guess(self, chat_id: int, user_id: int, guess: str) -> Tuple[bool, bool]:
        """
        Проверяет отгадку
        Returns: (is_correct, is_host)
        """
        if not self.is_game_active(chat_id):
            return False, False
        
        game = self.active_games[chat_id]
        
        # Ведущий не может отгадывать
        if game['host_user_id'] == user_id:
            return False, True
        
        # Если уже отгадано
        if game['guessed']:
            return False, False
        
        # Проверяем отгадку
        guess_clean = guess.lower().strip()
        if guess_clean == game['word_lower']:
            game['guessed'] = True
            game['guesser_user_id'] = user_id
            return True, False
        
        return False, False
    
    def is_guessed(self, chat_id: int) -> bool:
        """Проверяет, отгадано ли слово"""
        if not self.is_game_active(chat_id):
            return False
        return self.active_games[chat_id]['guessed']
    
    def get_host(self, chat_id: int) -> Optional[int]:
        """Возвращает ID ведущего"""
        if not self.is_game_active(chat_id):
            return None
        return self.active_games[chat_id]['host_user_id']
    
    def get_guesser(self, chat_id: int) -> Optional[int]:
        """Возвращает ID того, кто отгадал"""
        if not self.is_game_active(chat_id):
            return None
        return self.active_games[chat_id]['guesser_user_id']
    
    def check_timeout(self, chat_id: int) -> bool:
        """Проверяет, истекло ли время для отгадывания (10 минут)"""
        if not self.is_game_active(chat_id):
            return False
        
        game = self.active_games[chat_id]
        
        # Если слово уже отгадано, таймер не истек
        if game.get('guessed', False):
            return False
        
        round_start = game.get('round_start_time')
        
        if round_start is None:
            return False  # Раунд еще не начат
        
        elapsed = time.time() - round_start
        return elapsed >= game['timeout_seconds']
    
    def get_remaining_time(self, chat_id: int) -> Optional[int]:
        """Возвращает оставшееся время в секундах, или None если раунд не начат"""
        if not self.is_game_active(chat_id):
            return None
        
        game = self.active_games[chat_id]
        round_start = game.get('round_start_time')
        
        if round_start is None:
            return None
        
        elapsed = time.time() - round_start
        remaining = game['timeout_seconds'] - elapsed
        return max(0, int(remaining))

