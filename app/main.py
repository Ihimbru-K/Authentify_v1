from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Base, engine
from app.models import AdminLogin, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate
from app.security import verify_password, create_access_token, get_current_admin
from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv

app = FastAPI(title="Biometric Attendance System")

# Create database tables
Base.metadata.create_all(bind=engine)

@app.post("/auth/login")
async def login(admin: AdminLogin, db: Session = Depends(get_db)):
    db_admin = db.query(Admin).filter(Admin.username == admin.username).first()
    if not db_admin or not verify_password(admin.password, db_admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": admin.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/enrollment/enroll")
async def enroll_student(student: StudentCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        # Validate department and level
        department = db.query(Department).filter(Department.department_id == student.department_id).first()
        level = db.query(Level).filter(Level.level_id == student.level_id, Level.department_id == student.department_id).first()
        if not department or not level:
            raise HTTPException(status_code=400, detail="Invalid department or level")
        if department.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")

        # Store fingerprint as base64 string
        db_student = Student(
            matriculation_number=student.matriculation_number,
            name=student.name,
            department_id=student.department_id,
            level_id=student.level_id,
            fingerprint_template=student.fingerprint_template  # No decoding
        )
        db.add(db_student)
        db.commit()
        return {"message": "Student enrolled successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/enrollment/status")
async def enrollment_status(request: EnrollmentStatusRequest, db: Session = Depends(get_db)):
    try:
        # Match fingerprint string
        student = db.query(Student).filter(Student.fingerprint_template == request.fingerprint_template).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Check course lists
        enrolled_courses = db.query(CourseList, Course).join(Course, CourseList.course_id == Course.course_id).filter(
            CourseList.matriculation_number == student.matriculation_number
        ).all()
        course_info = [
            {"course_code": course.course_code, "course_name": course.course_name, "ca_mark": cl.ca_mark}
            for cl, course in enrolled_courses
        ]
        return {
            "matriculation_number": student.matriculation_number,
            "name": student.name,
            "department_id": student.department_id,
            "level_id": student.level_id,
            "enrolled_courses": course_info
        }
    except Exception as e:
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
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=enrollment_list_{department_id}_{level_id}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




# @app.get("/enrollment/list/{department_id}/{level_id}")
# async def download_enrollment_list(department_id: int, level_id: int, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
#     try:
#         if admin.department_id != department_id:
#             raise HTTPException(status_code=403, detail="Not authorized for this department")
#         students = db.query(Student).filter(
#             Student.department_id == department_id,
#             Student.level_id = level_id
#         ).all()
#         csv_content = generate_enrollment_list_csv(students, department_id, level_id)
#         return StreamingResponse(
#             io.BytesIO(csv_content.encode('utf-8')),
#             media_type="text/csv",
#             headers={"Content-Disposition": f"attachment; filename=enrollment_list_{department_id}_{level_id}.csv"}
#         )
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

@app.post("/course/upload")
async def upload_course_list(course_id: int, file: UploadFile = File(...), admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        # Validate course
        course = db.query(Course).filter(Course.course_id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")

        # Parse CSV
        content = await file.read()
        course_lists = parse_course_list_csv(content, course_id, db)
        for cl in course_lists:
            db_cl = CourseList(**cl)
            db.add(db_cl)
        db.commit()
        return {"message": "Course list uploaded successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/session/")
async def create_session(session: ExamSessionCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        # Validate course
        course = db.query(Course).filter(Course.course_id == session.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.department_id != admin.department_id:
            raise HTTPException(status_code=403, detail="Not authorized for this department")

        db_session = ExamSession(
            course_id=session.course_id,
            admin_id=admin.admin_id,
            start_time=session.start_time,
            end_time=session.end_time
        )
        db.add(db_session)
        db.commit()
        return {"message": "Session created successfully", "session_id": db_session.session_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))





























# from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session
# import base64
# import io
# from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Base, engine
# from app.models import AdminLogin, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate
# from app.security import verify_password, create_access_token, get_current_admin
# from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv

# app = FastAPI(title="Biometric Attendance System")

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

#         # Placeholder: Fingerprint processing
#         fingerprint_data = base64.b64decode(student.fingerprint_template)
#         db_student = Student(
#             matriculation_number=student.matriculation_number,
#             name=student.name,
#             department_id=student.department_id,
#             level_id=student.level_id,
#             fingerprint_template=fingerprint_data
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
#         # Placeholder: Fingerprint matching
#         fingerprint_data = base64.b64decode(request.fingerprint_template)
#         student = db.query(Student).filter(Student.fingerprint_template == fingerprint_data).first()
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

   


  






















































# from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
# from fastapi.responses import StreamingResponse
# from sqlalchemy.orm import Session
# from app.models import get_db, Admin, Student, Department, Level, Course, CourseList, ExamSession, Base, engine
# from app.models import AdminLogin, StudentCreate, EnrollmentStatusRequest, ExamSessionCreate
# from app.security import verify_password, create_access_token, get_current_admin
# from app.csv_handler import generate_enrollment_list_csv, parse_course_list_csv

# app = FastAPI(title="Biometric Attendance System")

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

#         # Store fingerprint as string (base64 placeholder)
#         db_student = Student(
#             matriculation_number=student.matriculation_number,
#             name=student.name,
#             department_id=student.department_id,
#             level_id=student.level_id,
#             fingerprint_template=student.fingerprint_template
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
#         # Match fingerprint string (placeholder)
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