#!/usr/bin/env python3
"""
Diagnostic script to test upload_log functionality.
Run this to check if the upload logging is configured correctly.
"""
import os
import json
from datetime import datetime

# Same defaults as app.py
CONFIG_DIR = os.environ.get('CONFIG_DIR', '/config')
SETTINGS_PATH = os.path.join(CONFIG_DIR, 'settings.json')
DEFAULT_SA_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON',
                                  os.path.join(CONFIG_DIR, 'google-service-account.json'))
DEFAULT_SHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME', 'Media Repo Inventory')

def load_settings():
    """Load settings from settings.json or return defaults."""
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading settings: {e}")
    return {
        'sheet_name': DEFAULT_SHEET_NAME,
        'service_account_json': DEFAULT_SA_JSON,
    }

def main():
    print("=" * 60)
    print("UPLOAD LOG DIAGNOSTIC")
    print("=" * 60)

    # Check environment
    print(f"\n📁 CONFIG_DIR: {CONFIG_DIR}")
    print(f"   Exists: {os.path.isdir(CONFIG_DIR)}")

    # Load settings
    print(f"\n📄 Settings file: {SETTINGS_PATH}")
    print(f"   Exists: {os.path.exists(SETTINGS_PATH)}")

    cfg = load_settings()
    print(f"\n⚙️  Loaded configuration:")
    print(f"   sheet_name: {cfg.get('sheet_name')}")
    print(f"   service_account_json: {cfg.get('service_account_json')}")

    # Check service account JSON
    sa_json = cfg.get('service_account_json')
    sheet_name = cfg.get('sheet_name')

    print(f"\n🔑 Service Account JSON:")
    print(f"   Path: {sa_json}")
    print(f"   File exists: {os.path.isfile(sa_json) if sa_json else 'N/A'}")

    if sa_json and os.path.isfile(sa_json):
        try:
            with open(sa_json, 'r') as f:
                sa_data = json.load(f)
                print(f"   ✅ Valid JSON")
                print(f"   Service account email: {sa_data.get('client_email', 'N/A')}")
        except Exception as e:
            print(f"   ❌ Invalid JSON: {e}")

    # Check if logging would be enabled
    log_to_sheets = bool(sa_json and sheet_name and os.path.isfile(sa_json))
    print(f"\n📊 Upload logging status:")
    print(f"   log_to_sheets: {log_to_sheets}")

    if not log_to_sheets:
        print("\n❌ LOGGING IS DISABLED")
        if not sa_json:
            print("   Reason: service_account_json not configured")
        elif not sheet_name:
            print("   Reason: sheet_name not configured")
        elif not os.path.isfile(sa_json):
            print(f"   Reason: Service account JSON file not found at {sa_json}")
    else:
        print("\n✅ LOGGING IS ENABLED")

        # Try to test actual logging
        print(f"\n🧪 Testing log_upload function...")
        try:
            from sheets_sync import log_upload
            test_path = "/test/sample.mkv"
            timestamp = datetime.utcnow().isoformat() + 'Z'

            print(f"   Attempting to log test file: {test_path}")
            log_upload(sa_json, sheet_name, test_path, timestamp)
            print(f"   ✅ Successfully logged to upload_log worksheet!")
        except Exception as e:
            print(f"   ❌ Error logging: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
