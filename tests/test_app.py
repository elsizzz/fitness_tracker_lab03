import pytest
from fastapi.testclient import TestClient

from app.models import WorkoutEntry
from app.database import DatabaseManager
from app.web import create_web_app
from app.exceptions import (
    InvalidWorkoutTypeError,
    InvalidDurationError,
    InvalidCaloriesError,
    InvalidDateError,
    WorkoutNotFoundError,
)


@pytest.fixture
def memory_db() -> DatabaseManager:
    """Фикстура изолированной in-memory БД для быстрых и воспроизводимых тестов."""
    return DatabaseManager(db_url="sqlite:///:memory:", allow_sqlite_fallback=False)


@pytest.fixture
def web_client(memory_db: DatabaseManager) -> TestClient:
    """Фикстура тестового HTTP-клиента FastAPI."""
    fastapi_app = create_web_app(db_manager=memory_db)
    return TestClient(fastapi_app)


# --- 1. Тесты модели и собственных исключений ---

def test_valid_workout_entry_creation():
    entry = WorkoutEntry(
        workout_date="2026-11-09",
        workout_type="Бег",
        duration_minutes=50,
        calories_burned=500,
        notes="Интервальный бег",
    )
    assert entry.workout_type == "Бег"
    assert entry.intensity == 10.0


def test_invalid_workout_type_raises_custom_exception():
    with pytest.raises(InvalidWorkoutTypeError):
        WorkoutEntry("2026-11-09", " ", 45, 300)


def test_invalid_date_raises_custom_exception():
    with pytest.raises(InvalidDateError):
        WorkoutEntry("09-11-2026", "Плавание", 45, 300)


@pytest.mark.parametrize("bad_duration", [0, -15, 2000])
def test_invalid_duration_raises_custom_exception(bad_duration: int):
    with pytest.raises(InvalidDurationError):
        WorkoutEntry("2026-11-09", "Бокс", bad_duration, 400)


@pytest.mark.parametrize("bad_calories", [0, -100, 25000])
def test_invalid_calories_raises_custom_exception(bad_calories: int):
    with pytest.raises(InvalidCaloriesError):
        WorkoutEntry("2026-11-09", "Бокс", 60, bad_calories)


# --- 2. Тесты работы с базой данных ---

def test_add_and_fetch_workouts(memory_db: DatabaseManager):
    w1 = WorkoutEntry("2026-11-08", "Силовая", 60, 480, "База")
    w2 = WorkoutEntry("2026-11-09", "Кардио", 30, 300, "Дорожка")

    saved1 = memory_db.add_workout(w1)
    saved2 = memory_db.add_workout(w2)

    assert saved1.id is not None
    assert saved2.id is not None

    all_items = memory_db.get_all_workouts()
    assert len(all_items) == 2
    assert all_items[0].workout_type == "Силовая"
    assert all_items[1].workout_type == "Кардио"


def test_activity_aggregation_and_summary_stats(memory_db: DatabaseManager):
    memory_db.add_workout(WorkoutEntry("2026-11-09", "Бег", 30, 300))
    memory_db.add_workout(WorkoutEntry("2026-11-09", "Растяжка", 20, 100))

    activity = memory_db.get_activity_by_date()
    assert "2026-11-09" in activity
    assert activity["2026-11-09"]["calories"] == 400
    assert activity["2026-11-09"]["duration"] == 50

    stats = memory_db.get_summary_stats()
    assert stats["total_workouts"] == 2
    assert stats["total_duration"] == 50
    assert stats["total_calories"] == 400
    assert stats["avg_intensity"] == 8.0


def test_delete_workout_and_not_found_exception(memory_db: DatabaseManager):
    saved = memory_db.add_workout(WorkoutEntry("2026-11-09", "Плавание", 45, 450))
    memory_db.delete_workout(saved.id)
    assert len(memory_db.get_all_workouts()) == 0

    with pytest.raises(WorkoutNotFoundError):
        memory_db.delete_workout(9999)


# --- 3. Тесты веб-приложения FastAPI (Well-done) ---

def test_web_api_lifecycle(web_client: TestClient):
    # Создание записи через POST /api/workouts
    response = web_client.post(
        "/api/workouts",
        json={
            "workout_date": "2026-11-09",
            "workout_type": "Кроссфит",
            "duration_minutes": 50,
            "calories_burned": 600,
            "notes": "WOD",
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["workout_type"] == "Кроссфит"
    assert created["intensity"] == 12.0

    # Проверка получения списка
    list_res = web_client.get("/api/workouts")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # Проверка ошибки валидации через API
    bad_res = web_client.post(
        "/api/workouts",
        json={
            "workout_date": "2026-11-09",
            "workout_type": "Кроссфит",
            "duration_minutes": -10,
            "calories_burned": 600,
        },
    )
    assert bad_res.status_code == 400

    # Удаление через DELETE /api/workouts/{id}
    del_res = web_client.delete(f"/api/workouts/{created['id']}")
    assert del_res.status_code == 200