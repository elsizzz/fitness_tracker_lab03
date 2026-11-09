class FitnessAppError(Exception):
    """Базовый класс для всех исключений приложения фитнес-трекера."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ValidationError(FitnessAppError):
    """Базовое исключение для ошибок валидации пользовательского ввода."""
    pass


class InvalidWorkoutTypeError(ValidationError):
    """Вызывается, если тип тренировки пустой или некорректный."""
    def __init__(self, workout_type: str = ""):
        super().__init__(f"Некорректный тип тренировки: '{workout_type}'. Поле не может быть пустым.")


class InvalidDurationError(ValidationError):
    """Вызывается, если длительность тренировки <= 0 или превышает разумный предел."""
    def __init__(self, duration: int):
        super().__init__(
            f"Некорректная длительность ({duration} мин.). Допустимый диапазон: от 1 до 1440 минут."
        )


class InvalidCaloriesError(ValidationError):
    """Вызывается, если количество сожженных калорий <= 0 или слишком велико."""
    def __init__(self, calories: int):
        super().__init__(
            f"Некорректное значение калорий ({calories} ккал). Допустимый диапазон: от 1 до 20000 ккал."
        )


class InvalidDateError(ValidationError):
    """Вызывается при неверном формате даты тренировки."""
    def __init__(self, date_str: str):
        super().__init__(
            f"Некорректный формат даты: '{date_str}'. Ожидается формат ГГГГ-ММ-ДД (например, 2026-11-09)."
        )


class DatabaseOperationError(FitnessAppError):
    """Вызывается при ошибках подключения или выполнения запросов к БД."""
    def __init__(self, details: str):
        super().__init__(f"Ошибка операции с базой данных: {details}")


class WorkoutNotFoundError(FitnessAppError):
    """Вызывается при попытке удалить или изменить несуществующую тренировку."""
    def __init__(self, workout_id: int):
        super().__init__(f"Тренировка с ID={workout_id} не найдена в базе данных.")