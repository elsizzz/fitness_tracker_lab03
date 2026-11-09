from datetime import datetime
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QMessageBox,
    QSplitter,
)
from PySide6.QtCharts import (
    QChart,
    QChartView,
    QBarSeries,
    QBarSet,
    QBarCategoryAxis,
    QValueAxis,
)

from app.database import DatabaseManager
from app.models import WorkoutEntry
from app.exceptions import FitnessAppError


class ActivityChartWidget(QWidget):
    """Виджет графика активности на базе QtCharts."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chart = QChart()
        self.chart.setTitle("График активности: сожженные калории и время по дням")
        self.chart.setAnimationOptions(QChart.SeriesAnimations)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.chart_view)

    def update_chart(self, activity_data: dict) -> None:
        """Перестраивает столбчатую диаграмму на основе данных из БД."""
        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        if not activity_data:
            self.chart.setTitle("График активности (нет данных для отображения)")
            return

        self.chart.setTitle("Динамика тренировок по датам")

        calories_set = QBarSet("Калории (ккал)")
        calories_set.setColor(QColor("#2563eb"))

        duration_set = QBarSet("Длительность (мин)")
        duration_set.setColor(QColor("#10b981"))

        dates = list(activity_data.keys())
        max_val = 100

        for d in dates:
            cals = activity_data[d]["calories"]
            dur = activity_data[d]["duration"]
            calories_set.append(cals)
            duration_set.append(dur)
            max_val = max(max_val, cals, dur)

        series = QBarSeries()
        series.append(calories_set)
        series.append(duration_set)
        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(dates)
        self.chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setRange(0, int(max_val * 1.15))
        axis_y.setTitleText("Значение")
        self.chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignBottom)


class MainWindow(QMainWindow):
    """Главное окно приложения 'Система учета фитнес-тренировок'."""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.setWindowTitle("Система учета фитнес-тренировок (Вариант 1 — Well-done)")
        self.resize(1180, 780)

        self._init_menu()
        self._init_ui()
        self.log_event(f"Приложение запущено. Подключена БД: {self.db.active_url}")
        self.refresh_all()

    def _init_menu(self) -> None:
        """Создание верхнего меню с выходом и сервисными действиями."""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Файл")

        seed_action = QAction("Загрузить демо-данные", self)
        seed_action.triggered.connect(self.load_demo_data)
        file_menu.addAction(seed_action)

        clear_action = QAction("Очистить все записи БД", self)
        clear_action.triggered.connect(self.clear_all_workouts)
        file_menu.addAction(clear_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("Справка")
        help_action = QAction("Инструкция по использованию", self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help_dialog)
        help_menu.addAction(help_action)

    def _init_ui(self) -> None:
        """Инициализация всех визуальных компонентов интерфейса."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. Верхняя панель заголовка и статистики (Labels)
        header_group = QGroupBox("Сводная статистика активности")
        header_layout = QHBoxLayout(header_group)

        bold_font = QFont()
        bold_font.setPointSize(10)
        bold_font.setBold(True)

        self.lbl_total_workouts = QLabel("Всего тренировок: 0")
        self.lbl_total_workouts.setFont(bold_font)

        self.lbl_total_duration = QLabel("Общее время: 0 мин.")
        self.lbl_total_duration.setFont(bold_font)

        self.lbl_total_calories = QLabel("Сожжено калорий: 0 ккал")
        self.lbl_total_calories.setFont(bold_font)

        self.lbl_avg_intensity = QLabel("Средняя интенсивность: 0.0 ккал/мин")
        self.lbl_avg_intensity.setFont(bold_font)

        self.lbl_db_status = QLabel()
        db_type = "PostgreSQL (Docker)" if "postgresql" in self.db.active_url else "SQLite (Локальная)"
        self.lbl_db_status.setText(f"СУБД: {db_type}")
        self.lbl_db_status.setStyleSheet("color: #059669; font-weight: bold;")

        header_layout.addWidget(self.lbl_total_workouts)
        header_layout.addWidget(self.lbl_total_duration)
        header_layout.addWidget(self.lbl_total_calories)
        header_layout.addWidget(self.lbl_avg_intensity)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_db_status)

        main_layout.addWidget(header_group)

        # 2. Центральная область: форма ввода + таблица слева, график справа
        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Блок ввода новых данных
        form_group = QGroupBox("Добавление новой тренировки")
        form_layout = QGridLayout(form_group)

        form_layout.addWidget(QLabel("Дата тренировки:"), 0, 0)
        self.input_date = QDateEdit()
        self.input_date.setCalendarPopup(True)
        self.input_date.setDisplayFormat("yyyy-MM-dd")
        self.input_date.setDate(QDate.currentDate())
        form_layout.addWidget(self.input_date, 0, 1)

        form_layout.addWidget(QLabel("Тип тренировки:"), 1, 0)
        self.input_type = QComboBox()
        self.input_type.setEditable(True)
        self.input_type.addItems([
            "Бег",
            "Силовая тренировка",
            "Плавание",
            "Велотренажер",
            "Кроссфит",
            "Йога",
            "Бокс",
        ])
        form_layout.addWidget(self.input_type, 1, 1)

        form_layout.addWidget(QLabel("Длительность (мин):"), 2, 0)
        self.input_duration = QLineEdit()
        self.input_duration.setPlaceholderText("Например: 45 (от 1 до 1440)")
        form_layout.addWidget(self.input_duration, 2, 1)

        form_layout.addWidget(QLabel("Сожжено калорий (ккал):"), 3, 0)
        self.input_calories = QLineEdit()
        self.input_calories.setPlaceholderText("Например: 420 (от 1 до 20000)")
        form_layout.addWidget(self.input_calories, 3, 1)

        form_layout.addWidget(QLabel("Заметки / Комментарий:"), 4, 0)
        self.input_notes = QLineEdit()
        self.input_notes.setPlaceholderText("Пульс, рабочие веса, самочувствие...")
        form_layout.addWidget(self.input_notes, 4, 1)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить тренировку")
        self.btn_add.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 6px;")
        self.btn_add.clicked.connect(self.add_workout)

        self.btn_delete = QPushButton("Удалить выбранную")
        self.btn_delete.setStyleSheet("background-color: #dc2626; color: white; padding: 6px;")
        self.btn_delete.clicked.connect(self.delete_selected_workout)

        self.btn_refresh = QPushButton("Обновить данные")
        self.btn_refresh.setStyleSheet("padding: 6px;")
        self.btn_refresh.clicked.connect(self.refresh_all)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        form_layout.addLayout(btn_layout, 5, 0, 1, 2)

        left_layout.addWidget(form_group)

        # Таблица тренировок
        table_group = QGroupBox("Журнал тренировок")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Дата", "Тип тренировки", "Мин.", "Ккал", "Заметки"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.table)

        left_layout.addWidget(table_group)
        splitter.addWidget(left_panel)

        # Правая панель: График активности
        chart_group = QGroupBox("Визуализация активности")
        chart_layout = QVBoxLayout(chart_group)
        self.chart_widget = ActivityChartWidget()
        chart_layout.addWidget(self.chart_widget)
        splitter.addWidget(chart_group)

        splitter.setSizes([600, 580])
        main_layout.addWidget(splitter, stretch=3)

        # 3. Нижняя панель: Логирование активности
        log_group = QGroupBox("Лог активности системы (Журнал событий)")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(140)
        log_layout.addWidget(self.log_output)

        main_layout.addWidget(log_group, stretch=1)

    def log_event(self, message: str, is_error: bool = False) -> None:
        """Записывает событие с меткой времени в виджет логирования."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "[ОШИБКА]" if is_error else "[ИНФО]"
        color = "#dc2626" if is_error else "#1e293b"
        formatted = f'<span style="color:{color};"><b>{timestamp} {prefix}:</b> {message}</span>'
        self.log_output.append(formatted)

    def parse_int_input(self, raw_value: str, field_type: str) -> int:
        """Преобразует строковый ввод в число или возвращает -1 для срабатывания кастомного исключения."""
        try:
            return int(raw_value.strip())
        except ValueError:
            return -1

    def add_workout(self) -> None:
        """Обработчик добавления тренировки с перехватом собственных исключений."""
        date_str = self.input_date.date().toString("yyyy-MM-dd")
        w_type = self.input_type.currentText()
        duration = self.parse_int_input(self.input_duration.text(), "duration")
        calories = self.parse_int_input(self.input_calories.text(), "calories")
        notes = self.input_notes.text()

        try:
            entry = WorkoutEntry(
                workout_date=date_str,
                workout_type=w_type,
                duration_minutes=duration,
                calories_burned=calories,
                notes=notes,
            )
            saved = self.db.add_workout(entry)
            self.log_event(
                f"Добавлена тренировка ID={saved.id}: '{saved.workout_type}' "
                f"({saved.duration_minutes} мин, {saved.calories_burned} ккал, интенсивность {saved.intensity} ккал/мин)."
            )
            self.input_duration.clear()
            self.input_calories.clear()
            self.input_notes.clear()
            self.refresh_all()

        except FitnessAppError as e:
            self.log_event(e.message, is_error=True)
            QMessageBox.warning(self, "Ошибка проверки данных", e.message)

    def delete_selected_workout(self) -> None:
        """Удаляет выбранную в таблице запись из БД."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            msg = "Не выбрана строка в таблице для удаления."
            self.log_event(msg, is_error=True)
            QMessageBox.information(self, "Удаление записи", msg)
            return

        row_idx = selected_rows[0].row()
        workout_id = int(self.table.item(row_idx, 0).text())

        try:
            self.db.delete_workout(workout_id)
            self.log_event(f"Тренировка с ID={workout_id} успешно удалена.")
            self.refresh_all()
        except FitnessAppError as e:
            self.log_event(e.message, is_error=True)
            QMessageBox.critical(self, "Ошибка удаления", e.message)

    def clear_all_workouts(self) -> None:
        """Очищает всю таблицу тренировок после подтверждения."""
        reply = QMessageBox.question(
            self,
            "Подтверждение очистки",
            "Вы действительно хотите удалить все записи о тренировках из базы данных?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                count = self.db.clear_all()
                self.log_event(f"База данных очищена. Удалено записей: {count}.")
                self.refresh_all()
            except FitnessAppError as e:
                self.log_event(e.message, is_error=True)

    def load_demo_data(self) -> None:
        """Заполняет базу демонстрационными тренировками для быстрой проверки графика и таблицы."""
        demo_samples = [
            ("2026-11-04", "Бег", 40, 410, "Утренняя пробежка в парке"),
            ("2026-11-05", "Силовая тренировка", 60, 520, "Грудь и трицепс, базовые упражнения"),
            ("2026-11-06", "Плавание", 45, 480, "Бассейн 1.5 км кролем"),
            ("2026-11-07", "Йога", 50, 220, "Растяжка и восстановление"),
            ("2026-11-08", "Кроссфит", 55, 670, "Высокоинтенсивный круговой комплекс"),
            ("2026-11-09", "Велотренажер", 35, 340, "Кардио-сессия в среднем темпе"),
        ]
        try:
            for d_date, d_type, d_dur, d_cal, d_notes in demo_samples:
                self.db.add_workout(WorkoutEntry(d_date, d_type, d_dur, d_cal, d_notes))
            self.log_event(f"Загружено {len(demo_samples)} демонстрационных тренировок.")
            self.refresh_all()
        except FitnessAppError as e:
            self.log_event(e.message, is_error=True)

    def refresh_all(self) -> None:
        """Синхронизирует таблицу, лейблы статистики и график с актуальным состоянием БД."""
        try:
            workouts = self.db.get_all_workouts()
            self.table.setRowCount(len(workouts))

            for row_idx, w in enumerate(workouts):
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(w.id)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(w.workout_date))
                self.table.setItem(row_idx, 2, QTableWidgetItem(w.workout_type))
                self.table.setItem(row_idx, 3, QTableWidgetItem(str(w.duration_minutes)))
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(w.calories_burned)))
                self.table.setItem(row_idx, 5, QTableWidgetItem(w.notes))

            stats = self.db.get_summary_stats()
            self.lbl_total_workouts.setText(f"Всего тренировок: {stats['total_workouts']}")
            self.lbl_total_duration.setText(f"Общее время: {stats['total_duration']} мин.")
            self.lbl_total_calories.setText(f"Сожжено калорий: {stats['total_calories']} ккал")
            self.lbl_avg_intensity.setText(f"Средняя интенсивность: {stats['avg_intensity']} ккал/мин")

            activity_data = self.db.get_activity_by_date()
            self.chart_widget.update_chart(activity_data)

        except FitnessAppError as e:
            self.log_event(e.message, is_error=True)

    def show_help_dialog(self) -> None:
        """Окно 'Справка -> Инструкция по использованию'."""
        QMessageBox.information(
            self,
            "Справка — Инструкция по использованию",
            "<h3>Инструкция по использованию приложения</h3>"
            "<p><b>1. Добавление новой тренировки:</b><br>"
            "• Выберите дату проведения тренировки в календаре.<br>"
            "• Выберите вид активности из выпадающего списка или введите собственный.<br>"
            "• Укажите длительность в минутах (допустимо целое число от 1 до 1440).<br>"
            "• Укажите количество сожженных калорий (от 1 до 20000 ккал).<br>"
            "• При необходимости заполните поле заметок и нажмите кнопку <b>«Добавить тренировку»</b>.</p>"
            "<p><b>2. Работа с таблицей и удаление записей:</b><br>"
            "• Все сохраненные тренировки отображаются в таблице «Журнал тренировок».<br>"
            "• Чтобы удалить запись, кликните по нужной строке в таблице и нажмите <b>«Удалить выбранную»</b>.</p>"
            "<p><b>3. График активности и сводная статистика:</b><br>"
            "• В верхней панели автоматически пересчитываются общее число тренировок, суммарное время, расход калорий и средняя интенсивность (ккал/мин).<br>"
            "• В правой части окна строится столбчатая диаграмма расхода калорий и длительности тренировок по датам.</p>"
            "<p><b>4. Быстрое тестирование и очистка (меню «Файл»):</b><br>"
            "• <i>Файл → Загрузить демо-данные</i>: автоматически добавляет набор тестовых тренировок за несколько дней для наглядной проверки графика.<br>"
            "• <i>Файл → Очистить все записи БД</i>: полностью удаляет все записи из базы данных.<br>"
            "• <i>Файл → Выход (Ctrl+Q)</i>: закрывает приложение.</p>"
            "<p><b>5. Контроль ошибок и логирование:</b><br>"
            "• Все действия пользователя и перехваченные ошибки валидации фиксируются с точным временем в нижней панели <b>«Лог активности системы»</b>.</p>",
        )