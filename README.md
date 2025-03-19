# canvas_caldav_sync
A simple script I made to sync assignments from the Canvas LMS to a CalDAV todo list.  
It's meant to be run as a cron job or systemd timer or similar.  
When ran, it checks for any upcoming assignments and adds them to the todo list if it isn't there already, and then checks every assignment in the todo list and marks them as completed if they have a submission on canvas.  
Options are available when running with --help.  
Uses [ConfigArgParse](https://pypi.org/project/ConfigArgParse/), so can use .config/canvas_caldav_sync, environment variables, or command line options.  
Also supports systemd-creds using `canvas-api-key` and `caldav-password`
