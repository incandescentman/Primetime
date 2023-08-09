import pyperclip
from ics import Calendar, Event
from dateutil.parser import parse
from datetime import datetime, timedelta
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
if not any(re.match(r'\d+(:\d+)?(am|pm)|noon|midnight', line, flags=re.IGNORECASE) for line in data):
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
current_time = datetime.now()
next_day = False

# Initialize previous_time with the time of the first event
time_string = re.search(r'(\d+:\d+|\d+|noon|midnight)(am|pm)?', data[0], flags=re.IGNORECASE).group()
if "noon" in time_string.lower():
    time_string = "12:00pm"
elif "midnight" in time_string.lower():
    time_string = "12:00am"
previous_time = parse(time_string + " EDT")  # adjust the timezone here

for item in data:
    # Remove leading and trailing white space
    item = item.strip()

    # If the line doesn't start with a time, ignore it
    if not re.match(r'\d+|noon|midnight', item):
        continue

    # Remove any hyphens from the line
    item = item.replace('-', '').strip()

    # Extract time and am/pm part
    match = re.search(r'(\d+:\d+|\d+|noon|midnight)(am|pm)?', item, flags=re.IGNORECASE)
    if match:
        time_part = match.group(1)
        am_pm_part = match.group(2)
        if am_pm_part is None and time_part.lower() not in ['noon', 'midnight']:
            if last_am_pm is not None:
                am_pm_part = last_am_pm
            else:
                raise ValueError('The first time must specify AM or PM.')
        elif am_pm_part is not None:
            # Extract the AM/PM part for future reference
            last_am_pm = 'am' if 'am' in am_pm_part.lower() else 'pm'
            if last_am_pm == 'am' and 'pm' in am_pm_part.lower():
                next_day = True

        if time_part.lower() == 'noon':
            start_time = parse('12:00pm EDT')  # adjust the timezone here
        elif time_part.lower() == 'midnight':
            start_time = parse('12:00am EDT')  # adjust the timezone here
            next_day = True
        else:
            start_time = parse(time_part + am_pm_part + " EDT")  # adjust the timezone here
            if next_day and 'am' in am_pm_part.lower():
                start_time += timedelta(days=1)

        # If the start time is before the previous time, add a day
        if start_time < previous_time:
            start_time += timedelta(days=1)

        # Update previous_time
        previous_time = start_time

        # Remove the matched time and am/pm part from the item
        item = item[match.end():].strip()
    else:
        raise ValueError(f"Unable to parse time from: {item}")



    # The last part might be the duration, or it might be part of the title
    try:
        # Updated this regex to match an integer followed by the word "minutes", "hour", or pomodoro variations
        duration_match = re.search(r'(\d+)\s*(minutes|hour|pomodoro|pomodori|pomodoros|pom|poms|pomo|pomos)', item)
        duration_val = int(duration_match.group(1))
        duration_type = duration_match.group(2)
        if duration_type in ['pomodoro', 'pomodori', 'pomodoros', 'pom', 'poms', 'pomo', 'pomos']:
            duration = duration_val * 30
        else:
            duration = duration_val * (60 if duration_type == 'hour' else 1)

        # Do the replacement based on the duration type
        title = item.replace('for ' + str(duration_val) + ' ' + duration_type, '').strip()
    except (ValueError, AttributeError):
        # If it's not a duration, it's part of the title
        duration = None
        title = item.strip()

    # ...





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

# Sort the events by start time
sorted_events = sorted(c.events, key=lambda e: e.begin)

# Find the maximum length of the event names for alignment
max_length = max([len(event.name) for event in sorted_events])

# Display the sorted events
print("Here's your proposed schedule:")
current_day = sorted_events[0].begin.date()
next_day_flag = False
next_day_start_time = parse('4:00am EDT') + timedelta(days=1)  # adjust the timezone here
for event in sorted_events:
    # Check if the event is on the next day
    if event.begin >= next_day_start_time and not next_day_flag:
        print("\n" + colored("### TOMORROW:", 'white'))
        next_day_flag = True

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
    print(colored(time_str, 'white') + "  " + colored(title_str, 'green') + "  " + colored(duration_str, 'red'))

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
