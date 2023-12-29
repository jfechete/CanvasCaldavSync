from canvasapi import Canvas
import caldav
import configargparse
import datetime

def main():
    options = get_options()
    canvas_user, caldav_calendar = get_connections(options)
    mark_completed_todos(options, canvas_user, caldav_calendar)
    add_canvas_todo(options, canvas_user, caldav_calendar)

def get_connections(options):
    canvas = Canvas(options.canvas_url, options.canvas_api_key)
    canvas_user = canvas.get_user(options.canvas_user_id)
    caldav_client = caldav.DAVClient(
        options.caldav_url,
        username=options.caldav_user, password=options.caldav_password
    )
    caldav_calendar = caldav_client.calendar(url=options.caldav_calendar_url)
    return canvas_user, caldav_calendar

def mark_completed_todos(options, canvas_user, caldav_calendar):
    for todo in caldav_calendar.todos():
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
            print(assignment_id)

def add_canvas_todo(options, canvas_user, caldav_calendar):
    upcoming_assigments = []
    #looks like rate-limit is designed to allow sequential use,
    #so since there's no multi-threading, no need to worry about it.
    #https://canvas.instructure.com/doc/api/file.throttling.html
    for course in canvas_user.get_courses(enrollment_state="active"):
        for assignment in course.get_assignments():
            has_due = assignment.due_at != None
            if has_due:
                due = datetime.datetime.strptime(
                    assignment.due_at,
                    "%Y-%m-%dT%H:%M:%SZ"
                )+datetime.timedelta(hours=options.timezone_offset)

            if (
                (has_due and (
                    (due-datetime.datetime.now()).days <= options.look_ahead
                )) or
                (not has_due and options.no_due)
            ):
                submission = assignment.get_submission(canvas_user)
                completed = submission.attempt != None
                if not completed:
                    upcoming_assigments.append({
                        "name":assignment.name,
                        "id":assignment.id,
                        "due":due,
                    })
    print(upcoming_assigments)

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
        "--canvas-api-key", required=True,
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
        "--caldav-password", required=True,
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
        "--timezone-offset", type=int, default=0,
        help="How many hours to offset from due date to account for timezone"
    )
    return parser.parse_args()

if __name__ == "__main__":
    main()
