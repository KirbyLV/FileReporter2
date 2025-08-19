import gspread
from oauth2client.service_account import ServiceAccountCredentials
from media_utils import parse_version

SCOPE = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# Columns the app owns. Anything else in the sheet is considered "custom" and preserved.
MANAGED_HEADERS = [
    'stem','version','filename','ext','path','size_bytes','codec','width','height',
    'fps','duration_sec','has_audio','created_iso','modified_iso'
]

def open_sheet(sa_json_path: str, sheet_name: str):
    creds = ServiceAccountCredentials.from_json_keyfile_name(sa_json_path, SCOPE)
    client = gspread.authorize(creds)
    try:
        sh = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        sh = client.create(sheet_name)
    ws = sh.sheet1

    # Ensure header row exists; do NOT wipe existing custom columns.
    existing = ws.row_values(1)
    if not existing:
        ws.append_row(MANAGED_HEADERS)
        existing = ws.row_values(1)

    # Append any missing managed headers to the right
    missing = [h for h in MANAGED_HEADERS if h not in existing]
    if missing:
        new_headers = existing + missing
        ws.update(f"A1:{col_letter(len(new_headers))}1", [new_headers])
        existing = new_headers

    return ws

def to_row_dict(rec: dict) -> dict:
    """Return a dict of managed fields for easy merging into an existing row vector."""
    pv = parse_version(rec['name'])
    return {
        'stem': pv['stem'],
        'version': pv['version'],
        'filename': rec.get('name'),
        'ext': rec.get('ext'),
        'path': rec.get('path'),
        'size_bytes': rec.get('size_bytes'),
        'codec': rec.get('codec'),
        'width': rec.get('width'),
        'height': rec.get('height'),
        'fps': rec.get('fps'),
        'duration_sec': rec.get('duration_sec'),
        'has_audio': rec.get('has_audio'),
        'created_iso': rec.get('created_iso'),
        'modified_iso': rec.get('modified_iso'),
    }

def col_letter(n: int) -> str:
    """1 -> A, 2 -> B, ..."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def sync_records(ws, records: list):
    """
    Preserve any extra columns:
    - Read the whole sheet
    - Build a stem->row map
    - For existing rows, update only managed columns, leaving others alone
    - For new rows, append rows with managed data; extra columns remain blank
    """
    # 1) Headers & index maps
    headers = ws.row_values(1)
    header_to_idx = {h: i for i, h in enumerate(headers)}  # 0-based
    num_cols = len(headers)
    stem_col = header_to_idx.get('stem')
    if stem_col is None:
        raise RuntimeError("Sheet is missing 'stem' column after header setup.")

    # 2) Fetch existing rows (raw values) and build stem -> rownum map (2-based)
    # Use get_all_values for exact shape & custom columns
    all_vals = ws.get_all_values()
    rows = all_vals[1:] if len(all_vals) > 1 else []
    stem_to_rownum = {}
    for i, row in enumerate(rows, start=2):
        stem_val = row[stem_col].strip() if stem_col < len(row) else ""
        if stem_val:
            stem_to_rownum[stem_val] = i

    # 3) Prepare batch updates
    batch_updates = []   # each item: {'range': 'A{r}:{Z}{r}', 'values': [[...]]}
    appends = []         # 2D list of new rows

    for rec in records:
        managed = to_row_dict(rec)
        stem = managed['stem']
        if not stem:
            # Skip rows without a usable key
            continue

        # Build a full row vector of current sheet width; start with existing row or blanks
        if stem in stem_to_rownum:
            rnum = stem_to_rownum[stem]
            # get existing row into a vector of fixed width
            idx_in_rows = rnum - 2
            existing_row = rows[idx_in_rows] if 0 <= idx_in_rows < len(rows) else []
            row_vec = (existing_row + [""] * (num_cols - len(existing_row)))[:num_cols]
        else:
            rnum = None
            row_vec = [""] * num_cols

        # Merge managed fields into row_vec at their column positions
        for key, val in managed.items():
            if key in header_to_idx:
                row_vec[header_to_idx[key]] = "" if val is None else str(val)

        if rnum:
            # Update the whole row range with the merged vector (preserves custom columns' current values)
            rng = f"A{rnum}:{col_letter(num_cols)}{rnum}"
            batch_updates.append({'range': rng, 'values': [row_vec]})
        else:
            # New row: append; custom columns remain blank by design
            appends.append(row_vec)

    # 4) Apply updates efficiently
    if batch_updates:
        ws.batch_update(batch_updates)
    if appends:
        ws.append_rows(appends)
