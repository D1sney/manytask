#!/usr/bin/env python3
"""
Скрипт для заполнения базы данных тестовыми данными
Использование:
    python seed_data.py
"""

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Импорты ваших моделей
from manytask.models import (
    Base,
    ComplexFormula,
    Course,
    Deadline,
    Grade,
    Namespace,
    PrimaryFormula,
    Task,
    TaskGroup,
    User,
    UserOnCourse,
    UserOnNamespace,
    UserOnNamespaceRole,
)
from manytask.course import CourseStatus, ManytaskDeadlinesType


# ==================== КОНФИГУРАЦИЯ ====================

# Получаем строку подключения из переменных окружения или используем дефолтную
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://adminmanytask:adminmanytask@localhost:5432/manytask"
)

# Параметры генерации данных
CONFIG = {
    "num_users": 50,  # Количество студентов
    "num_admins": 3,  # Количество админов
    "num_namespaces": 2,  # Количество пространств имён
    "num_courses": 3,  # Количество курсов
    "task_groups_per_course": 5,  # Групп заданий на курс
    "tasks_per_group": 4,  # Заданий в группе
    "student_completion_rate": 0.7,  # 70% студентов решают задачи
}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def generate_token(length: int = 32) -> str:
    """Генерирует случайный токен"""
    import secrets
    return secrets.token_hex(length)


def random_datetime(start: datetime, end: datetime) -> datetime:
    """Генерирует случайную дату между start и end"""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


# ==================== ОСНОВНОЙ КЛАСС ====================

class DataSeeder:
    def __init__(self, session: Session):
        self.session = session
        self.users: list[User] = []
        self.namespaces: list[Namespace] = []
        self.courses: list[Course] = []
        
    def seed_all(self, clean: bool = True):
        """Заполняет всю базу данных"""
        if clean:
            self.clean_database()
        
        print("🌱 Начинаем заполнение базы данных...")
        
        self.create_users()
        self.create_namespaces()
        self.create_courses()
        self.create_course_structure()
        self.enroll_students()
        self.create_grades()
        
        print("✅ База данных успешно заполнена!")
        self.print_summary()
    
    def clean_database(self):
        """Очищает все таблицы (ОСТОРОЖНО!)"""
        print("🗑️  Очистка базы данных...")
        # Удаляем в правильном порядке из-за foreign keys
        self.session.query(Grade).delete()
        self.session.query(Task).delete()
        self.session.query(TaskGroup).delete()
        self.session.query(Deadline).delete()
        self.session.query(PrimaryFormula).delete()
        self.session.query(ComplexFormula).delete()
        self.session.query(UserOnCourse).delete()
        self.session.query(Course).delete()
        self.session.query(UserOnNamespace).delete()
        self.session.query(Namespace).delete()
        self.session.query(User).delete()
        self.session.commit()
        print("✓ База данных очищена")
    
    def create_users(self):
        """Создаёт пользователей"""
        print(f"👥 Создание {CONFIG['num_users']} пользователей...")
        
        # Создаём админов
        for i in range(CONFIG['num_admins']):
            user = User(
                username=f"admin{i+1}",
                first_name=f"Admin",
                last_name=f"User{i+1}",
                rms_id=1000 + i,
                is_instance_admin=True,
            )
            self.session.add(user)
            self.users.append(user)
        
        # Создаём обычных пользователей
        first_names = ["Иван", "Мария", "Пётр", "Анна", "Сергей", "Елена", "Дмитрий", "Ольга"]
        last_names = ["Иванов", "Петров", "Сидоров", "Смирнов", "Козлов", "Новиков", "Морозов"]
        
        for i in range(CONFIG['num_users']):
            user = User(
                username=f"student{i+1}",
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                rms_id=2000 + i,
                is_instance_admin=False,
            )
            self.session.add(user)
            self.users.append(user)
        
        self.session.commit()
        print(f"✓ Создано {len(self.users)} пользователей")
    
    def create_namespaces(self):
        """Создаёт пространства имён"""
        print(f"📁 Создание {CONFIG['num_namespaces']} пространств имён...")
        
        namespace_data = [
            {"name": "Computer Science", "slug": "cs", "gitlab_group_id": 1000},
            {"name": "Mathematics", "slug": "math", "gitlab_group_id": 1001},
            {"name": "Physics", "slug": "physics", "gitlab_group_id": 1002},
        ]
        
        admin = self.users[0]
        
        for i in range(min(CONFIG['num_namespaces'], len(namespace_data))):
            data = namespace_data[i]
            namespace = Namespace(
                name=data["name"],
                slug=data["slug"],
                gitlab_group_id=data["gitlab_group_id"],
                created_by_id=admin.id,
            )
            self.session.add(namespace)
            self.session.flush()
            self.namespaces.append(namespace)
            
            for admin_user in self.users[:CONFIG['num_admins']]:
                user_on_namespace = UserOnNamespace(
                    user_id=admin_user.id,
                    namespace_id=namespace.id,
                    role=UserOnNamespaceRole.NAMESPACE_ADMIN,
                    assigned_by_id=admin.id,
                )
                self.session.add(user_on_namespace)
        
        self.session.commit()
        print(f"✓ Создано {len(self.namespaces)} пространств имён")


    
    def create_courses(self):
        """Создаёт курсы"""
        print(f"📚 Создание {CONFIG['num_courses']} курсов...")
        
        course_data = [
            {
                "name": "Python Programming 2024",
                "gitlab_course_group": "cs/python-2024",
                "gitlab_course_public_repo": "cs/python-2024/public",
                "gitlab_course_students_group": "cs/python-2024/students",
            },
            {
                "name": "Algorithms and Data Structures",
                "gitlab_course_group": "cs/algorithms-2024",
                "gitlab_course_public_repo": "cs/algorithms-2024/public",
                "gitlab_course_students_group": "cs/algorithms-2024/students",
            },
            {
                "name": "Web Development",
                "gitlab_course_group": "cs/webdev-2024",
                "gitlab_course_public_repo": "cs/webdev-2024/public",
                "gitlab_course_students_group": "cs/webdev-2024/students",
            },
        ]
        
        for i in range(min(CONFIG['num_courses'], len(course_data))):
            data = course_data[i]
            namespace = self.namespaces[i % len(self.namespaces)] if self.namespaces else None
            
            course = Course(
                namespace_id=namespace.id if namespace else None,
                name=data["name"],
                registration_secret=f"secret_{i+1}",
                token=generate_token(16),
                show_allscores=True,
                status=CourseStatus.IN_PROGRESS if i == 0 else CourseStatus.CREATED,
                gitlab_course_group=data["gitlab_course_group"],
                gitlab_course_public_repo=data["gitlab_course_public_repo"],
                gitlab_course_students_group=data["gitlab_course_students_group"],
                gitlab_default_branch="main",
                task_url_template="https://gitlab.com/{repo}/tree/{branch}/{task}",
                links={
                    "telegram": "https://t.me/course_chat",
                    "discord": "https://discord.gg/course",
                },
                timezone="Europe/Moscow",
                max_submissions=None,
                submission_penalty=0.1,
                deadlines_type=ManytaskDeadlinesType.HARD,
            )
            self.session.add(course)
            self.session.flush()
            self.courses.append(course)
        
        self.session.commit()
        print(f"✓ Создано {len(self.courses)} курсов")
    
    def create_course_structure(self):
        """Создаёт структуру курса: группы заданий, дедлайны, задания"""
        print("📝 Создание структуры курсов...")
        
        now = datetime.now(tz=timezone.utc)
        
        for course in self.courses:
            # Создаём формулу оценок
            for grade_threshold in [3, 4, 5]:
                complex_formula = ComplexFormula(
                    grade=grade_threshold,
                    course_id=course.id,
                )
                self.session.add(complex_formula)
                self.session.flush()
                
                # Добавляем первичную формулу
                primary_formula = PrimaryFormula(
                    complex_id=complex_formula.id,
                    primary_formula={"base": grade_threshold * 20.0},
                )
                self.session.add(primary_formula)
            
            # Создаём группы заданий
            for group_idx in range(CONFIG['task_groups_per_course']):
                # Создаём дедлайн
                start_date = now + timedelta(days=group_idx * 7)
                end_date = start_date + timedelta(days=14)
                
                deadline = Deadline(
                    start=start_date,
                    steps={
                        0.9: end_date - timedelta(days=7),
                        0.7: end_date - timedelta(days=3),
                        0.5: end_date,
                    },
                    end=end_date + timedelta(days=7),
                )
                self.session.add(deadline)
                self.session.flush()
                
                # Создаём группу заданий
                task_group = TaskGroup(
                    name=f"week{group_idx + 1}",
                    course_id=course.id,
                    deadline_id=deadline.id,
                    enabled=True,
                    position=group_idx,
                )
                self.session.add(task_group)
                self.session.flush()
                
                # Создаём задания в группе
                for task_idx in range(CONFIG['tasks_per_group']):
                    is_bonus = task_idx == CONFIG['tasks_per_group'] - 1  # Последнее задание бонусное
                    
                    task = Task(
                        name=f"task_{group_idx+1}_{task_idx+1}",
                        group_id=task_group.id,
                        score=10 if not is_bonus else 5,
                        min_score=0,
                        is_bonus=is_bonus,
                        is_large=task_idx == 0,  # Первое задание большое
                        is_special=False,
                        enabled=True,
                        url=f"/tasks/week{group_idx+1}/task{task_idx+1}",
                        position=task_idx,
                    )
                    self.session.add(task)
        
        self.session.commit()
        print("✓ Структура курсов создана")
    
    def enroll_students(self):
        """Записывает студентов на курсы"""
        print("🎓 Запись студентов на курсы...")
        
        students = [u for u in self.users if not u.is_instance_admin]
        admins = [u for u in self.users if u.is_instance_admin]
        
        for course in self.courses:
            # Все админы - админы курса
            for admin in admins:
                user_on_course = UserOnCourse(
                    user_id=admin.id,
                    course_id=course.id,
                    join_date=datetime.now(tz=timezone.utc) - timedelta(days=30),
                    is_course_admin=True,
                    comment="Course administrator",
                )
                self.session.add(user_on_course)
            
            # Записываем случайных студентов
            num_students = random.randint(
                len(students) // 2,
                len(students)
            )
            enrolled_students = random.sample(students, num_students)
            
            for student in enrolled_students:
                join_date = random_datetime(
                    datetime.now(tz=timezone.utc) - timedelta(days=60),
                    datetime.now(tz=timezone.utc) - timedelta(days=1),
                )
                
                user_on_course = UserOnCourse(
                    user_id=student.id,
                    course_id=course.id,
                    join_date=join_date,
                    is_course_admin=False,
                    comment=None,
                )
                self.session.add(user_on_course)
        
        self.session.commit()
        print("✓ Студенты записаны на курсы")
    
    def create_grades(self):
        """Создаёт оценки для студентов"""
        print("📊 Генерация оценок...")
        
        for course in self.courses:
            # Получаем всех студентов курса
            users_on_course = self.session.query(UserOnCourse).filter(
                UserOnCourse.course_id == course.id,
                UserOnCourse.is_course_admin == False,
            ).all()
            
            # Получаем все задания курса
            task_groups = self.session.query(TaskGroup).filter(
                TaskGroup.course_id == course.id
            ).all()
            
            for user_on_course in users_on_course:
                # Решает ли этот студент задачи
                is_active = random.random() < CONFIG['student_completion_rate']
                
                if not is_active:
                    continue
                
                for task_group in task_groups:
                    tasks = self.session.query(Task).filter(
                        Task.group_id == task_group.id
                    ).all()
                    
                    for task in tasks:
                        # Вероятность решения задачи
                        if random.random() < 0.8:  # 80% задач решены
                            # Генерируем оценку
                            if task.is_bonus:
                                score = random.choice([0, task.score])
                            else:
                                score = random.randint(
                                    task.min_score,
                                    task.score
                                )
                            
                            # Случайная дата сдачи
                            if task_group.deadline:
                                submit_date = random_datetime(
                                    task_group.deadline.start,
                                    task_group.deadline.end + timedelta(days=7),
                                )
                            else:
                                submit_date = datetime.now(tz=timezone.utc)
                            
                            grade = Grade(
                                user_on_course_id=user_on_course.id,
                                task_id=task.id,
                                score=score,
                                last_submit_date=submit_date,
                            )
                            self.session.add(grade)
        
        self.session.commit()
        print("✓ Оценки сгенерированы")
    
    def print_summary(self):
        """Выводит статистику по созданным данным"""
        print("\n" + "="*50)
        print("📈 СТАТИСТИКА")
        print("="*50)
        
        users_count = self.session.query(User).count()
        admins_count = self.session.query(User).filter(User.is_instance_admin == True).count()
        namespaces_count = self.session.query(Namespace).count()
        courses_count = self.session.query(Course).count()
        tasks_count = self.session.query(Task).count()
        grades_count = self.session.query(Grade).count()
        
        print(f"👥 Пользователей: {users_count} (админов: {admins_count})")
        print(f"📁 Пространств имён: {namespaces_count}")
        print(f"📚 Курсов: {courses_count}")
        print(f"📝 Заданий: {tasks_count}")
        print(f"📊 Оценок: {grades_count}")
        
        print("\n🔑 ТЕСТОВЫЕ ДАННЫЕ ДЛЯ ВХОДА:")
        print("-" * 50)
        print("Админы:")
        for i in range(CONFIG['num_admins']):
            print(f"  - username: admin{i+1}, rms_id: {1000 + i}")
        
        print("\nСтуденты (примеры):")
        for i in range(min(3, CONFIG['num_users'])):
            print(f"  - username: student{i+1}, rms_id: {2000 + i}")
        
        print("\nКурсы:")
        for course in self.courses:
            print(f"  - {course.name}")
            print(f"    Secret: {course.registration_secret}")
            print(f"    Token: {course.token}")
            print(f"    Status: {course.status.value}")
        
        print("="*50 + "\n")


# ==================== MAIN ====================

def main():
    """Основная функция"""
    print("🚀 Скрипт заполнения базы данных")
    print(f"📦 Подключение к: {DATABASE_URL}")
    
    # Создаём подключение
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Проверяем подключение
        session.execute(text("SELECT 1"))
        print("✓ Подключение к БД успешно\n")
        
        # Запускаем заполнение
        seeder = DataSeeder(session)
        seeder.seed_all(clean=True)  # clean=False если не хотите удалять данные
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
