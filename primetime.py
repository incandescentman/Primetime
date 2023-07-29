import pyperclip
from ics import Calendar, Event
from dateutil.parser import parse
from datetime import timedelta
import re
import sys
import tty
import termios
import subprocess
import platform
from termcolor import colored

# Function to get a single character input
def get_ch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# Get clipboard data and split into lines
data = pyperclip.paste().split('\n')

# If clipboard data doesn't seem to contain a valid schedule, ask for input
if not any(re.match(r'\d+(:\d+)?(am|pm)', line, flags=re.IGNORECASE) for line in data):
    print("Please paste your schedule (then press RETURN twice):")
    data = []
    while True:
        line = input()
        if line:
            data.append(line)
        else:
            break

# Create a new calendar
c = Calendar()
events = []





# Process each line of the clipboard data
last_am_pm = None
for item in data:
    # Remove leading and trailing white space
    item = item.strip()

    # If the line doesn't start with a time, ignore it
    if not re.match(r'\d+', item):
        continue

    # Remove any hyphens from the line
    item = item.replace('-', '').strip()

    # Extract time and am/pm part
    match = re.search(r'(\d+:\d+|\d+)\s*(am|pm)?', item, flags=re.IGNORECASE)
    if match:
        time_part = match.group(1)
        am_pm_part = match.group(2)
        if am_pm_part is None:
            if last_am_pm is not None:
                am_pm_part = last_am_pm
            else:
                raise ValueError('The first time must specify AM or PM.')
        else:
            # Extract the AM/PM part for future reference
            last_am_pm = 'am' if 'am' in am_pm_part.lower() else 'pm'

        start_time = parse(time_part + am_pm_part + " EDT")  # adjust the timezone here

        # Remove the matched time and am/pm part from the item
        item = item[match.end():].strip()
    else:
        raise ValueError(f"Unable to parse time from: {item}")



    # If the time is "12:00am", add one day to the date
    if time_part == '12:00am':
        start_time += timedelta(days=1)

    # The last part might be the duration, or it might be part of the title
    try:
        # Updated this regex to match an integer followed by the word "minutes" or "hour"
        duration = re.search(r'(\d+)\s*(minutes|hour)', item)
        duration_val = int(duration.group(1))
        duration_type = 'hour' if 'hour' in duration.group(2) else 'minutes'
        duration = duration_val * (60 if duration_type == 'hour' else 1)

        # Do the replacement based on the duration type
        if duration_type == 'hour':
            title = item.replace('for ' + str(duration_val) + ' ' + duration_type, '').strip()
        else:
            title = item.replace('for ' + str(duration_val) + ' ' + duration_type, '').strip()
    except (ValueError, AttributeError):
        # If it's not a duration, it's part of the title
        duration = None
        title = item.strip()

    # Create a new event and add it to the list
    e = Event()
    e.name = title
    e.begin = start_time
    e.duration_minutes = duration
    events.append(e)

# Sort events by start time
events.sort(key=lambda e: e.begin)

# Process the events to set the end times and add them to the calendar
for i, event in enumerate(events):
    # If a duration was given, use it to calculate the end time
    if event.duration_minutes is not None:
        event.duration = timedelta(minutes=event.duration_minutes)
    # Otherwise, if there's a next event, set the end time to 10 minutes before it
    elif i < len(events) - 1:
        event.duration = max(events[i+1].begin - event.begin - timedelta(minutes=10), timedelta(minutes=1))
    # If it's the last event and no duration was given, just set it to end at the next hour
    else:
        event.duration = timedelta(hours=1)

    # Add the event to the calendar after all modifications
    c.events.add(event)

# Display the proposed schedule
print("Here's your proposed schedule:")

# Sort the events by start time
sorted_events = sorted(c.events, key=lambda e: e.begin)

# Find the maximum length of the event names for alignment
max_length = max([len(event.name) for event in sorted_events])

# Display the sorted events
for event in sorted_events:
    total_minutes = event.duration.total_seconds() / 60
    hours, minutes = divmod(total_minutes, 60)
    # Format the duration
    if hours:
        duration_str = f"{int(hours)} hour{'s' if hours > 1 else ''}"
        if minutes > 0:
            duration_str += f" {int(minutes)} minute{'s' if minutes > 1 else ''}"
    else:
        duration_str = f"{int(minutes)} minute{'s' if minutes > 1 else ''}"
    time_str = event.begin.strftime('%-I:%M%p')
    # Add a leading space to the hour part of the time if it's one digit
    hour, rest = time_str.split(':')
    time_str = (' ' + hour if len(hour) < 2 else hour) + ':' + rest
    title_str = event.name.ljust(max_length)
    print(colored(time_str, 'white') + ": " + colored(title_str, 'green') + " " + colored(duration_str, 'red'))

# Ask the user to confirm
print("\nDoes the schedule look good? (y/N) ")

# Get a single character input
confirm = get_ch()

# If the user confirms, write the calendar to a .ics file and open it
if confirm.lower() in ["", "y"]:
    with open('timeblocking.ics', 'w') as my_file:
        my_file.writelines(c)
    print("\nICS file has been created")

    # Check the platform and open the file with the default application
    if platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', 'timeblocking.ics'))
    elif platform.system() == 'Windows':  # Windows
        subprocess.call(('start', 'timeblocking.ics'), shell=True)
    else:  # linux variants
        subprocess.call(('xdg-open', 'timeblocking.ics'))

else:
    print("\nSchedule not confirmed, exiting without creating ICS file.")
