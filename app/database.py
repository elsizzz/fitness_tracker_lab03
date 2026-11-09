import os
from typing import List, Dict
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from app.models import Base, WorkoutRecordORM, WorkoutEntry
from app.exceptions import DatabaseOperationError, WorkoutNotFoundError


class DatabaseManager:
    """
    Класс управления хранилищем данных (PostgreSQL в Docker / SQLite fallback).
    """
    DEFAULT_POSTGRES_URL = "postgresql+psycopg2://fitness_user:fitness_password@localhost:5432/fitness_db"

    def __init__(self, db_url: str | None = None, allow_sqlite_fallback: bool = True):
        target_url = db_url or os.getenv("DATABASE_URL", self.DEFAULT_POSTGRES_URL)
        self.active_url = target_url

        try:
            self.engine = self._build_engine(target_url)
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        except Exception as e:
            if allow_sqlite_fallback and db_url is None:
                # Автоматический откат на локальную SQLite, если контейнер Docker еще не запущен
                self.active_url = "sqlite:///fitness_local_fallback.db"
                self.engine = self._build_engine(self.active_url)
                Base.metadata.create_all(self.engine)
                self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
            else:
                raise DatabaseOperationError(str(e))

    @staticmethod
    def _build_engine(url: str):
        """Создает движок SQLAlchemy с учетом особенностей SQLite в памяти и потоков FastAPI."""
        if url.startswith("sqlite"):
            if ":memory:" in url:
                return create_engine(
                    url,
                    echo=False,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            return create_engine(
                url,
                echo=False,
                connect_args={"check_same_thread": False},
            )
        return create_engine(url, echo=False, pool_pre_ping=True)

    def add_workout(self, entry: WorkoutEntry) -> WorkoutEntry:
        """Сохраняет новую тренировку в БД."""
        entry.validate()
        try:
            with self.SessionLocal() as session:
                orm_obj = WorkoutRecordORM(
                    workout_date=entry.workout_date,
                    workout_type=entry.workout_type,
                    duration_minutes=entry.duration_minutes,
                    calories_burned=entry.calories_burned,
                    notes=entry.notes,
                )
                session.add(orm_obj)
                session.commit()
                session.refresh(orm_obj)
                entry.id = orm_obj.id
                return entry
        except SQLAlchemyError as e:
            raise DatabaseOperationError(str(e))

    def get_all_workouts(self) -> List[WorkoutEntry]:
        """Возвращает список всех тренировок, отсортированных по дате и ID."""
        try:
            with self.SessionLocal() as session:
                records = (
                    session.query(WorkoutRecordORM)
                    .order_by(WorkoutRecordORM.workout_date.asc(), WorkoutRecordORM.id.asc())
                    .all()
                )
                return [
                    WorkoutEntry(
                        workout_id=r.id,
                        workout_date=r.workout_date,
                        workout_type=r.workout_type,
                        duration_minutes=r.duration_minutes,
                        calories_burned=r.calories_burned,
                        notes=r.notes or "",
                    )
                    for r in records
                ]
        except SQLAlchemyError as e:
            raise DatabaseOperationError(str(e))

    def delete_workout(self, workout_id: int) -> None:
        """Удаляет тренировку по её ID."""
        try:
            with self.SessionLocal() as session:
                record = session.query(WorkoutRecordORM).filter_by(id=workout_id).first()
                if not record:
                    raise WorkoutNotFoundError(workout_id)
                session.delete(record)
                session.commit()
        except WorkoutNotFoundError:
            raise
        except SQLAlchemyError as e:
            raise DatabaseOperationError(str(e))

    def clear_all(self) -> int:
        """Очищает все записи в таблице и возвращает количество удаленных строк."""
        try:
            with self.SessionLocal() as session:
                deleted_count = session.query(WorkoutRecordORM).delete()
                session.commit()
                return deleted_count
        except SQLAlchemyError as e:
            raise DatabaseOperationError(str(e))

    def get_activity_by_date(self) -> Dict[str, Dict[str, int]]:
        """
        Агрегирует статистику по датам для построения графика активности.
        Возвращает словарь: {'YYYY-MM-DD': {'calories': X, 'duration': Y}}
        """
        try:
            with self.SessionLocal() as session:
                rows = (
                    session.query(
                        WorkoutRecordORM.workout_date,
                        func.sum(WorkoutRecordORM.calories_burned).label("total_calories"),
                        func.sum(WorkoutRecordORM.duration_minutes).label("total_duration"),
                    )
                    .group_by(WorkoutRecordORM.workout_date)
                    .order_by(WorkoutRecordORM.workout_date.asc())
                    .all()
                )
                return {
                    row.workout_date: {
                        "calories": int(row.total_calories or 0),
                        "duration": int(row.total_duration or 0),
                    }
                    for row in rows
                }
        except SQLAlchemyError as e:
            raise DatabaseOperationError(str(e))

    def get_summary_stats(self) -> Dict[str, float | int]:
        """Возвращает общую сводную статистику по всем тренировкам."""
        workouts = self.get_all_workouts()
        total_count = len(workouts)
        total_duration = sum(w.duration_minutes for w in workouts)
        total_calories = sum(w.calories_burned for w in workouts)
        avg_intensity = round(total_calories / total_duration, 2) if total_duration > 0 else 0.0
        return {
            "total_workouts": total_count,
            "total_duration": total_duration,
            "total_calories": total_calories,
            "avg_intensity": avg_intensity,
        }