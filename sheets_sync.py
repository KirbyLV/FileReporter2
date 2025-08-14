import gspread
from oauth2client.service_account import ServiceAccountCredentials
from media_utils import parse_version

SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

HEADERS = ['stem','version','filename','ext','path','size_bytes','codec','width','height','fps','duration_sec','has_audio','created_iso','modified_iso']


def open_sheet(sa_json_path: str, sheet_name: str):
    creds = ServiceAccountCredentials.from_json_keyfile_name(sa_json_path, SCOPE)
    client = gspread.authorize(creds)
    try:
        sh = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        sh = client.create(sheet_name)
    ws = sh.sheet1
    try:
        existing = ws.row_values(1)
    except gspread.exceptions.APIError:
        existing = []
    if not existing:
        ws.append_row(HEADERS)
    return ws


def to_row(rec: dict):
    pv = parse_version(rec['name'])
    return [pv['stem'], pv['version'], rec.get('name'), rec.get('ext'), rec.get('path'), rec.get('size_bytes'), rec.get('codec'), rec.get('width'), rec.get('height'), rec.get('fps'), rec.get('duration_sec'), rec.get('has_audio'), rec.get('created_iso'), rec.get('modified_iso')]


def sync_records(ws, records: list):
    all_vals = ws.get_all_records()
    stem_to_row = {row.get('stem'): idx for idx, row in enumerate(all_vals, start=2)}

    updates, appends = [], []
    for rec in records:
        pv = parse_version(rec['name'])
        stem = pv['stem']
        row_vals = to_row(rec)
        if stem in stem_to_row:
            rnum = stem_to_row[stem]
            updates.append((f"A{rnum}:N{rnum}", row_vals))
        else:
            appends.append(row_vals)

    for rng, vals in updates:
        ws.update(rng, [vals])
    if appends:
        ws.append_rows(appends)