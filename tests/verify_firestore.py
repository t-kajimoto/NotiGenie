import sys
import os
import uuid
from google.cloud import firestore
from google.api_core.exceptions import ServiceUnavailable, Forbidden


def verify_firestore():
    """
    Verifies access to Google Cloud Firestore by attempting to write
    and read a test document.
    """
    print("=== Firestore Connection Verification ===")

    # 1. Check for Project ID
    project_id = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print(
            "[WARN] GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable "
            "not found."
        )
        print(
            "       The client will attempt to detect the project ID "
            "from credentials."
        )
    else:
        print(f"[INFO] Target Project ID: {project_id}")

    try:
        # 2. Initialize Client
        # Note: This relies on Application Default Credentials (ADC)
        database_id = os.environ.get("FIRESTORE_DATABASE") or "(default)"
        print(f"[INFO] Target Database ID: {database_id}")

        db = firestore.Client(database=database_id)
        print(f"[INFO] Client initialized. Project: {db.project}")

        # 3. Perform Write Test
        collection_name = "system_verification"
        doc_id = f"test_{uuid.uuid4().hex}"
        doc_ref = db.collection(collection_name).document(doc_id)

        test_data = {
            "message": "Firestore verification test",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "status": "pending"
        }

        print(f"[INFO] Attempting to write to {collection_name}/{doc_id}...")
        doc_ref.set(test_data)
        print("[PASS] Write successful.")

        # 4. Perform Read Test
        print(f"[INFO] Attempting to read from {collection_name}/{doc_id}...")
        doc = doc_ref.get()
        if doc.exists:
            print(f"[PASS] Read successful. Data: {doc.to_dict()}")
        else:
            print("[FAIL] Document not found after write!")
            return False

        # 5. Cleanup
        print("[INFO] Cleaning up (deleting test document)...")
        doc_ref.delete()
        print("[PASS] Cleanup successful.")

        print("\n[SUCCESS] Firestore is correctly configured and accessible.")
        return True

    except ServiceUnavailable as e:
        print(f"\n[ERROR] Service Unavailable: {e}")
        print("Possible causes:")
        print(
            "1. The Firestore API is not enabled in the Google Cloud Console."
        )
        print("2. The database has not been created.")
        print(
            "   -> Go to Console > Firestore and create a database in "
            "'Native Mode'."
        )
        return False
    except Forbidden as e:
        print(f"\n[ERROR] Permission Denied: {e}")
        print("Possible causes:")
        print(
            "1. The Service Account or User credentials missing "
            "'Cloud Datastore User' or 'Firebase Admin' roles."
        )
        print(
            "2. Firestore Security Rules are blocking the request "
            "(if using Client SDK, but this uses Admin SDK so IAM "
            "matters more)."
        )
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if verify_firestore():
        sys.exit(0)
    else:
        sys.exit(1)
