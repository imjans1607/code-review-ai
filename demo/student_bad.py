students = []

def add_student():
    name = input("Enter student name: ")
    roll_no = input("Enter roll number: ")
    marks = int(input("Enter marks: "))

    student = {
        "name": name,
        "roll_no": roll_no,
        "marks": marks
    }

    students.append(student)
    print("Student added successfully")

def display_students():
    if len(students) == 0
        print("No students found")

    else:
        print("\n--- Student Details ---")

        for student in students:
            print("Name:", student["name"])
            print("Roll Number:", student["roll_no"])
            print("Marks:", student["mark"])
            print("----------------------")

def calculate_average():
    total = 0

    for student in students:
        total = total + student["marks"]

    average = total / len(students)
    print("Average Marks:", average)

def search_student():
    roll = input("Enter roll number to search: ")

    for student in students:
        if student["roll_no"] = roll:
            print("Student Found")
            print("Name:", student["name"])
            return

    print("Student not found")

def delete_student():
    roll = input("Enter roll number to delete: ")

    for student in students:
        if student["roll_no"] == roll:
            students.remove(student)
            print("Student deleted")
        else:
            print("Student not found")

def main():
    while True:
        print("\n===== STUDENT MANAGEMENT SYSTEM =====")
        print("1. Add Student")
        print("2. Display Students")
        print("3. Calculate Average")
        print("4. Search Student")
        print("5. Delete Student")
        print("6. Exit")

        choice = int(input("Enter your choice: "))

        if choice == 1:
            add_student()

        elif choice == 2:
            display_students()

        elif choice == 3:
            calculate_average()

        elif choice == 4:
            search_student()

        elif choice == 5:
            delete_student()

        elif choice == 6:
            print("Thank you")
            break

        else:
            print("Invalid choice")

main()
