import os
import json
import datetime
import subprocess
from google.cloud import firestore
from notion_client import Client
# dotenv logic is handled by caller or pre-loaded environment

def fetch_firestore_logs():
    print("--- Fetching Firestore Logs ---")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        print(f"Skipping Firestore fetch. Credentials not found or invalid at: {cred_path}")
        return []
        
    try:
        # Check if we can actually connect (basic check)
        # Note: robust checking requires a real query which might fail with auth error
        db = firestore.Client()
        collection_name = "conversations" 
        
        jst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(jst)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_day_utc = start_of_day.astimezone(datetime.timezone.utc)
        
        print(f"Querying Firestore since: {start_of_day_utc}")

        docs = db.collection(collection_name)\
            .where("updated_at", ">=", start_of_day_utc)\
            .order_by("updated_at", direction=firestore.Query.DESCENDING)\
            .limit(20)\
            .stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            if 'updated_at' in data:
                data['updated_at'] = data['updated_at'].isoformat()
            
            # Clean history
            history = data.get('history', [])
            cleaned_history = []
            for item in history:
                if 'parts' in item:
                    text_content = item['parts'][0] if isinstance(item['parts'], list) and len(item['parts']) > 0 else str(item['parts'])
                    cleaned_history.append({
                        'role': item.get('role'),
                        'text': text_content
                    })
            results.append({
                'id': doc.id,
                'updated_at': data.get('updated_at'),
                'history': cleaned_history
            })
        
        print(f"Found {len(results)} conversation logs.")
        return results
    except Exception as e:
        print(f"Error fetching Firestore: {e}")
        return []

def fetch_cloud_logging():
    print("--- Fetching Cloud Logging (Cloud Run / Functions) ---")
    try:
        jst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(jst)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        timestamp = start_of_day.isoformat()

        # Filter for both Cloud Function (Gen1) and Cloud Run Revision (Gen2)
        # excluding system logs to reduce noise, focusing on stdout/stderr usually
        filter_str = f'(resource.type="cloud_function" OR resource.type="cloud_run_revision") AND timestamp>="{timestamp}" AND severity>=NOTICE' 
        
        print(f"Querying Cloud Logging since: {timestamp}")
        
        # Resolve gcloud path
        gcloud_path = "gcloud"
        # Try known standard paths if default fails (simple check)
        known_paths = [
            r"C:\Users\kajit\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
        ]
        for p in known_paths:
            if os.path.exists(p):
                gcloud_path = p
                break

        cmd = [
            gcloud_path, "logging", "read",
            filter_str,
            "--limit=50", 
            "--format=json",
            "--project=notigenie" # Ensure project is set
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        except FileNotFoundError:
             # Fallback if gcloud path resolution failed completely
            print("gcloud command not found. Ensure Google Cloud SDK is installed and in PATH.")
            return []

        if result.returncode != 0:
            print(f"Error running gcloud: {result.stderr}")
            return []
            
        logs = json.loads(result.stdout)
        print(f"Found {len(logs)} log entries.")
        return logs
    except Exception as e:
        print(f"Error fetching Cloud Logging: {e}")
        return []

def fetch_notion_updates():
    print("--- Fetching Notion Updates ---")
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        print("NOTION_API_KEY is not set.")
        return []

    try:
        notion = Client(auth=api_key)
        
        jst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(jst)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"Querying Notion since: {start_of_day.isoformat()}")
        
        response = notion.search(
            filter={"property": "object", "value": "page"},
            sort={"direction": "descending", "timestamp": "last_edited_time"},
            page_size=20
        )
        
        results = []
        for page in response.get("results", []):
            last_edited_str = page["last_edited_time"].replace('Z', '+00:00')
            last_edited = datetime.datetime.fromisoformat(last_edited_str)
            
            if last_edited >= start_of_day.astimezone(datetime.timezone.utc):
                results.append({
                    "id": page["id"],
                    "url": page["url"],
                    "last_edited_time": page["last_edited_time"],
                    "title": _get_title(page)
                })
        
        print(f"Found {len(results)} updated pages.")
        return results
    except Exception as e:
        print(f"Error fetching Notion: {e}")
        return []

def _get_title(page):
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("id") == "title" or prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return "".join([t.get("plain_text", "") for t in title_list])
    return "No Title"

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "firestore": [], # fetch_firestore_logs(), # Skipped due to invalid credentials
        "cloud_logging": fetch_cloud_logging(),
        "notion": fetch_notion_updates()
    }
    
    output_file = "daily_summary_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"Report saved to {output_file}")
