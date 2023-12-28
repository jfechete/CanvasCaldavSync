from canvasapi import Canvas
import configargparse
import datetime

def main():
    options = get_options()
    add_canvas_todo(options)

def add_canvas_todo(options):
    canvas = Canvas(options.canvas_url, options.canvas_api_key)
    user = canvas.get_user(options.canvas_user_id)
    upcoming_assigments = []
    #looks like rate-limit is designed to allow sequential use,
    #so since there's no multi-threading, no need to worry about it.
    #https://canvas.instructure.com/doc/api/file.throttling.html
    for course in user.get_courses(enrollment_state="active"):
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
                submission = assignment.get_submission(user)
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
        "--canvas-api-key", required=True,
        help="The canvas api key to use"
    )
    parser.add_argument(
        "--canvas-user-id", required=True,
        help="The canvas user to read courses/assignments for"
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
