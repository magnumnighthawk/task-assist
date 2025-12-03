from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy import Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

# Use DATABASE_PATH env var if set, otherwise default to local path
DATABASE_PATH = os.getenv('DATABASE_PATH', 'task_manager.db')
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Work(Base):
    __tablename__ = 'work'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default='Draft')  # Draft, Published, Completed
    expected_completion_hint = Column(String, nullable=True)  # "this week", "by Friday", etc
    created_at = Column(DateTime, default=datetime.utcnow)
    tasks = relationship('Task', back_populates='work', cascade='all, delete-orphan')

class Task(Base):
    __tablename__ = 'task'
    id = Column(Integer, primary_key=True, index=True)
    work_id = Column(Integer, ForeignKey('work.id'))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    priority = Column(String, default='Medium')  # Low, Medium, High
    status = Column(String, default='Draft')  # Draft, Published, Tracked, Completed
    due_date = Column(DateTime, nullable=True)
    snooze_count = Column(Integer, default=0)
    calendar_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    work = relationship('Work', back_populates='tasks')


class WatchChannel(Base):
    __tablename__ = 'watch_channel'
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String, nullable=False, unique=True)
    resource_id = Column(String, nullable=True)
    address = Column(String, nullable=False)
    expiration = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# CRUD functions


def create_work(db, title, description, tasks=None, status='Draft', expected_completion_hint=None):
    work = Work(title=title, description=description, status=status, expected_completion_hint=expected_completion_hint)
    if tasks:
        for t in tasks:
            work.tasks.append(Task(**t))
    db.add(work)
    db.commit()
    db.refresh(work)
    return work

def publish_work(db, work_id):
    work = db.query(Work).filter(Work.id == work_id).first()
    if work:
        work.status = 'Published'
        for task in work.tasks:
            task.status = 'Published'
        db.commit()
    return work

def complete_work(db, work_id):
    work = db.query(Work).filter(Work.id == work_id).first()
    if work:
        work.status = 'Completed'
        for task in work.tasks:
            task.status = 'Completed'
        db.commit()
    return work

def update_task_status(db, task_id, status):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = status
        db.commit()
    return task

def increment_task_snooze(db, task_id):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.snooze_count += 1
        db.commit()
    return task

def update_task_calendar_event(db, task_id, event_id):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.calendar_event_id = event_id
        db.commit()
    return task

def create_task(db, work_id, title, status='Draft', due_date=None):
    task = Task(work_id=work_id, title=title, status=status, due_date=due_date)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def get_work(db, work_id):
    return db.query(Work).filter(Work.id == work_id).first()

def get_tasks_by_work(db, work_id):
    return db.query(Task).filter(Task.work_id == work_id).all()

def get_all_works(db):
    return db.query(Work).all()

def get_all_tasks(db):
    return db.query(Task).all()

def get_unnotified_completed_tasks(db):
    return db.query(Task).filter(Task.status == 'Completed', Task.notified == False).all()

def get_unnotified_completed_works(db):
    return db.query(Work).filter(Work.status == 'Completed', Work.notified == False).all()

def create_watch_channel(db, channel_id, resource_id, address, expiration=None):
    wc = WatchChannel(channel_id=channel_id, resource_id=resource_id, address=address, expiration=expiration)
    db.add(wc)
    db.commit()
    db.refresh(wc)
    return wc


def get_all_watch_channels(db):
    return db.query(WatchChannel).all()


def update_watch_channel_expiration(db, channel_id, expiration):
    wc = db.query(WatchChannel).filter(WatchChannel.channel_id == channel_id).first()
    if wc:
        wc.expiration = expiration
        db.commit()
    return wc


def delete_watch_channel(db, channel_id):
    wc = db.query(WatchChannel).filter(WatchChannel.channel_id == channel_id).first()
    if wc:
        db.delete(wc)
        db.commit()
    return wc
