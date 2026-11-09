from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

from app.exceptions import (
    InvalidWorkoutTypeError,
    InvalidDurationError,
    InvalidCaloriesError,
    InvalidDateError,
)

Base = declarative_base()


class WorkoutRecordORM(Base):
    """ORM-модель таблицы тренировок для SQLAlchemy."""
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workout_date = Column(String(10), nullable=False, index=True)
    workout_type = Column(String(100), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    calories_burned = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True, default="")


class WorkoutEntry:
    """
    Доменный класс тренировки с инкапсуляцией бизнес-логики и валидации.
    """
    def __init__(
        self,
        workout_date: str,
        workout_type: str,
        duration_minutes: int,
        calories_burned: int,
        notes: str = "",
        workout_id: Optional[int] = None,
    ):
        self.id = workout_id
        self.workout_date = str(workout_date).strip()
        self.workout_type = str(workout_type).strip()
        self.duration_minutes = duration_minutes
        self.calories_burned = calories_burned
        self.notes = str(notes).strip()

        self.validate()

    def validate(self) -> None:
        """Проверяет корректность полей и выбрасывает собственные исключения."""
        if not self.workout_type or len(self.workout_type) < 2:
            raise InvalidWorkoutTypeError(self.workout_type)

        try:
            datetime.strptime(self.workout_date, "%Y-%m-%d")
        except ValueError:
            raise InvalidDateError(self.workout_date)

        if not isinstance(self.duration_minutes, int) or not (1 <= self.duration_minutes <= 1440):
            raise InvalidDurationError(self.duration_minutes)

        if not isinstance(self.calories_burned, int) or not (1 <= self.calories_burned <= 20000):
            raise InvalidCaloriesError(self.calories_burned)

    @property
    def intensity(self) -> float:
        """Расчет темпа расхода энергии (ккал в минуту)."""
        return round(self.calories_burned / self.duration_minutes, 2)

    def to_dict(self) -> dict:
        """Преобразование объекта в словарь для сериализации."""
        return {
            "id": self.id,
            "workout_date": self.workout_date,
            "workout_type": self.workout_type,
            "duration_minutes": self.duration_minutes,
            "calories_burned": self.calories_burned,
            "intensity": self.intensity,
            "notes": self.notes,
        }