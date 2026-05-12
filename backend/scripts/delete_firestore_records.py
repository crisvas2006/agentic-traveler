import os
from google.cloud import firestore
from dotenv import load_dotenv

# 1. Load the environment variables from the .env file in the parent folder
# This ensures GOOGLE_APPLICATION_CREDENTIALS is set for the script
load_dotenv(dotenv_path="../.env")

# 2. Setup client (uses your project & database IDs)
# We pull the project ID from env, falling back to the hardcoded ID
db = firestore.Client(
    project=os.getenv("GOOGLE_PROJECT_ID"), 
    database="agentic-traveler-db"
)

def delete_filtered_docs():
    # 3. Define your query (targeting the feedback collection)
    collection_ref = db.collection("feedback")
    query = collection_ref.where("user_id", "==", "eval_script")
    
    # 4. Get the matching documents
    docs = query.stream()
    
    deleted_count = 0
    for doc in docs:
        print(f"Deleting document: {doc.id}")
        # Uncomment the line below to actually perform the deletion!
        doc.reference.delete()
        deleted_count += 1
        
    print(f"Successfully found {deleted_count} documents to delete.")

if __name__ == "__main__":
    delete_filtered_docs()
