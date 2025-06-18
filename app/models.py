

from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from datetime import datetime
from app.config import DATABASE_URL

# SQLAlchemy Setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# SQLAlchemy Models
class University(Base):
    __tablename__ = "universities"
    university_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

class School(Base):
    __tablename__ = "schools"
    school_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    university_id = Column(Integer, ForeignKey("universities.university_id"))

class Department(Base):
    __tablename__ = "departments"
    department_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    school_id = Column(Integer, ForeignKey("schools.school_id"))

class Level(Base):
    __tablename__ = "levels"
    level_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"))

class Course(Base):
    __tablename__ = "courses"
    course_id = Column(Integer, primary_key=True)
    course_code = Column(String, unique=True, nullable=False)
    course_name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"))
    level_id = Column(Integer, ForeignKey("levels.level_id"))

class Student(Base):
    __tablename__ = "students"
    matriculation_number = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"))
    level_id = Column(Integer, ForeignKey("levels.level_id"))
    photo = Column(String, nullable=True)
    fingerprint_template = Column(String, nullable=False)

class CourseList(Base):
    __tablename__ = "course_lists"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"))
    matriculation_number = Column(String, ForeignKey("students.matriculation_number"))
    ca_mark = Column(Float, nullable=True)

class ExamSession(Base):
    __tablename__ = "exam_sessions"
    session_id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"))
    admin_id = Column(Integer, ForeignKey("admins.admin_id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.session_id"))
    matriculation_number = Column(String, ForeignKey("students.matriculation_number"))
    authenticated = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ErrorLog(Base):
    __tablename__ = "error_logs"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.session_id"))
    matriculation_number = Column(String, ForeignKey("students.matriculation_number"))
    error_type = Column(String)
    details = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Admin(Base):
    __tablename__ = "admins"
    admin_id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"))

# Pydantic Models
class AdminLogin(BaseModel):
    username: str
    password: str

class AdminSignup(BaseModel):
    username: str
    password: str
    department_id: int

class StudentCreate(BaseModel):
    matriculation_number: str
    name: str
    department_id: int
    level_id: int
    fingerprint_template: str
    photo: Optional[str] = None

class EnrollmentStatusRequest(BaseModel):
    fingerprint_template: str

class ExamSessionCreate(BaseModel):
    course_code: str  # Changed to course_code for clarity
    start_time: datetime
    end_time: datetime

class StudentAuthRequest(BaseModel):
    session_id: int
    fingerprint_template: str

class CAMarkDisputeRequest(BaseModel):
    session_id: int
    matriculation_number: str
    course_id: int
    details: str

class AttendanceReportRequest(BaseModel):
    session_id: int

class ErrorReportRequest(BaseModel):
    session_id: int
























# from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# from pydantic import BaseModel
# from datetime import datetime
# from app.config import DATABASE_URL

# # SQLAlchemy Setup
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# # SQLAlchemy Models
# class University(Base):
#     __tablename__ = "universities"
#     university_id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)

# class School(Base):
#     __tablename__ = "schools"
#     school_id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)
#     university_id = Column(Integer, ForeignKey("universities.university_id"))

# class Department(Base):
#     __tablename__ = "departments"
#     department_id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)
#     school_id = Column(Integer, ForeignKey("schools.school_id"))

# class Level(Base):
#     __tablename__ = "levels"
#     level_id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)
#     department_id = Column(Integer, ForeignKey("departments.department_id"))

# class Course(Base):
#     __tablename__ = "courses"
#     course_id = Column(Integer, primary_key=True)
#     course_code = Column(String, unique=True, nullable=False)
#     course_name = Column(String, nullable=False)
#     department_id = Column(Integer, ForeignKey("departments.department_id"))
#     level_id = Column(Integer, ForeignKey("levels.level_id"))

# class Student(Base):
#     __tablename__ = "students"
#     matriculation_number = Column(String, primary_key=True)
#     name = Column(String, nullable=False)
#     department_id = Column(Integer, ForeignKey("departments.department_id"))
#     level_id = Column(Integer, ForeignKey("levels.level_id"))
#     fingerprint_template = Column(String, nullable=False)

# class CourseList(Base):
#     __tablename__ = "course_lists"
#     id = Column(Integer, primary_key=True)
#     course_id = Column(Integer, ForeignKey("courses.course_id"))
#     matriculation_number = Column(String, ForeignKey("students.matriculation_number"))
#     ca_mark = Column(Float, nullable=True)

# class ExamSession(Base):
#     __tablename__ = "exam_sessions"
#     session_id = Column(Integer, primary_key=True)
#     course_id = Column(Integer, ForeignKey("courses.course_id"))
#     admin_id = Column(Integer, ForeignKey("admins.admin_id"))
#     start_time = Column(DateTime, nullable=False)
#     end_time = Column(DateTime, nullable=False)

# class Attendance(Base):
#     __tablename__ = "attendance"
#     id = Column(Integer, primary_key=True)
#     session_id = Column(Integer, ForeignKey("exam_sessions.session_id"))
#     matriculation_number = Column(String, ForeignKey("students.matriculation_number"))
#     authenticated = Column(Boolean, default=False)
#     timestamp = Column(DateTime, default=datetime.utcnow)

# class ErrorLog(Base):
#     #
#     __tablename__ = "error_logs"
#     id = Column(Integer, primary_key=True)
#     session_id = Column(Integer, ForeignKey("exam_sessions.session_id"))
#     matriculation_number = Column(String, ForeignKey("students.matriculation_number"))
#     error_type = Column(String)
#     details = Column(String)
#     timestamp = Column(DateTime, default=datetime.utcnow)

# class Admin(Base):
#     __tablename__ = "admins"
#     admin_id = Column(Integer, primary_key=True)
#     username = Column(String, unique=True, nullable=False)
#     password_hash = Column(String, nullable=False)
#     department_id = Column(Integer, ForeignKey("departments.department_id"))

# # Pydantic Models
# class AdminLogin(BaseModel):
#     username: str
#     password: str

# class StudentCreate(BaseModel):
#     matriculation_number: str
#     name: str
#     department_id: int
#     level_id: int
#     fingerprint_template: str

# class EnrollmentStatusRequest(BaseModel):
#     fingerprint_template: str

# class ExamSessionCreate(BaseModel):
#     course_id: int
#     start_time: datetime
#     end_time: datetime

# class AdminSignup(BaseModel):
#     username: str
#     password: str
#     department_id: int


# class StudentAuthRequest(BaseModel):
#     session_id: int
#     fingerprint_template: str

# class AttendanceReportRequest(BaseModel):
#     session_id: int