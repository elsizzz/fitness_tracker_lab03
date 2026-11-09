from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from app.database import DatabaseManager
from app.models import WorkoutEntry
from app.exceptions import FitnessAppError, WorkoutNotFoundError


class WorkoutCreateSchema(BaseModel):
    workout_date: str
    workout_type: str
    duration_minutes: int
    calories_burned: int
    notes: Optional[str] = ""


def create_web_app(db_manager: Optional[DatabaseManager] = None) -> FastAPI:
    """Фабрика FastAPI-приложения с внедрением менеджера БД."""
    app = FastAPI(
        title="Fitness Tracker Web API & UI",
        description="Веб-версия системы учета фитнес-тренировок (Вариант 1, Well-done)",
        version="1.0.0",
    )
    db = db_manager or DatabaseManager()

    @app.get("/api/workouts")
    def api_get_workouts():
        workouts = db.get_all_workouts()
        return [w.to_dict() for w in workouts]

    @app.post("/api/workouts", status_code=status.HTTP_201_CREATED)
    def api_add_workout(payload: WorkoutCreateSchema):
        try:
            entry = WorkoutEntry(
                workout_date=payload.workout_date,
                workout_type=payload.workout_type,
                duration_minutes=payload.duration_minutes,
                calories_burned=payload.calories_burned,
                notes=payload.notes or "",
            )
            saved = db.add_workout(entry)
            return saved.to_dict()
        except FitnessAppError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    @app.delete("/api/workouts/{workout_id}")
    def api_delete_workout(workout_id: int):
        try:
            db.delete_workout(workout_id)
            return {"status": "deleted", "id": workout_id}
        except WorkoutNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        except FitnessAppError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    @app.get("/api/stats")
    def api_get_stats():
        return db.get_summary_stats()

    @app.get("/api/activity")
    def api_get_activity():
        return db.get_activity_by_date()

    @app.get("/", response_class=HTMLResponse)
    def index_page():
        return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Система учета фитнес-тренировок — Web</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-top: 0; color: #0f172a; }
        .stats-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: white; padding: 16px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-weight: 600; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 24px; }
        .form-row { margin-bottom: 12px; display: flex; flex-direction: column; }
        label { font-size: 14px; margin-bottom: 4px; font-weight: 600; }
        input, select { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; }
        button { background: #2563eb; color: white; border: none; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
        button.del-btn { background: #dc2626; padding: 5px 10px; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
        th, td { border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; }
        th { background: #f1f5f9; }
        #logBox { background: #0f172a; color: #e2e8f0; font-family: monospace; padding: 12px; border-radius: 8px; height: 130px; overflow-y: auto; font-size: 13px; }
    </style>
</head>
<body>
<div class="container">
    <h1>Система учета фитнес-тренировок (FastAPI Web-версия)</h1>
    <div class="stats-bar">
        <div class="stat-card" id="stWorkouts">Всего тренировок: 0</div>
        <div class="stat-card" id="stDuration">Общее время: 0 мин</div>
        <div class="stat-card" id="stCalories">Сожжено калорий: 0 ккал</div>
        <div class="stat-card" id="stIntensity">Интенсивность: 0 ккал/мин</div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Добавить тренировку</h3>
            <div class="form-row">
                <label>Дата (ГГГГ-ММ-ДД)</label>
                <input type="date" id="wDate">
            </div>
            <div class="form-row">
                <label>Тип тренировки</label>
                <input type="text" id="wType" value="Бег">
            </div>
            <div class="form-row">
                <label>Длительность (мин)</label>
                <input type="number" id="wDuration" placeholder="45">
            </div>
            <div class="form-row">
                <label>Калории (ккал)</label>
                <input type="number" id="wCalories" placeholder="400">
            </div>
            <div class="form-row">
                <label>Заметки</label>
                <input type="text" id="wNotes" placeholder="Комментарий к тренировке">
            </div>
            <button onclick="addWorkout()">Сохранить в БД</button>
        </div>

        <div class="card">
            <h3>График активности по дням</h3>
            <canvas id="activityChart" height="180"></canvas>
        </div>
    </div>

    <div class="card">
        <h3>Журнал тренировок</h3>
        <table>
            <thead>
                <tr><th>ID</th><th>Дата</th><th>Тип</th><th>Мин.</th><th>Ккал</th><th>Ккал/мин</th><th>Заметки</th><th>Действие</th></tr>
            </thead>
            <tbody id="workoutTable"></tbody>
        </table>
    </div>

    <div class="card">
        <h3>Лог активности</h3>
        <div id="logBox"></div>
    </div>
</div>

<script>
    document.getElementById('wDate').valueAsDate = new Date();
    let chartInstance = null;

    function writeLog(msg, isError=false) {
        const box = document.getElementById('logBox');
        const time = new Date().toLocaleTimeString();
        const color = isError ? '#f87171' : '#38bdf8';
        box.innerHTML += `<div style="color:${color}">[${time}] ${msg}</div>`;
        box.scrollTop = box.scrollHeight;
    }

    async function loadAll() {
        const [wRes, sRes, aRes] = await Promise.all([
            fetch('/api/workouts'), fetch('/api/stats'), fetch('/api/activity')
        ]);
        const workouts = await wRes.json();
        const stats = await sRes.json();
        const activity = await aRes.json();

        document.getElementById('stWorkouts').innerText = `Всего тренировок: ${stats.total_workouts}`;
        document.getElementById('stDuration').innerText = `Общее время: ${stats.total_duration} мин`;
        document.getElementById('stCalories').innerText = `Сожжено калорий: ${stats.total_calories} ккал`;
        document.getElementById('stIntensity').innerText = `Интенсивность: ${stats.avg_intensity} ккал/мин`;

        const tbody = document.getElementById('workoutTable');
        tbody.innerHTML = '';
        workouts.forEach(w => {
            tbody.innerHTML += `<tr>
                <td>${w.id}</td><td>${w.workout_date}</td><td>${w.workout_type}</td>
                <td>${w.duration_minutes}</td><td>${w.calories_burned}</td><td>${w.intensity}</td>
                <td>${w.notes}</td>
                <td><button class="del-btn" onclick="deleteWorkout(${w.id})">Удалить</button></td>
            </tr>`;
        });

        const labels = Object.keys(activity);
        const cals = labels.map(d => activity[d].calories);
        const durs = labels.map(d => activity[d].duration);

        if (chartInstance) chartInstance.destroy();
        const ctx = document.getElementById('activityChart').getContext('2d');
        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Калории (ккал)', data: cals, backgroundColor: '#2563eb' },
                    { label: 'Длительность (мин)', data: durs, backgroundColor: '#10b981' }
                ]
            }
        });
    }

    async function addWorkout() {
        const payload = {
            workout_date: document.getElementById('wDate').value,
            workout_type: document.getElementById('wType').value,
            duration_minutes: parseInt(document.getElementById('wDuration').value || '0'),
            calories_burned: parseInt(document.getElementById('wCalories').value || '0'),
            notes: document.getElementById('wNotes').value
        };
        const res = await fetch('/api/workouts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            writeLog(`Ошибка: ${data.detail}`, true);
        } else {
            writeLog(`Добавлена тренировка ID=${data.id} (${data.workout_type}, ${data.calories_burned} ккал)`);
            loadAll();
        }
    }

    async function deleteWorkout(id) {
        const res = await fetch(`/api/workouts/${id}`, { method: 'DELETE' });
        if (res.ok) {
            writeLog(`Удалена тренировка ID=${id}`);
            loadAll();
        }
    }

    writeLog('Веб-интерфейс инициализирован. Загрузка данных из БД...');
    loadAll();
</script>
</body>
</html>
        """

    return app


app = create_web_app()