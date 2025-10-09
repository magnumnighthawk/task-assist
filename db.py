from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()
engine = create_engine('sqlite:///task_manager.db')
SessionLocal = sessionmaker(bind=engine)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    tasks = relationship('Task', back_populates='work', cascade='all, delete-orphan')

class Task(Base):
    __tablename__ = 'task'
    id = Column(Integer, primary_key=True, index=True)
    work_id = Column(Integer, ForeignKey('work.id'))
    title = Column(String, nullable=False)
    status = Column(String, default='pending')
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    work = relationship('Work', back_populates='tasks')

# Create tables
Base.metadata.create_all(bind=engine)

# CRUD functions

def create_work(db, title, description, tasks=None):
    work = Work(title=title, description=description)
    if tasks:
        for t in tasks:
            work.tasks.append(Task(**t))
    db.add(work)
    db.commit()
    db.refresh(work)
    return work

def create_task(db, work_id, title, status='pending', due_date=None):
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
