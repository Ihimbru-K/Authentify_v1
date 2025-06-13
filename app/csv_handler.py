import pandas as pd
import io
from fastapi import HTTPException

from app.models import Student
import logging

logging.basicConfig(level=logging.DEBUG)

def generate_enrollment_list_csv(students, department_id, level_id):
    if not students:
        raise HTTPException(status_code=404, detail="No students found")
    data = [
        {"matriculation_number": s.matriculation_number, "name": s.name}
        for s in students
    ]
    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    return stream.getvalue()




def parse_course_list_csv(content, course_id, db):
    df = pd.read_csv(io.BytesIO(content))
    required_columns = ["matriculation_number", "name", "ca_mark"]
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail="CSV missing required columns")
    
    logging.debug(f"CSV columns: {df.columns.tolist()}")
    logging.debug(f"CSV data: {df.to_dict(orient='records')}")
    
    course_lists = []
    for _, row in df.iterrows():
        matric = row["matriculation_number"]
        student = db.query(Student).filter(Student.matriculation_number == matric).first()
        logging.debug(f"Checking student {matric}: {'Found' if student else 'Not found'}")
        if student:
            ca_mark = row["ca_mark"]
            logging.debug(f"Raw ca_mark for {matric}: {ca_mark}, Type: {type(ca_mark)}")
            try:
                ca_mark_value = float(ca_mark) if pd.notna(ca_mark) else None
            except (ValueError, TypeError):
                logging.debug(f"Invalid ca_mark for {matric}: {ca_mark}")
                ca_mark_value = None
            course_lists.append({
                "course_id": course_id,
                "matriculation_number": matric,
                "ca_mark": ca_mark_value
            })
    logging.debug(f"Course lists to insert: {course_lists}")
    return course_lists
















# def parse_course_list_csv(content, course_id, db):
#     df = pd.read_csv(io.BytesIO(content))
#     required_columns = ["matriculation_number", "name", "ca_mark"]
#     if not all(col in df.columns for col in required_columns):
#         raise HTTPException(status_code=400, detail="CSV missing required columns")
    
#     course_lists = []
#     for _, row in df.iterrows():
#         student = db.query(Student).filter(Student.matriculation_number == row["matriculation_number"]).first()
#         if student:
#             course_lists.append({
#                 "course_id": course_id,
#                 "matriculation_number": row["matriculation_number"],
#                 "ca_mark": float(row["ca_mark"]) if pd.notna(row["ca_mark"]) else None
#             })
#     return course_lists