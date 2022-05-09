from os import environ as env
from datetime import datetime, timedelta
from time import sleep
import os
import argparse

from telethon import TelegramClient


api_id = env['TG_API_ID']
api_hash = env['TG_API_HASH']
bot_token = env['TG_BOT_TOKEN_ELIS']
client = TelegramClient('anon', api_id, api_hash).start(bot_token=bot_token)

log_file = '/var/log/snort/alert.fast'
data = {}
events = dict()

parser = argparse.ArgumentParser()
parser.add_argument('-u', '--username', required=True,
                    help="Telegram username")
parser.add_argument('-s', '--sleep', default=2, type=int,
                    help='Bot sleep time in seconds')
args = parser.parse_args()

tg_username = args.username
bot_sleep = args.sleep


def parse_datetime(date_str):
    date = datetime.strptime(date_str, "%d/%m/%y-%H:%M:%S.%f")
    formatted_date = date.strftime("%d-%m-%Y")
    formatted_time = date.strftime("%H:%M:%S")
    return {
        'date': formatted_date,
        'time': formatted_time
    }


def get_last_byte():
    with open(log_file) as f:
        f.seek(0, os.SEEK_END)
        return f.tell()


def read_new_data():
    with open(log_file) as f:
        f.seek(data['last_byte'])
        return f.readlines()


def build_message(event):
    msg_str = (
        f"Date: {event['date']}\n"
        f"Event: {event['name']}\n"
        f"      - Start time: {event['start_time']}\n"
        f"      - Stop time: {event['stop_time']}\n"
        f"Sources:\n"
    )

    for source in event['sources']:
        msg_str += f"      - {source}\n"

    msg_str += f"Hits: {event['hits']}\n"
    return msg_str


def is_event_recent(last_occurance, new_occurance):
    _last_occurance = datetime.strptime(last_occurance, "%d-%m-%Y %H:%M:%S")
    _new_occurance = datetime.strptime(new_occurance, "%d-%m-%Y %H:%M:%S")
    delta = timedelta(minutes=5)
    return (_new_occurance - _last_occurance) <= delta


def populate_new_event(event, parsed_datetime, source):
    events[event] = {
        'msg_id': None,
        'date': parsed_datetime['date'],
        'name': event,
        'start_time': parsed_datetime['time'],
        'stop_time': parsed_datetime['time'],
        'sources': [source],
        'hits': 1,
    }


async def main():
    data['last_byte'] = get_last_byte()
    data['time_start'] = datetime.now()

    while True:
        sleep(bot_sleep)

        last_byte = get_last_byte()

        if last_byte == data['last_byte']:
            pass

        else:
            new_data = read_new_data()
            for alert in new_data:
                alert_parts = alert.split()

                parsed_datetime = parse_datetime(alert_parts[0])
                event = alert_parts[3].strip()
                source = alert_parts[8].split(':')[0]

                if event not in events:
                    populate_new_event(event, parsed_datetime, source)
                    msg_str = build_message(events[event])
                    msg = await client.send_message(tg_username, msg_str)
                    events[event]['msg_id'] = msg.id

                else:
                    last_occurance = f"{events[event]['date']} {events[event]['stop_time']}"
                    new_occurance = " ".join(parsed_datetime.values())

                    if is_event_recent(last_occurance, new_occurance):
                        events[event]['hits'] += 1
                        events[event]['stop_time'] = parsed_datetime['time']

                        if source not in events[event]['sources']:
                            events[event]['sources'].append(source)

                        msg_str = build_message(events[event])
                        await client.edit_message(tg_username, events[event]['msg_id'], msg_str)

                    else:
                        populate_new_event(event, parsed_datetime, source)
                        msg_str = build_message(events[event])
                        msg = await client.send_message(tg_username, msg_str)
                        events[event]['msg_id'] = msg.id

                data['last_byte'] = last_byte


with client:
    client.loop.run_until_complete(main())
