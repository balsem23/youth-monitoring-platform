import csv
import io
import json
from datetime import datetime
from django.core.exceptions import ValidationError
from .models import Student, DataIngestionLog, AuditLog

def ingest_students_csv(file_obj, file_name, user):
    """
    Ingests a CSV file of students, validates each row, and updates/creates Student records.
    Returns a dictionary with success/error statistics and list of error messages.
    """
    errors_list = []
    accepted_count = 0
    rejected_count = 0
    total_count = 0

    try:
        # Read file contents and decode to string
        file_content = file_obj.read()
        if isinstance(file_content, bytes):
            try:
                decoded_content = file_content.decode('utf-8-sig') # handle BOM if present
            except UnicodeDecodeError:
                decoded_content = file_content.decode('latin-1')
        else:
            decoded_content = file_content

        csv_file = io.StringIO(decoded_content)
        reader = csv.reader(csv_file)
        
        # Read header
        try:
            header = next(reader)
        except StopIteration:
            raise ValidationError("The CSV file is empty.")

        # Clean header columns (strip spaces, lower case)
        header = [col.strip().lower() for col in header]
        
        required_cols = ['first_name', 'last_name', 'date_of_birth', 'attendance_rate', 'average_grade']
        missing_cols = [col for col in required_cols if col not in header]
        
        if missing_cols:
            error_msg = f"Missing required columns in CSV header: {', '.join(missing_cols)}"
            # Log failure in AuditLog
            AuditLog.objects.create(
                user=user,
                user_role=user.profile.role if hasattr(user, 'profile') else 'ADMIN',
                action_type='INGESTION',
                action_result='FAILURE',
                description=f"CSV upload failed for {file_name}: {error_msg}"
            )
            raise ValidationError(error_msg)

        # Map header columns to their indices
        col_indices = {col: header.index(col) for col in required_cols}

        # Process each row
        for row_num, row in enumerate(reader, start=2): # Header is row 1
            if not row:
                continue # Skip empty rows
            
            total_count += 1
            
            # Check row length
            if len(row) < len(header):
                errors_list.append(f"Row {row_num}: Row has fewer fields than the header.")
                rejected_count += 1
                continue

            # Extract fields
            first_name = row[col_indices['first_name']].strip()
            last_name = row[col_indices['last_name']].strip()
            dob_str = row[col_indices['date_of_birth']].strip()
            attendance_str = row[col_indices['attendance_rate']].strip()
            grade_str = row[col_indices['average_grade']].strip()

            row_errors = []

            # Validate non-empty names
            if not first_name:
                row_errors.append("First name is empty.")
            if not last_name:
                row_errors.append("Last name is empty.")

            # Validate date of birth (YYYY-MM-DD)
            dob = None
            if not dob_str:
                row_errors.append("Date of birth is empty.")
            else:
                try:
                    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                except ValueError:
                    row_errors.append(f"Invalid date format '{dob_str}'. Must be YYYY-MM-DD.")

            # Validate attendance rate (0 to 100)
            attendance_rate = None
            if not attendance_str:
                row_errors.append("Attendance rate is empty.")
            else:
                try:
                    attendance_rate = float(attendance_str)
                    if not (0 <= attendance_rate <= 100):
                        row_errors.append(f"Attendance rate {attendance_rate} must be between 0 and 100.")
                except ValueError:
                    row_errors.append(f"Invalid attendance rate '{attendance_str}'. Must be a number.")

            # Validate average grade (must be non-negative float)
            average_grade = None
            if not grade_str:
                row_errors.append("Average grade is empty.")
            else:
                try:
                    average_grade = float(grade_str)
                    if average_grade < 0 or average_grade > 100:
                        row_errors.append(f"Average grade {average_grade} must be between 0 and 100.")
                except ValueError:
                    row_errors.append(f"Invalid average grade '{grade_str}'. Must be a number.")

            if row_errors:
                errors_list.append(f"Row {row_num}: {', '.join(row_errors)}")
                rejected_count += 1
            else:
                # Update or create Student
                Student.objects.update_or_create(
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=dob,
                    defaults={
                        'attendance_rate': attendance_rate,
                        'average_grade': average_grade,
                    }
                )
                accepted_count += 1

    except ValidationError as ve:
        raise ve
    except Exception as e:
        error_msg = f"System error processing CSV: {str(e)}"
        raise ValidationError(error_msg)

    # Save DataIngestionLog
    log = DataIngestionLog.objects.create(
        user=user,
        file_name=file_name,
        total_rows=total_count,
        accepted_rows=accepted_count,
        rejected_rows=rejected_count,
        errors="\n".join(errors_list)
    )

    # Save AuditLog entry
    AuditLog.objects.create(
        user=user,
        user_role=user.profile.role if hasattr(user, 'profile') else 'ADMIN',
        action_type='INGESTION',
        action_result='SUCCESS',
        description=f"CSV upload finished for {file_name}. Accepted: {accepted_count}, Rejected: {rejected_count}."
    )

    return {
        'total': total_count,
        'accepted': accepted_count,
        'rejected': rejected_count,
        'errors': errors_list,
        'log_id': log.id
    }
