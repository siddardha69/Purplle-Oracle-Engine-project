import os
import zipfile

def create_zip():
    zip_name = "purplle_store_intelligence_submission.zip"
    exclude_dirs = {".git", ".venv", "venv", "__pycache__", ".ipynb_checkpoints", ".pytest_cache", "local_logs", "logs"}
    exclude_files = {
        "yolov8n.pt", 
        "store_intelligence.db", 
        "openh264-1.8.0-win64.dll", 
        "test_avc1.mp4", 
        "test_h264.mp4", 
        "test_vp8.webm", 
        "test_vp9.webm"
    }
    
    print(f"Creating submission zip: {zip_name}...")
    count = 0
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Modify dirs in-place to exclude unwanted directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            for file in files:
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, '.')
                
                # Ignore the zip file itself
                if relpath == zip_name:
                    continue
                    
                # Exclude specific files
                if file in exclude_files or file.endswith('.db') or file.endswith('.db-journal') or file.endswith('.log'):
                    continue
                    
                # Exclude large raw video files (keeping only demo_processed.mp4)
                if "data/videos" in relpath.replace('\\', '/'):
                    if file not in ["demo_processed.mp4", "README.md"]:
                        continue
                        
                # Exclude events.jsonl to keep submission clean
                if file == "events.jsonl":
                    continue
                    
                zipf.write(relpath)
                count += 1
                
    size_mb = os.path.getsize(zip_name) / (1024 * 1024)
    print(f"Successfully zipped {count} files.")
    print(f"Zip file saved at: {os.path.abspath(zip_name)}")
    print(f"Total size: {size_mb:.2f} MB (Limit: 50.00 MB)")

if __name__ == "__main__":
    create_zip()
