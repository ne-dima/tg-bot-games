import random
import time
import json
import os
from typing import Dict, Optional, Set, Tuple
from games.words import WORDS


class CrocodileGame:
    """Игра Крокодил - ведущий объясняет слово, остальные отгадывают"""
    
    SCORES_FILE = 'scores.json'
    
    def __init__(self):
        self.active_games: Dict[int, Dict] = {}  # chat_id -> game_state
        self.scores: Dict[int, Dict[int, int]] = {}  # chat_id -> {user_id -> score}
        self.load_scores()
    
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
    
    def _normalize_word(self, word: str) -> str:
        """Нормализует слово для сравнения - убирает знаки препинания, делает lowercase"""
        import re
        # Приводим к нижнему регистру, убираем знаки препинания и лишние пробелы
        normalized = re.sub(r'[^\w\s]', '', word.lower())
        return ' '.join(normalized.split())  # Убираем лишние пробелы
    
    def set_host(self, chat_id: int, user_id: int) -> Optional[str]:
        """Устанавливает ведущего и дает ему новое слово"""
        if not self.is_game_active(chat_id):
            return None
        
        word = random.choice(WORDS)
        self.active_games[chat_id]['host_user_id'] = user_id
        self.active_games[chat_id]['current_word'] = word
        self.active_games[chat_id]['word_lower'] = self._normalize_word(word)
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
        
        # Нормализуем отгадку для сравнения
        guess_normalized = self._normalize_word(guess)
        word_normalized = game['word_lower']
        
        # Проверяем отгадку (точное совпадение)
        if guess_normalized == word_normalized:
            game['guessed'] = True
            game['guesser_user_id'] = user_id
            # Начисляем очко за правильную отгадку
            self.add_score(chat_id, user_id, 1)
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
    
    def add_score(self, chat_id: int, user_id: int, points: int = 1):
        """Начисляет очки игроку"""
        if chat_id not in self.scores:
            self.scores[chat_id] = {}
        if user_id not in self.scores[chat_id]:
            self.scores[chat_id][user_id] = 0
        self.scores[chat_id][user_id] += points
        self.save_scores()
    
    def get_score(self, chat_id: int, user_id: int) -> int:
        """Возвращает количество очков игрока в чате"""
        if chat_id not in self.scores:
            return 0
        return self.scores[chat_id].get(user_id, 0)
    
    def get_all_scores(self, chat_id: int) -> Dict[int, int]:
        """Возвращает все очки в чате"""
        return self.scores.get(chat_id, {}).copy()
    
    def reset_scores(self, chat_id: int):
        """Сбрасывает все очки в чате"""
        if chat_id in self.scores:
            del self.scores[chat_id]
            self.save_scores()
    
    def save_scores(self):
        """Сохраняет статистику очков в файл"""
        try:
            # Конвертируем ключи в строки для JSON
            scores_to_save = {}
            for chat_id, users in self.scores.items():
                scores_to_save[str(chat_id)] = {str(user_id): score for user_id, score in users.items()}
            
            with open(self.SCORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(scores_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Логируем ошибку, но не падаем
            print(f"Ошибка при сохранении статистики: {e}")
    
    def load_scores(self):
        """Загружает статистику очков из файла"""
        if not os.path.exists(self.SCORES_FILE):
            return
        
        try:
            with open(self.SCORES_FILE, 'r', encoding='utf-8') as f:
                scores_data = json.load(f)
            
            # Конвертируем строковые ключи обратно в int
            self.scores = {}
            for chat_id_str, users in scores_data.items():
                chat_id = int(chat_id_str)
                self.scores[chat_id] = {int(user_id_str): score for user_id_str, score in users.items()}
        except Exception as e:
            # Если файл поврежден, начинаем с пустой статистики
            print(f"Ошибка при загрузке статистики: {e}")
            self.scores = {}

