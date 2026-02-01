import flask
import sqlite3
from datetime import date
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@app.route("/")
def home():
    # Get the selected date from URL parameter, default to today
    selected_date = request.args.get("date", date.today().isoformat())
    
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return render_template("index.html", students=students, selected_date=selected_date)

@app.route("/add_student", methods=["POST"])
def add_student():
    name = request.form["name"]
    roll_no = request.form["roll_no"]

    conn = get_db_connection()

    try:
        conn.execute("INSERT INTO students (name, roll_no) VALUES (?, ?)", (name, roll_no))
        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return f"""
            <script>
                alert('Error: Roll number {roll_no} already exists!');
                window.location.href = '/';
            </script>
        """
    conn.close()

    return redirect("/")

@app.route("/mark_attendance/<int:student_id>/<status>")
def mark_attendance(student_id, status):
    # Get the selected date from URL parameter
    selected_date = request.args.get("date")
    
    # If no date provided or empty string, use today's date
    if not selected_date:
        selected_date = date.today().isoformat()
    
    # Check if the selected date is in the future
    if selected_date > date.today().isoformat():
        return f"""
               <script>
                    alert("Cannot Mark Attendance For Future Dates!");
                    window.location.href = '/?date={selected_date}';
                </script>
               """

    conn = get_db_connection()
    conn.execute(
        """INSERT INTO attendance (student_id, date, status)
           VALUES (?, ?, ?)
           ON CONFLICT(student_id, date)
           DO UPDATE SET status = excluded.status
        """,
        (student_id, selected_date, status)
    )
    conn.commit()
    conn.close()

    # Redirect back to home with the selected date
    return redirect(f"/?date={selected_date}")

@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/delete_attendance/<int:student_id>/<attendance_date>")
def delete_attendance(student_id, attendance_date):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM attendance WHERE student_id = ? AND date = ?",
        (student_id, attendance_date)
    )
    conn.commit()
    conn.close()
    return redirect("/attendance?date=" + attendance_date)

@app.route("/attendance")
def view_attendance():
    selected_date = request.args.get("date", date.today().isoformat())

    conn = get_db_connection()
    records = conn.execute("""
                           SELECT students.name, students.roll_no, students.id as student_id, 
                                  attendance.status, attendance.date
                           FROM attendance
                           JOIN students ON attendance.student_id = students.id
                           WHERE attendance.date = ?
                           ORDER BY students.name
                           """, (selected_date,)).fetchall()
    conn.close()
    return render_template("attendance.html", records=records, selected_date=selected_date)

@app.route("/summary")
def attendance_summary():
    conn = get_db_connection()

    summary = conn.execute("""
        SELECT 
            students.id,
            students.name,
            students.roll_no,
            COUNT(attendance.id) AS total_days,
            SUM(CASE WHEN attendance.status = 'present' THEN 1 ELSE 0 END) AS present_days
        FROM students
        LEFT JOIN attendance ON students.id = attendance.student_id
        GROUP BY students.id
        ORDER BY students.name
    """).fetchall()

    summary = [dict(s) for s in summary]  # convert sqlite Row → dict

    # 🔥 Attach attendance history to each student
    for s in summary:
        records = conn.execute("""
            SELECT date, status
            FROM attendance
            WHERE student_id = ?
            ORDER BY date DESC
        """, (s["id"],)).fetchall()

        s["attendance"] = records

    conn.close()
    return render_template("summary.html", summary=summary)

@app.route("/delete", methods=["GET"])
def delete_page():
    return render_template("delete.html")


@app.route("/delete", methods=["POST"])
def delete_by_name():
    name = request.form["name"].strip()
    conn = get_db_connection()

    student = conn.execute(
        "SELECT id FROM students WHERE LOWER(name) = LOWER(?)", (name,)
    ).fetchone()

    if student is None:
        conn.close()
        return """
            <script>
                alert("No student found with that name! Please try again.");
                window.location.href = '/';
            </script>
        """
    
    conn.execute("DELETE FROM students WHERE id = ?", (student["id"],))
    conn.commit()
    conn.close()

    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
