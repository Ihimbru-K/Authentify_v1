

import base64
from fastapi import FastAPI, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import pytz
from sqlalchemy.orm import Session
from datetime import datetime
import io
import pandas as pd
import logging

import uvicorn
from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Attendance, ErrorLog, Base, engine
from app.models import AdminLogin, AdminSignup, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate, StudentAuthRequest, CAMarkDisputeRequest, AttendanceReportRequest, ErrorReportRequest
from app.security import verify_password, create_access_token, get_current_admin, get_password_hash
from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv
from app.models import EnrollmentRequest

logging.basicConfig(level=logging.DEBUG)

app = FastAPI(title="Authentikate UBa Biometric Exam Attendance System")

# Create database tables
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.post("/auth/signup")
async def signup(admin: AdminSignup, db: Session = Depends(get_db)):
    try:
        department = db.query(Department).filter(Department.department_id == admin.department_id).first()
        if not department:
            raise HTTPException(status_code=400, detail="Invalid department")
        existing_admin = db.query(Admin).filter(Admin.username == admin.username).first()
        if existing_admin:
            raise HTTPException(status_code=400, detail="Username already exists")
        db_admin = Admin(
            username=admin.username,
            password_hash=get_password_hash(admin.password),
            department_id=admin.department_id
        )
        db.add(db_admin)
        db.commit()
        logging.debug(f"Admin registered: {admin.username}")
        token = create_access_token({"sub": admin.username})  # Generate token
        return {
            "message": "Admin registered successfully",
            "access_token": token,
            "token_type": "bearer"
        }
    except Exception as e:
        db.rollback()
        logging.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))




# @app.post("/auth/signup")
# async def signup(admin: AdminSignup, db: Session = Depends(get_db)):
#     try:
#         department = db.query(Department).filter(Department.department_id == admin.department_id).first()
#         if not department:
#             raise HTTPException(status_code=400, detail="Invalid department")
#         existing_admin = db.query(Admin).filter(Admin.username == admin.username).first()
#         if existing_admin:
#             raise HTTPException(status_code=400, detail="Username already exists")
#         db_admin = Admin(
#             username=admin.username,
#             password_hash=get_password_hash(admin.password),
#             department_id=admin.department_id
#         )
#         db.add(db_admin)
#         db.commit()
#         logging.debug(f"Admin registered: {admin.username}")
#         return {"message": "Admin registered successfully"}
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Signup error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/auth/login")
# async def login(admin: AdminLogin, db: Session = Depends(get_db)):
#     db_admin = db.query(Admin).filter(Admin.username == admin.username).first()
#     if not db_admin or not verify_password(admin.password, db_admin.password_hash):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     token = create_access_token({"sub": admin.username})
#     logging.debug(f"Admin logged in: {admin.username}")
#     return {
#         "access_token": token,
#         "token_type": "bearer",
#         "name": admin.username  
#     }


@app.post("/auth/login")
async def login(admin: AdminLogin, db: Session = Depends(get_db)):
    db_admin = db.query(Admin).filter(Admin.username == admin.username).first()
    if not db_admin or not verify_password(admin.password, db_admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.username})
    logging.debug(f"Admin logged in: {admin.username}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "name": admin.username,
        "department_id": db_admin.department_id  
    }




@app.post("/enrollment/status")
async def enrollment_status(request: EnrollmentStatusRequest, db: Session = Depends(get_db)):
    try:
        student = db.query(Student).filter(Student.fingerprint_template == request.fingerprint_template).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        enrolled_courses = db.query(CourseList, Course).join(Course, CourseList.course_id == Course.course_id).filter(
            CourseList.matriculation_number == student.matriculation_number
        ).all()
        course_info = [
            {"course_code": course.course_code, "course_name": course.course_name, "ca_mark": cl.ca_mark}
            for cl, course in enrolled_courses
        ]
        logging.debug(f"Enrollment status for {student.matriculation_number}: {course_info}")
        return {
            "matriculation_number": student.matriculation_number,
            "name": student.name,
            "department_id": student.department_id,
            "level_id": student.level_id,
            "photo": student.photo,  # Return base64 string
            "enrolled_courses": course_info
        }
    except Exception as e:
        logging.error(f"Status error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    

@app.post("/enrollment/enroll")
async def enroll_student(
    matriculation_number: str = Form(...),
    name: str = Form(...),
    department_id: int = Form(...),
    level_id: int = Form(...),
    fingerprint_template: str = Form(...),
    photo: UploadFile = File(None),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db) 
):
    try:
        logging.debug(f"Received form data: matric={matriculation_number}, name={name}, dept={department_id}, level={level_id}, fingerprint={fingerprint_template}")
        
        department = db.query(Department).filter(Department.department_id == department_id).first()
        level = db.query(Level).filter(Level.level_id == level_id, Level.department_id == department_id).first()
        if not department or not level:
            raise HTTPException(status_code=400, detail="Invalid department or level")
        if department.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")

        # Handle photo (store as base64 for now)
        photo_data = None
        if photo:
            photo_content = await photo.read()
            photo_data = base64.b64encode(photo_content).decode('utf-8')

        db_student = Student(
            matriculation_number=matriculation_number,
            name=name,
            department_id=department_id,
            level_id=level_id,
            fingerprint_template=fingerprint_template,
            photo=photo_data
        )
        db.add(db_student)
        db.commit()
        logging.debug(f"Student enrolled: {matriculation_number}")
        return {"message": "Student enrolled successfully", "student_id": db_student.matriculation_number}
    except Exception as e:
        db.rollback()
        logging.error(f"Enrollment error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))







@app.get("/enrollment/list/{department_id}/{level_id}")
async def download_enrollment_list(department_id: int, level_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        if admin.department_id != department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")
        students = db.query(Student).filter(
            Student.department_id == department_id,
            Student.level_id == level_id
        ).all()
        csv_content = generate_enrollment_list_csv(students, department_id, level_id)
        logging.debug(f"Enrollment list generated for dept {department_id}, level {level_id}")
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=enrollment_list_{department_id}_{level_id}.csv"}
        )
    except Exception as e:
        logging.error(f"List error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/course/upload")
async def upload_course_list(course_id: int, file: UploadFile = File(...), admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        course = db.query(Course).filter(Course.course_id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")
        content = await file.read()
        course_lists = parse_course_list_csv(content, course_id, db)
        for cl in course_lists:
            db_cl = CourseList(**cl)
            db.add(db_cl)
        db.commit()
        logging.debug(f"Course list uploaded for course {course_id}")
        return {"message": "Course list uploaded successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    




@app.post("/session/")
async def create_session(session: ExamSessionCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        # Validate course by code
        course = db.query(Course).filter(Course.course_code == session.course_code).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")

        # Check for overlapping sessions
        overlapping_session = db.query(ExamSession).filter(
            ExamSession.course_id == course.course_id,
            ExamSession.start_time <= session.end_time,
            ExamSession.end_time >= session.start_time
        ).first()
        if overlapping_session:
            raise HTTPException(status_code=400, detail="Session overlaps with existing session for this course")

        db_session = ExamSession(
            course_id=course.course_id,
            admin_id=admin.admin_id,
            start_time=session.start_time,
            end_time=session.end_time
        )
        db.add(db_session)
        db.commit()
        logging.debug(f"Session created: {db_session.session_id}")
        return {"message": "Session created successfully", "session_id": db_session.session_id}
    except Exception as e:
        db.rollback()
        logging.error(f"Session error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    


# @app.get("/departments")
# async def get_departments(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         depts = db.query(Department).filter(Department.department_id == admin.department_id).all()
#         return [{"department_id": d.department_id, "name": d.name} for d in depts]
#     except Exception as e:
#         logging.error(f"Departments fetch error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))


@app.get("/departments")
async def get_departments(db: Session = Depends(get_db)):
    try:
        depts = db.query(Department).all()  # Fetch all departments, not just for the admin
        return [{"department_id": d.department_id, "name": d.name} for d in depts]
    except Exception as e:
        logging.error(f"Departments fetch error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/levels")
async def get_levels(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        levels = db.query(Level).filter(Level.department_id == admin.department_id).all()
        return [{"level_id": l.level_id, "name": l.name} for l in levels]
    except Exception as e:
        logging.error(f"Levels fetch error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# @app.get("/levels")
# async def get_levels(department_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         if department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")
#         levels = db.query(Level).filter(Level.department_id == department_id).all()
#         return [{"level_id": l.level_id, "name": l.name} for l in levels]
#     except Exception as e:
#         logging.error(f"Levels fetch error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.get("/courses")
# async def get_courses(department_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         if department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")
#         courses = db.query(Course).filter(Course.department_id == department_id).all()
#         return [{"course_id": c.course_id, "course_code": c.course_code, "course_name": c.course_name} for c in courses]
#     except Exception as e:
#         logging.error(f"Courses fetch error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))



@app.get("/courses")
async def get_courses(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        courses = db.query(Course).filter(Course.department_id == admin.department_id).all()
        return [{"course_id": c.course_id, "course_code": c.course_code, "course_name": c.course_name} for c in courses]
    except Exception as e:
        logging.error(f"Courses fetch error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


    
@app.get("/sessions")
async def get_sessions(admin_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        # Fetch sessions where the admin is the creator
        sessions = db.query(ExamSession).filter(ExamSession.admin_id == admin.admin_id).all()
        if not sessions:
            raise HTTPException(status_code=404, detail="No sessions found for this admin")

        # Convert to response format
        return [
            {
                "session_id": session.session_id,
                "course_code": db.query(Course).filter(Course.course_id == session.course_id).first().course_code,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat()
            }
            for session in sessions
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching sessions: {str(e)}")



# @app.post("/attendance/authenticate")
# async def authenticate_student(auth: StudentAuthRequest, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate session
#         session = db.query(ExamSession).filter(ExamSession.session_id == auth.session_id).first()
#         if not session:
#             raise HTTPException(status_code=404, detail="Session not found")
#         if session.admin_id != admin.admin_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this session")

#         # Check time window in WAT
#         wat_tz = pytz.timezone('Africa/Lagos')  # WAT (UTC+1)
#         now = datetime.now(wat_tz).replace(tzinfo=None)  # Make naive
#         logging.debug(f"Current WAT time: {now}, Session start: {session.start_time}, end: {session.end_time}")

#         # start_time and end_time are naive (from TIMESTAMP WITHOUT TIME ZONE)
#         start_time = session.start_time
#         end_time = session.end_time

#         if now < start_time or now > end_time:
#             raise HTTPException(status_code=403, detail="Authentication outside session time window")

#         # Match fingerprint
#         student = db.query(Student).filter(Student.fingerprint_template == auth.fingerprint_template).first()
#         if not student:
#             error_log = ErrorLog(
#                 session_id=auth.session_id,
#                 matriculation_number=None,
#                 error_type="AUTH_FAILED",
#                 details="No student matched the provided fingerprint"
#             )
#             db.add(error_log)
#             db.commit()
#             logging.error(f"Fingerprint mismatch for session {auth.session_id}")
#             raise HTTPException(status_code=404, detail="Student not found")

#         # Check course enrollment
#         course_list = db.query(CourseList).filter(
#             CourseList.course_id == session.course_id,
#             CourseList.matriculation_number == student.matriculation_number
#         ).first()
#         if not course_list:
#             error_log = ErrorLog(
#                 session_id=auth.session_id,
#                 matriculation_number=student.matriculation_number,
#                 error_type="NOT_ENROLLED",
#                 details=f"Student not enrolled in course {session.course_id}"
#             )
#             db.add(error_log)
#             db.commit()
#             logging.error(f"Student {student.matriculation_number} not enrolled in course {session.course_id}")
#             raise HTTPException(status_code=403, detail="Student not enrolled in this course")

#         # Validate CA mark
#         if course_list.ca_mark is None or course_list.ca_mark < 0:
#             error_log = ErrorLog(
#                 session_id=auth.session_id,
#                 matriculation_number=student.matriculation_number,
#                 error_type="INVALID_CA_MARK",
#                 details=f"Invalid CA mark: {course_list.ca_mark}"
#             )
#             db.add(error_log)
#             db.commit()
#             logging.error(f"Invalid CA mark for {student.matriculation_number}: {course_list.ca_mark}")
#             raise HTTPException(status_code=403, detail="Invalid CA mark")

#         # Check if already authenticated
#         existing_attendance = db.query(Attendance).filter(
#             Attendance.session_id == auth.session_id,
#             Attendance.matriculation_number == student.matriculation_number
#         ).first()
#         if existing_attendance and existing_attendance.authenticated:
#             logging.debug(f"Student {student.matriculation_number} already authenticated for session {auth.session_id}")
#             return {
#                 #"course_name": course.course_name,
#                 "message": "Student already authenticated",
#                 "matriculation_number": student.matriculation_number,
#                 "name": student.name,
#                 "ca_mark": course_list.ca_mark,
#                 "photo": student.photo,
#             }

#         # Record attendance
#         attendance = Attendance(
#             session_id=auth.session_id,
#             matriculation_number=student.matriculation_number,
#             authenticated=True
#         )
#         db.add(attendance)
#         db.commit()
#         logging.debug(f"Student {student.matriculation_number} authenticated for session {auth.session_id}")
#         return {
#             "message": "Student authenticated successfully",
#             "matriculation_number": student.matriculation_number,
#             "name": student.name,
#             "ca_mark": course_list.ca_mark
#         }
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Authentication error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))



@app.post("/attendance/authenticate")
async def authenticate_student(auth: StudentAuthRequest, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        # Validate session
        session = db.query(ExamSession).filter(ExamSession.session_id == auth.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.admin_id != admin.admin_id:
            raise HTTPException(status_code=403, detail="Not authorized for this session")

        # Check time window in WAT
        wat_tz = pytz.timezone('Africa/Lagos')  # WAT (UTC+1)
        now = datetime.now(wat_tz).replace(tzinfo=None)  # Make naive
        logging.debug(f"Current WAT time: {now}, Session start: {session.start_time}, end: {session.end_time}")

        # start_time and end_time are naive (from TIMESTAMP WITHOUT TIME ZONE)
        start_time = session.start_time
        end_time = session.end_time

        if now < start_time or now > end_time:
            raise HTTPException(status_code=403, detail="Authentication outside session time window")

        # Match fingerprint
        student = db.query(Student).filter(Student.fingerprint_template == auth.fingerprint_template).first()
        if not student:
            error_log = ErrorLog(
                session_id=auth.session_id,
                matriculation_number=None,
                error_type="AUTH_FAILED",
                details="No student matched the provided fingerprint"
            )
            db.add(error_log)
            db.commit()
            logging.error(f"Fingerprint mismatch for session {auth.session_id}")
            raise HTTPException(status_code=404, detail="Student not found")

        # Check course enrollment
        course_list = db.query(CourseList).filter(
            CourseList.course_id == session.course_id,
            CourseList.matriculation_number == student.matriculation_number
        ).first()
        if not course_list:
            error_log = ErrorLog(
                session_id=auth.session_id,
                matriculation_number=student.matriculation_number,
                error_type="NOT_ENROLLED",
                details=f"Student not enrolled in course {session.course_id}"
            )
            db.add(error_log)
            db.commit()
            logging.error(f"Student {student.matriculation_number} not enrolled in course {session.course_id}")
            raise HTTPException(status_code=403, detail="Student not enrolled in this course")

        # Validate CA mark
        if course_list.ca_mark is None or course_list.ca_mark < 0:
            error_log = ErrorLog(
                session_id=auth.session_id,
                matriculation_number=student.matriculation_number,
                error_type="INVALID_CA_MARK",
                details=f"Invalid CA mark: {course_list.ca_mark}"
            )
            db.add(error_log)
            db.commit()
            logging.error(f"Invalid CA mark for {student.matriculation_number}: {course_list.ca_mark}")
            raise HTTPException(status_code=403, detail="Invalid CA mark")

        # Get course name
        course = db.query(Course).filter(Course.course_id == session.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check if already authenticated
        existing_attendance = db.query(Attendance).filter(
            Attendance.session_id == auth.session_id,
            Attendance.matriculation_number == student.matriculation_number
        ).first()
        if existing_attendance and existing_attendance.authenticated:
            logging.debug(f"Student {student.matriculation_number} already authenticated for session {auth.session_id}")
            return {
                "message": "Student already authenticated",
                "matriculation_number": student.matriculation_number,
                "name": student.name,
                "ca_mark": course_list.ca_mark,
                "photo": student.photo,
                "course_name": course.course_name
            }

        # Record attendance
        attendance = Attendance(
            session_id=auth.session_id,
            matriculation_number=student.matriculation_number,
            authenticated=True
        )
        db.add(attendance)
        db.commit()
        logging.debug(f"Student {student.matriculation_number} authenticated for session {auth.session_id}")
        return {
            "message": "Student authenticated successfully",
            "matriculation_number": student.matriculation_number,
            "name": student.name,
            "ca_mark": course_list.ca_mark,
            "photo": student.photo,
            "course_name": course.course_name
        }
    except Exception as e:
        db.rollback()
        logging.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sessions")
async def get_sessions(admin_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        if admin_id != admin.admin_id:
            raise HTTPException(status_code=403, detail="Not authorized to view sessions for this admin")
        wat_tz = pytz.timezone('Africa/Lagos')
        now = datetime.now(wat_tz).replace(tzinfo=None)
        # Delete expired sessions
        db.query(ExamSession).filter(ExamSession.end_time < now).delete()
        db.commit()
        sessions = db.query(ExamSession).filter(
            ExamSession.admin_id == admin.admin_id,
            ExamSession.end_time >= now
        ).all()
        if not sessions:
            return {"message": "No active sessions found for this admin"}
        return [
            {
                "session_id": session.session_id,
                "course_code": db.query(Course).filter(Course.course_id == session.course_id).first().course_code,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat()
            }
            for session in sessions
        ]
    except Exception as e:
        logging.error(f"Error fetching sessions: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# @app.delete("/sessions/{session_id}")
# async def end_session(session_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         session = db.query(ExamSession).filter(ExamSession.session_id == session_id).first()
#         if not session:
#             raise HTTPException(status_code=404, detail="Session not found")
#         if session.admin_id != admin.admin_id:
#             raise HTTPException(status_code=403, detail="Not authorized to end this session")
#         db.delete(session)
#         db.commit()
#         logging.debug(f"Session {session_id} ended and deleted by admin {admin.admin_id}")
#         return {"message": "Session ended and deleted successfully"}
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Error ending session: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))


@app.post("/attendance/dispute")
async def report_ca_mark_dispute(dispute: CAMarkDisputeRequest, db: Session = Depends(get_db)):
    try:
        # Validate session and course
        session = db.query(ExamSession).filter(ExamSession.session_id == dispute.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.course_id != dispute.course_id:
            raise HTTPException(status_code=400, detail="Course does not match session")

        # Validate student
        student = db.query(Student).filter(Student.matriculation_number == dispute.matriculation_number).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Log dispute
        error_log = ErrorLog(
            session_id=dispute.session_id,
            matriculation_number=dispute.matriculation_number,
            error_type="CA_MARK_ISSUE",
            details=dispute.details
        )
        db.add(error_log)
        db.commit()
        logging.debug(f"CA mark dispute logged for {dispute.matriculation_number} in session {dispute.session_id}")
        return {"message": "CA mark dispute logged successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Dispute error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/reports/attendance/{session_id}")
async def get_attendance_report(session_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        session = db.query(ExamSession).filter(ExamSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.admin_id != admin.admin_id:
            raise HTTPException(status_code=403, detail="Not authorized for this session")

        attendance_records = db.query(Attendance, Student).join(
            Student, Attendance.matriculation_number == Student.matriculation_number
        ).filter(Attendance.session_id == session_id).all()

        enrolled_students = db.query(CourseList, Student).join(
            Student, CourseList.matriculation_number == Student.matriculation_number
        ).filter(CourseList.course_id == session.course_id).all()

        data = []
        for a, s in attendance_records:
            if a.authenticated:
                data.append({
                    "matriculation_number": s.matriculation_number,
                    "name": s.name,
                    "status": "Present",
                    "timestamp": a.timestamp.isoformat()
                })

        enrolled_matrics = {s.matriculation_number for _, s in enrolled_students}
        for _, s in enrolled_students:
            if s.matriculation_number not in {a.matriculation_number for a, _ in attendance_records}:
                data.append({
                    "matriculation_number": s.matriculation_number,
                    "name": s.name,
                    "status": "Absent",
                    "timestamp": None
                })

        df = pd.DataFrame(data)
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        logging.debug(f"Attendance report generated for session {session_id}")
        return StreamingResponse(
            io.BytesIO(stream.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendance_report_{session_id}.csv"}
        )
    except Exception as e:
        logging.error(f"Report error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/reports/errors/{session_id}")
async def get_error_report(session_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        session = db.query(ExamSession).filter(ExamSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.admin_id != admin.admin_id:
            raise HTTPException(status_code=403, detail="Not authorized for this session")

        error_logs = db.query(ErrorLog).filter(ErrorLog.session_id == session_id).all()
        data = [
            {
                "matriculation_number": log.matriculation_number or "Unknown",
                "error_type": log.error_type,
                "details": log.details,
                "timestamp": log.timestamp.isoformat()
            }
            for log in error_logs
        ]

        df = pd.DataFrame(data)
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        logging.debug(f"Error report generated for session {session_id}")
        return StreamingResponse(
            io.BytesIO(stream.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=error_report_{session_id}.csv"}
        ) 
    except Exception as e:
        logging.error(f"Error report error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))