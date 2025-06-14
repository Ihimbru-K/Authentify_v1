from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
import io
import pandas as pd
import logging
from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Attendance, ErrorLog, Base, engine
from app.models import AdminLogin, AdminSignup, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate, StudentAuthRequest, CAMarkDisputeRequest, AttendanceReportRequest, ErrorReportRequest
from app.security import verify_password, create_access_token, get_current_admin, get_password_hash
from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv

logging.basicConfig(level=logging.DEBUG)

app = FastAPI(title="Authentikate Biometric UBa Exam Attendance System")

# Create database tables
Base.metadata.create_all(bind=engine)

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
        return {"message": "Admin registered successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
async def login(admin: AdminLogin, db: Session = Depends(get_db)):
    db_admin = db.query(Admin).filter(Admin.username == admin.username).first()
    if not db_admin or not verify_password(admin.password, db_admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.username})
    logging.debug(f"Admin logged in: {admin.username}")
    return {"access_token": token, "token_type": "bearer"}

@app.post("/enrollment/enroll")
async def enroll_student(student: StudentCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        department = db.query(Department).filter(Department.department_id == student.department_id).first()
        level = db.query(Level).filter(Level.level_id == student.level_id, Level.department_id == student.department_id).first()
        if not department or not level:
            raise HTTPException(status_code=400, detail="Invalid department or level")
        if department.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")
        db_student = Student(
            matriculation_number=student.matriculation_number,
            name=student.name,
            department_id=student.department_id,
            level_id=student.level_id,
            fingerprint_template=student.fingerprint_template
        )
        db.add(db_student)
        db.commit()
        logging.debug(f"Student enrolled: {student.matriculation_number}")
        return {"message": "Student enrolled successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Enrollment error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

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
            "enrolled_courses": course_info
        }
    except Exception as e:
        logging.error(f"Status error: {str(e)}")
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

@app.post("/attendance/authenticate")
async def authenticate_student(auth: StudentAuthRequest, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        # Validate session
        session = db.query(ExamSession).filter(ExamSession.session_id == auth.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.admin_id != admin.admin_id:
            raise HTTPException(status_code=403, detail="Not authorized for this session")

        # Check time window
        now = datetime.utcnow()
        if now < session.start_time or now > session.end_time:
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
                "ca_mark": course_list.ca_mark
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
            "ca_mark": course_list.ca_mark
        }
    except Exception as e:
        db.rollback()
        logging.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

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


































# from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session
# import io
# import pandas as pd
# import logging
# from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Attendance, ErrorLog, Base, engine
# from app.models import AdminLogin, AdminSignup, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate, StudentAuthRequest, AttendanceReportRequest
# from app.security import verify_password, create_access_token, get_current_admin, get_password_hash
# from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv

# logging.basicConfig(level=logging.DEBUG)

# app = FastAPI(title="Authentikate Biometric UBa Exam Attendance System")

# # Create database tables
# Base.metadata.create_all(bind=engine)

# @app.post("/auth/signup")
# async def signup(admin: AdminSignup, db: Session = Depends(get_db)):
#     try:
#         # Validate department
#         department = db.query(Department).filter(Department.department_id == admin.department_id).first()
#         if not department:
#             raise HTTPException(status_code=400, detail="Invalid department")

#         # Check if username exists
#         existing_admin = db.query(Admin).filter(Admin.username == admin.username).first()
#         if existing_admin:
#             raise HTTPException(status_code=400, detail="Username already exists")

#         # Hash password and create admin
#         db_admin = Admin(
#             username=admin.username,
#             password_hash=get_password_hash(admin.password),
#             department_id=admin.department_id
#         )
#         db.add(db_admin)
#         db.commit()
#         return {"message": "Admin registered successfully"}
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/auth/login")
# async def login(admin: AdminLogin, db: Session = Depends(get_db)):
#     db_admin = db.query(Admin).filter(Admin.username == admin.username).first()
#     if not db_admin or not verify_password(admin.password, db_admin.password_hash):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     token = create_access_token({"sub": admin.username})
#     return {"access_token": token, "token_type": "bearer"}

# @app.post("/enrollment/enroll")
# async def enroll_student(student: StudentCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate department and level
#         department = db.query(Department).filter(Department.department_id == student.department_id).first()
#         level = db.query(Level).filter(Level.level_id == student.level_id, Level.department_id == student.department_id).first()
#         if not department or not level:
#             raise HTTPException(status_code=400, detail="Invalid department or level")
#         if department.department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")

#         # Store fingerprint as string
#         db_student = Student(
#             matriculation_number=student.matriculation_number,
#             name=student.name,
#             department_id=student.department_id,
#             level_id=student.level_id,
#             fingerprint_template=student.fingerprint_template
#         )
#         db.add(db_student)
#         db.commit()
#         logging.debug(f"Student enrolled: {student.matriculation_number}")
#         return {"message": "Student enrolled successfully"}
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Enrollment error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/enrollment/status")
# async def enrollment_status(request: EnrollmentStatusRequest, db: Session = Depends(get_db)):
#     try:
#         # Match fingerprint string
#         student = db.query(Student).filter(Student.fingerprint_template == request.fingerprint_template).first()
#         if not student:
#             raise HTTPException(status_code=404, detail="Student not found")

#         # Check course lists
#         enrolled_courses = db.query(CourseList, Course).join(Course, CourseList.course_id == Course.course_id).filter(
#             CourseList.matriculation_number == student.matriculation_number
#         ).all()
#         course_info = [
#             {"course_code": course.course_code, "course_name": course.course_name, "ca_mark": cl.ca_mark}
#             for cl, course in enrolled_courses
#         ]
#         logging.debug(f"Enrollment status for {student.matriculation_number}: {course_info}")
#         return {
#             "matriculation_number": student.matriculation_number,
#             "name": student.name,
#             "department_id": student.department_id,
#             "level_id": student.level_id,
#             "enrolled_courses": course_info
#         }
#     except Exception as e:
#         logging.error(f"Status error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.get("/enrollment/list/{department_id}/{level_id}")
# async def download_enrollment_list(department_id: int, level_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         if admin.department_id != department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")
#         students = db.query(Student).filter(
#             Student.department_id == department_id,
#             Student.level_id == level_id
#         ).all()
#         csv_content = generate_enrollment_list_csv(students, department_id, level_id)
#         logging.debug(f"Enrollment list generated for dept {department_id}, level {level_id}")
#         return StreamingResponse(
#             io.BytesIO(csv_content.encode('utf-8')),
#             media_type="text/csv",
#             headers={"Content-Disposition": f"attachment; filename=enrollment_list_{department_id}_{level_id}.csv"}
#         )
#     except Exception as e:
#         logging.error(f"List error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/course/upload")
# async def upload_course_list(course_id: int, file: UploadFile = File(...), admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate course
#         course = db.query(Course).filter(Course.course_id == course_id).first()
#         if not course:
#             raise HTTPException(status_code=404, detail="Course not found")
#         if course.department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")

#         # Parse CSV
#         content = await file.read()
#         course_lists = parse_course_list_csv(content, course_id, db)
#         for cl in course_lists:
#             db_cl = CourseList(**cl)
#             db.add(db_cl)
#         db.commit()
#         logging.debug(f"Course list uploaded for course {course_id}")
#         return {"message": "Course list uploaded successfully"}
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Upload error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/session/")
# async def create_session(session: ExamSessionCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate course
#         course = db.query(Course).filter(Course.course_id == session.course_id).first()
#         if not course:
#             raise HTTPException(status_code=404, detail="Course not found")
#         if course.department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")

#         db_session = ExamSession(
#             course_id=session.course_id,
#             admin_id=admin.admin_id,
#             start_time=session.start_time,
#             end_time=session.end_time
#         )
#         db.add(db_session)
#         db.commit()
#         logging.debug(f"Session created: {db_session.session_id}")
#         return {"message": "Session created successfully", "session_id": db_session.session_id}
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Session error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/attendance/authenticate")
# async def authenticate_student(auth: StudentAuthRequest, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate session
#         session = db.query(ExamSession).filter(ExamSession.session_id == auth.session_id).first()
#         if not session:
#             raise HTTPException(status_code=404, detail="Session not found")
#         if session.admin_id != admin.admin_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this session")

#         # Match fingerprint
#         student = db.query(Student).filter(Student.fingerprint_template == auth.fingerprint_template).first()
#         if not student:
#             # Log error
#             error_log = ErrorLog(
#                 session_id=auth.session_id,
#                 matriculation_number=None,
#                 error_type="FINGERPRINT_MISMATCH",
#                 details="No student matched the provided fingerprint"
#             )
#             db.add(error_log)
#             db.commit()
#             logging.error(f"Fingerprint mismatch for session {auth.session_id}")
#             raise HTTPException(status_code=404, detail="Student not found")

#         # Check if student is enrolled in the course
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

#         # Check if already authenticated
#         existing_attendance = db.query(Attendance).filter(
#             Attendance.session_id == auth.session_id,
#             Attendance.matriculation_number == student.matriculation_number
#         ).first()
#         if existing_attendance and existing_attendance.authenticated:
#             logging.debug(f"Student {student.matriculation_number} already authenticated for session {auth.session_id}")
#             return {"message": "Student already authenticated"}

#         # Record attendance
#         attendance = Attendance(
#             session_id=auth.session_id,
#             matriculation_number=student.matriculation_number,
#             authenticated=True
#         )
#         db.add(attendance)
#         db.commit()
#         logging.debug(f"Student {student.matriculation_number} authenticated for session {auth.session_id}")
#         return {"message": "Student authenticated successfully", "matriculation_number": student.matriculation_number}
#     except Exception as e:
#         db.rollback()
#         logging.error(f"Authentication error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))

# @app.get("/reports/attendance/{session_id}")
# async def get_attendance_report(session_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate session
#         session = db.query(ExamSession).filter(ExamSession.session_id == session_id).first()
#         if not session:
#             raise HTTPException(status_code=404, detail="Session not found")
#         if session.admin_id != admin.admin_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this session")

#         # Get attendance records
#         attendance_records = db.query(Attendance, Student).join(
#             Student, Attendance.matriculation_number == Student.matriculation_number
#         ).filter(Attendance.session_id == session_id).all()

#         # Get enrolled students for the course
#         enrolled_students = db.query(CourseList, Student).join(
#             Student, CourseList.matriculation_number == Student.matriculation_number
#         ).filter(CourseList.course_id == session.course_id).all()

#         # Prepare report
#         data = []
#         enrolled_matrics = {s.matriculation_number for _, s in enrolled_students}
#         for a, s in attendance_records:
#             if a.authenticated:
#                 data.append({
#                     "matriculation_number": s.matriculation_number,
#                     "name": s.name,
#                     "status": "Present"
#                 })

#         # Add absent students
#         for _, s in enrolled_students:
#             if s.matriculation_number not in {a.matriculation_number for a, _ in attendance_records}:
#                 data.append({
#                     "matriculation_number": s.matriculation_number,
#                     "name": s.name,
#                     "status": "Absent"
#                 })

#         # Generate CSV
#         df = pd.DataFrame(data)
#         stream = io.StringIO()
#         df.to_csv(stream, index=False)
#         logging.debug(f"Attendance report generated for session {session_id}")
#         return StreamingResponse(
#             io.BytesIO(stream.getvalue().encode('utf-8')),
#             media_type="text/csv",
#             headers={"Content-Disposition": f"attachment; filename=attendance_report_{session_id}.csv"}
#         )
#     except Exception as e:
#         logging.error(f"Report error: {str(e)}")
#         raise HTTPException(status_code=400, detail=str(e))





























# from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session
# import io
# from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Base, engine
# from app.models import AdminLogin, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate
# from app.security import verify_password, create_access_token, get_current_admin
# from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv

# app = FastAPI(title="Authentikate Biometric UBa Exam Attendance System")

# # Create database tables
# Base.metadata.create_all(bind=engine)

# @app.post("/auth/login")
# async def login(admin: AdminLogin, db: Session = Depends(get_db)):
#     db_admin = db.query(Admin).filter(Admin.username == admin.username).first()
#     if not db_admin or not verify_password(admin.password, db_admin.password_hash):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#     token = create_access_token({"sub": admin.username})
#     return {"access_token": token, "token_type": "bearer"}

# @app.post("/enrollment/enroll")
# async def enroll_student(student: StudentCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate department and level
#         department = db.query(Department).filter(Department.department_id == student.department_id).first()
#         level = db.query(Level).filter(Level.level_id == student.level_id, Level.department_id == student.department_id).first()
#         if not department or not level:
#             raise HTTPException(status_code=400, detail="Invalid department or level")
#         if department.department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")

#         # Store fingerprint as base64 string
#         db_student = Student(
#             matriculation_number=student.matriculation_number,
#             name=student.name,
#             department_id=student.department_id,
#             level_id=student.level_id,
#             fingerprint_template=student.fingerprint_template  # No decoding
#         )
#         db.add(db_student)
#         db.commit()
#         return {"message": "Student enrolled successfully"}
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/enrollment/status")
# async def enrollment_status(request: EnrollmentStatusRequest, db: Session = Depends(get_db)):
#     try:
#         # Match fingerprint string
#         student = db.query(Student).filter(Student.fingerprint_template == request.fingerprint_template).first()
#         if not student:
#             raise HTTPException(status_code=404, detail="Student not found")

#         # Check course lists
#         enrolled_courses = db.query(CourseList, Course).join(Course, CourseList.course_id == Course.course_id).filter(
#             CourseList.matriculation_number == student.matriculation_number
#         ).all()
#         course_info = [
#             {"course_code": course.course_code, "course_name": course.course_name, "ca_mark": cl.ca_mark}
#             for cl, course in enrolled_courses
#         ]
#         return {
#             "matriculation_number": student.matriculation_number,
#             "name": student.name,
#             "department_id": student.department_id,
#             "level_id": student.level_id,
#             "enrolled_courses": course_info
#         }
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))



# @app.get("/enrollment/list/{department_id}/{level_id}")
# async def download_enrollment_list(department_id: int, level_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         if admin.department_id != department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")
#         students = db.query(Student).filter(
#             Student.department_id == department_id,
#             Student.level_id == level_id
#         ).all()
#         csv_content = generate_enrollment_list_csv(students, department_id, level_id)
#         return StreamingResponse(
#             io.BytesIO(csv_content.encode('utf-8')),
#             media_type="text/csv",
#             headers={"Content-Disposition": f"attachment; filename=enrollment_list_{department_id}_{level_id}.csv"}
#         )
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# #


# # @app.get("/enrollment/list/{department_id}/{level_id}")
# # async def download_enrollment_list(department_id: int, level_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
# #     try:
# #         if admin.department_id != department_id:
# #             raise HTTPException(status_code=403, detail="Not authorized for this department")
# #         students = db.query(Student).filter(
# #             Student.department_id == department_id,
# #             Student.level_id = level_id
# #         ).all()
# #         csv_content = generate_enrollment_list_csv(students, department_id, level_id)
# #         return StreamingResponse(
# #             io.BytesIO(csv_content.encode('utf-8')),
# #             media_type="text/csv",
# #             headers={"Content-Disposition": f"attachment; filename=enrollment_list_{department_id}_{level_id}.csv"}
# #         )
# #     except Exception as e:
# #         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/course/upload")
# async def upload_course_list(course_id: int, file: UploadFile = File(...), admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate course
#         course = db.query(Course).filter(Course.course_id == course_id).first()
#         if not course:
#             raise HTTPException(status_code=404, detail="Course not found")
#         if course.department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")

#         # Parse CSV
#         content = await file.read()
#         course_lists = parse_course_list_csv(content, course_id, db)
#         for cl in course_lists:
#             db_cl = CourseList(**cl)
#             db.add(db_cl)
#         db.commit()
#         return {"message": "Course list uploaded successfully"}
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=400, detail=str(e))

# @app.post("/session/")
# async def create_session(session: ExamSessionCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         # Validate course
#         course = db.query(Course).filter(Course.course_id == session.course_id).first()
#         if not course:
#             raise HTTPException(status_code=404, detail="Course not found")
#         if course.department_id != admin.department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")

#         db_session = ExamSession(
#             course_id=session.course_id,
#             admin_id=admin.admin_id,
#             start_time=session.start_time,
#             end_time=session.end_time
#         )
#         db.add(db_session)
#         db.commit()
#         return {"message": "Session created successfully", "session_id": db_session.session_id}
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=400, detail=str(e))


























