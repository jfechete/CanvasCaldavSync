from canvasapi import Canvas
import caldav
import configargparse
import datetime
import pytz
import os

SYSTEMD_CRED_VARIABLE = "CREDENTIALS_DIRECTORY"
CANVAS_API_KEY_CRED = "canvas-api-key"
CALDAV_PASSWORD_CRED = "caldav-password"

def main():
    options = get_options()
    canvas_user, caldav_calendar = get_connections(options)
    assignment_todos = get_assignment_todos(
        options, canvas_user, caldav_calendar
    )
    add_upcoming_assignments(
        options, canvas_user, caldav_calendar, assignment_todos
    )
    update_existing_assignments(options, canvas_user, assignment_todos)

def get_connections(options):
    canvas = Canvas(options.canvas_url, options.canvas_api_key)
    canvas_user = canvas.get_user(options.canvas_user_id)
    caldav_client = caldav.DAVClient(
        options.caldav_url,
        username=options.caldav_user, password=options.caldav_password
    )
    caldav_calendar = caldav_client.calendar(url=options.caldav_calendar_url)
    return canvas_user, caldav_calendar

def get_assignment_todos(options, canvas_user, caldav_calendar):
    assignment_todos = {}
    for todo in caldav_calendar.todos(include_completed=True):
        if (
            "CATEGORIES" in todo.icalendar_component and
            options.category in todo.icalendar_component["CATEGORIES"].cats
        ):
            id_line = todo.icalendar_component["DESCRIPTION"].split("\n")[0]
            if not id_line.startswith(options.description_id_prefix):
                raise ValueError("Invalid first line for todo {}".format(
                    todo.icalendar_component["SUMMARY"]
                ))
            assignment_id = id_line[len(options.description_id_prefix):]
            assignment_todos[assignment_id] = todo
    return assignment_todos

def add_upcoming_assignments(
    options, canvas_user, caldav_calendar, assignment_todos
):
    upcoming_assigments = []
    now = datetime.datetime.now()
    if options.timezone != None:
        now = now.astimezone(pytz.timezone(options.timezone))
    #looks like rate-limit is designed to allow sequential use,
    #so since there's no multi-threading, no need to worry about it.
    #https://canvas.instructure.com/doc/api/file.throttling.html
    for course in canvas_user.get_courses(enrollment_state="active"):
        for assignment in course.get_assignments():
            assignment_id = "{}:{}".format(course.id, assignment.id)
            if assignment_id in assignment_todos:
                continue

            due = get_due_date(options, assignment)

            if (
                (due != None and (
                    (due-now).days <= options.look_ahead
                )) or
                (due == None and options.no_due)
            ):
                new_todo = caldav_calendar.save_todo(
                    summary=assignment.name, due=due,
                    categories=[options.category],
                    description="{}{}\nCourse: {}".format(
                        options.description_id_prefix, assignment_id,
                        course.name
                    )
                )
                assignment_todos[assignment_id] = new_todo

def update_existing_assignments(options, canvas_user, assignment_todos):
    courses = {}
    for course in canvas_user.get_courses(enrollment_state="active"):
        courses[course.id] = course

    for assignment_id, assignment_todo in assignment_todos.items():
        if (
            "STATUS" in assignment_todo.icalendar_component and
            assignment_todo.icalendar_component["STATUS"] == "COMPLETED"
        ):
            continue

        course_id, assignment_id = assignment_id.split(":")
        assignment = courses[int(course_id)].get_assignment(
            int(assignment_id)
        )

        due = get_due_date(options, assignment)
        if due != assignment_todo.icalendar_component["DUE"].dt:
            assignment_todo.icalendar_component["DUE"].dt = due
            assignment_todo.save()

        completed = assignment.get_submission(canvas_user).attempt != None
        if completed:
            assignment_todo.complete()

def get_due_date(options, assignment):
    due = assignment.due_at
    if due != None:
        due = datetime.datetime.strptime(
            due,
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if options.timezone != None:
            due = due.replace(tzinfo=pytz.utc).astimezone(
                pytz.timezone(options.timezone)
            )
        if due.hour <= options.fallback_hour:
            due -= datetime.timedelta(days=1)
            due = due.replace(hour=23, minute=59)
    return due

def get_options():
    parser = configargparse.ArgParser(
        default_config_files=["~/.config/canvas_caldav_sync"]
    )
    parser.add_argument(
        "-c", "--config", is_config_file=True,
        help="Use an alternate config file"
    )
    parser.add_argument(
        "--canvas-url", required=True,
        help="The canvas url to connect to"
    )
    parser.add_argument(
        "--canvas-user-id", required=True,
        help="The canvas user to read courses/assignments for"
    )
    parser.add_argument(
        "--canvas-api-key",
        help="The canvas api key to use"
    )
    parser.add_argument(
        "--caldav-url", required=True,
        help="The url of the caldav server"
    )
    parser.add_argument(
        "--caldav-user", required=True,
        help="The caldav user"
    )
    parser.add_argument(
        "--caldav-password",
        help="The caldav password"
    )
    parser.add_argument(
        "--caldav-calendar-url", required=True,
        help="The url of the caldav calendar to read todos from"
    )
    parser.add_argument(
        "--description-id-prefix", default="assignment-id: ",
        help=(
            "What the prefix should be for the first line of todo description"
            " (Make sure to not edit the first line of a description, "
            "because it gets parsed when checking if the assignment is done)"
        )
    )
    parser.add_argument(
        "--category", default="canvas-assignment",
        help="What category to use to mark canvas assignments"
    )
    parser.add_argument(
        "--look-ahead", type=int, default=14,
        help="How many days ahead an assignment can be due to be added"
    )
    parser.add_argument(
        "--no-due", action="store_true",
        help="Include assignments with no due date"
    )
    parser.add_argument(
        "--timezone",
        help="What timezone to convert due date to"
    )
    parser.add_argument(
        "--fallback-hour", type=int, default=-1,
        help=(
            "If due on or before this hour, "
            "set due date back to previous day right before midnight"
        )
    )

    args = parser.parse_args()
    cred_folder = os.getenv(SYSTEMD_CRED_VARIABLE)
    if cred_folder is not None:
        canvas_api_key_file = os.path.join(cred_folder, CANVAS_API_KEY_CRED)
        caldav_password_file = os.path.join(cred_folder, CALDAV_PASSWORD_CRED)
        if os.path.isfile(canvas_api_key_file):
            with open(canvas_api_key_file) as fb:
                args.canvas_api_key = fb.read()
        if os.path.isfile(caldav_password_file):
            with open(caldav_password_file) as fb:
                args.caldav_password = fb.read()
    if args.canvas_api_key is None:
        raise ValueError("No canvas api key provided")
    if args.caldav_password is None:
        raise ValueError("No caldav password provided")

    return args

if __name__ == "__main__":
    main()
