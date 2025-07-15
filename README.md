


# Authentikate UBa Biometric Exam Attendance System

## Overview

The Authentikate UBa Biometric Exam Attendance System is a FastAPI-based backend application designed to manage biometric authentication for exam attendance at a university. It supports admin registration, student enrollment, exam session management, attendance tracking via fingerprint authentication, and report generation. The system uses a PostgreSQL database and includes CSV handling for enrollment and course data.

## Table of Contents

- [Features](#features)
- [Technologies](#technologies)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Database Models](#database-models)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Features

- Admin registration and login with JWT authentication.
- Student enrollment with fingerprint templates and photos.
- Enrollment status checks via fingerprint.
- Exam session creation and management.
- Biometric attendance authentication with time window validation.
- CSV generation for enrollment lists and attendance/error reports.
- CA mark dispute reporting and error logging.

## Technologies

- Programming Language: Python
- Framework: FastAPI
- Database: PostgreSQL (via SQLAlchemy)
- Authentication: JWT with jose and passlib
- Data Handling: pandas for CSV processing
- Server: Uvicorn
- Containerization: Docker
- Dependencies: Managed via requirements.txt

## Installation

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- PostgreSQL
- Environment variables for configuration

### Steps

**Clone the Repository**

```bash
git clone https://github.com/Ihimbru-K/Authentikate_shipping_backend.git
cd Authentikate_shipping_backend
````

**Install Dependencies**

```bash
pip install -r requirements.txt
```

**Set Up Environment**

* Create a `.env` file with `DATABASE_URL`, `SECRET_KEY`, and `ALGORITHM` (see Configuration).

**Run with Docker**

```bash
docker-compose up --build
```

**Run Locally**

```bash
python main.py
```

## Configuration

### Environment Variables (`.env`)

* `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@localhost:5432/dbname`).
* `SECRET_KEY`: JWT secret key.
* `ALGORITHM`: JWT algorithm (e.g., `HS256`).
* `PORT`: Default port (8000, overridden by Railway if deployed).

**Default Port:** Set to `8000` in `main.py`, adjustable via environment variable `PORT`.

## API Endpoints

| Endpoint                                      | Method | Description                         | Authentication Required |
| --------------------------------------------- | ------ | ----------------------------------- | ----------------------- |
| `/auth/signup`                                | POST   | Register a new admin                | No                      |
| `/auth/login`                                 | POST   | Admin login to get JWT token        | No                      |
| `/enrollment/status`                          | POST   | Check student enrollment status     | Yes                     |
| `/enrollment/enroll`                          | POST   | Enroll a new student                | Yes                     |
| `/enrollment/list/{department_id}/{level_id}` | GET    | Download enrollment list as CSV     | Yes                     |
| `/course/upload`                              | POST   | Upload course list via CSV          | Yes                     |
| `/session/`                                   | POST   | Create a new exam session           | Yes                     |
| `/departments`                                | GET    | List all departments                | No                      |
| `/levels`                                     | GET    | List levels for admin's department  | Yes                     |
| `/courses`                                    | GET    | List courses for admin's department | Yes                     |
| `/sessions`                                   | GET    | List active sessions for admin      | Yes                     |
| `/attendance/authenticate`                    | POST   | Authenticate student attendance     | Yes                     |
| `/attendance/dispute`                         | POST   | Report CA mark dispute              | No                      |
| `/reports/attendance/{session_id}`            | GET    | Generate attendance report as CSV   | Yes                     |
| `/reports/errors/{session_id}`                | GET    | Generate error report as CSV        | Yes                     |

### Example Request: Admin Signup

```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin1", "password": "password123", "department_id": 1}'
```

### Example Response

```json
{
  "message": "Admin registered successfully",
  "access_token": "<jwt_token>",
  "token_type": "bearer"
}
```

## Database Models

* **University:** `university_id`, `name`
* **School:** `school_id`, `name`, `university_id`
* **Department:** `department_id`, `name`, `school_id`
* **Level:** `level_id`, `name`, `department_id`
* **Course:** `course_id`, `course_code`, `course_name`, `department_id`, `level_id`
* **Student:** `matriculation_number`, `name`, `department_id`, `level_id`, `photo`, `fingerprint_template`
* **CourseList:** `id`, `course_id`, `matriculation_number`, `ca_mark`
* **ExamSession:** `session_id`, `course_id`, `admin_id`, `start_time`, `end_time`
* **Attendance:** `id`, `session_id`, `matriculation_number`, `authenticated`, `timestamp`
* **ErrorLog:** `id`, `session_id`, `matriculation_number`, `error_type`, `details`, `timestamp`
* **Admin:** `admin_id`, `username`, `password_hash`, `department_id`

## Usage

### Start the Server

**Use Docker**

```bash
docker-compose up
```

**Or run locally**

```bash
python main.py
```

### API Interaction

Use tools like **Postman** or **cURL** with JWT tokens for authenticated endpoints.

### Monitoring

Logs are managed with Python’s `logging` module at DEBUG level.

## Contributing

* Fork the repository.
* ```bash
  git checkout -b feature/new-feature
  ```
* Commit changes.

  ```bash
  git commit -m "Add new feature"
  ```
* Push to the branch.

  ```bash
  git push origin feature/new-feature
  ```
* Open a Pull Request.

## License

No license file was provided; assume MIT unless otherwise specified.
