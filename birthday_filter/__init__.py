import configparser
import json
import re
import shutil
import subprocess
from typing import Any

import birthday_filter.config as cfg


def log(msg):
    print(f"[birthday-filter] {msg}")


def format_vd_cfg(o: dict) -> dict:
    def recurse(o: Any) -> dict | str:
        if isinstance(o, dict):
            return {k: recurse(v) for k, v in o.items()}
        return json.dumps(o)

    return {k: recurse(v) for k, v in o.items()}


def main():
    log("Doing initial setup")
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Create one directory to read the cards (it is read-only) and
    # then two directories to read and write the calendar (it is
    # read-write).
    card_dir = cfg.DATA_DIR / "vdirsyncer-cards"
    cal_dir = cfg.DATA_DIR / "vdirsyncer-cal"
    vd_cfg_file = cfg.DATA_DIR / "vdirsyncer-config"
    vd_status_file = cfg.DATA_DIR / "vdirsyncer-status"
    vd_cfg = configparser.ConfigParser()
    vd_cfg.update(
        format_vd_cfg(
            {
                "general": {
                    "status_path": str(vd_status_file),
                },
                "storage cards": {
                    "type": "filesystem",
                    "path": str(card_dir),
                    "fileext": ".vcf",
                },
                "storage cal": {
                    "type": "filesystem",
                    "path": str(cal_dir),
                    "fileext": ".ics",
                },
                "storage carddav": {
                    "type": "carddav",
                    "url": cfg.CARDDAV.url,
                    "username": cfg.CARDDAV.username,
                    "password": cfg.CARDDAV.password,
                    "read_only": True,
                },
                "storage caldav": {
                    "type": "caldav",
                    "url": cfg.CALDAV.url,
                    "username": cfg.CALDAV.username,
                    "password": cfg.CALDAV.password,
                },
                "pair card_download": {
                    "a": "cards",
                    "b": "carddav",
                    "collections": ["from b"],
                    "conflict_resolution": "b wins",
                },
                "pair cal_upload": {
                    "a": "cal",
                    "b": "caldav",
                    "collections": [cfg.BIRTHDAY_CALENDAR_ID],
                    "conflict_resolution": "a wins",
                },
            }
        ),
    )
    with open(vd_cfg_file, "w") as f:
        vd_cfg.write(f)
    (card_dir / "Default").mkdir(parents=True, exist_ok=True)
    log("Running vdirsyncer to download cards")
    run_vd = lambda *args: subprocess.run(
        ["vdirsyncer", f"--config={str(vd_cfg_file)}", *args], check=True
    )
    run_vd("discover", "card_download")
    run_vd("sync", "card_download")
    log("Extracting list of starred contacts")
    with open(card_dir / "Default" / "vips.vcf") as f:
        contact_uuids = set()
        for line in f:
            if not (m := re.match(r"X-ADDRESSBOOKSERVER-MEMBER:urn:uuid:(.+)$", line)):
                continue
            contact_uuids.add(m.group(1))
    birthdays = {}
    for contact_uuid in sorted(contact_uuids):
        with open(card_dir / "Default" / f"{contact_uuid}.vcf") as f:
            ct_name = None
            ct_month = None
            ct_day = None
            for line in f:
                if m := re.match(r"FN:(.+)$", line):
                    ct_name = m.group(1)
                    continue
                if m := re.match(r"BDAY[;:].*[0-9]{4}-([0-9]{2})-([0-9]{2})$", line):
                    ct_month = int(m.group(1))
                    ct_day = int(m.group(2))
                    continue
        if not (ct_name and ct_month and ct_day):
            log(f"Skipping {ct_name or contact_uuid} as data was not found in card")
            continue
        log(f"Registering {ct_name} with birthday {ct_month:02d}-{ct_day:02d}")
        birthdays[f"bf-{contact_uuid}"] = (ct_name, ct_month, ct_day)
    log(f"Total birthday count: {len(birthdays)}")
    log("Generating birthday calendar")
    try:
        shutil.rmtree(cal_dir / cfg.BIRTHDAY_CALENDAR_ID)
    except FileNotFoundError:
        pass
    (cal_dir / cfg.BIRTHDAY_CALENDAR_ID).mkdir(parents=True)
    for event_uuid, (ct_name, ct_month, ct_day) in birthdays.items():
        with open(cal_dir / cfg.BIRTHDAY_CALENDAR_ID / f"{event_uuid}.ics", "w") as f:
            f.write("BEGIN:VCALENDAR\n")
            f.write("VERSION:2.0\n")
            f.write("CALSCALE:GREGORIAN\n")
            f.write("BEGIN:VEVENT\n")
            f.write(f"UID:{event_uuid}\n")
            f.write("SEQUENCE:0\n")
            f.write(f"DTSTAMP:2000{ct_month:02d}{ct_day:02d}T000000Z\n")
            f.write(f"DTSTART;VALUE=DATE:2000{ct_month:02d}{ct_day:02d}\n")
            f.write("DURATION:P1D\n")
            f.write("PRIORITY:0\n")
            f.write(f"SUMMARY:🎂 {ct_name}\n")
            f.write("RRULE:FREQ=YEARLY\n")
            f.write("STATUS:CONFIRMED\n")
            f.write("END:VEVENT\n")
            f.write("END:VCALENDAR\n")
    log("Running vdirsyncer to upload calendar")
    run_vd("discover", "cal_upload")
    run_vd("sync", "cal_upload")
