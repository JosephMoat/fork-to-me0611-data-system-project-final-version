from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.student import Student
from app.models.student_course_record import StudentCourseRecord
from app.models.user import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_STUDENT_ID = "110306078"
DEMO_STUDENT_NAME = "聖結石"
SOURCE_STUDENT_ID = "111001001"
DEMO_PASSWORD = "password123"


def ensure_demo_account():
    db: Session = SessionLocal()
    try:
        student = db.query(Student).filter(Student.student_id == DEMO_STUDENT_ID).first()
        if student is None:
            db.add(
                Student(
                    student_id=DEMO_STUDENT_ID,
                    name=DEMO_STUDENT_NAME,
                    admission_year=111,
                    department="資訊科學系",
                )
            )
            print(f"Demo student {DEMO_STUDENT_ID} created.")

        user = db.query(User).filter(User.username == DEMO_STUDENT_ID).first()
        if user is None:
            db.add(
                User(
                    student_id=DEMO_STUDENT_ID,
                    username=DEMO_STUDENT_ID,
                    password_hash=pwd_context.hash(DEMO_PASSWORD),
                )
            )
            print(f"Demo user {DEMO_STUDENT_ID} created.")

        existing_records = db.query(StudentCourseRecord).filter(
            StudentCourseRecord.student_id == DEMO_STUDENT_ID
        ).count()

        if existing_records == 0:
            source_records = db.query(StudentCourseRecord).filter(
                StudentCourseRecord.student_id == SOURCE_STUDENT_ID
            ).all()
            for record in source_records:
                db.add(
                    StudentCourseRecord(
                        student_id=DEMO_STUDENT_ID,
                        course_id=record.course_id,
                        semester=record.semester,
                        grade=record.grade,
                        is_passed=record.is_passed,
                    )
                )
            print(f"Copied {len(source_records)} demo course records from {SOURCE_STUDENT_ID}.")

        db.commit()
        print("Demo account check completed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    ensure_demo_account()
