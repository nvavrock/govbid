import glob
import os
import requests
from datetime import datetime

def cleanup_old_exports(target_dir: str, keep_path: str) -> None:
    keep_abs = os.path.abspath(keep_path)
    pattern = os.path.join(target_dir, "ContractOpportunitiesFull_*.csv")
    for old_path in glob.glob(pattern):
        if os.path.abspath(old_path) != keep_abs:
            os.remove(old_path)
            print(f"Removed old export: {old_path}")

def download_sam_opportunities(target_dir="./data"):
    # Target URL for the public SAM.gov bulk extract
    url = "https://sam.gov/api/prod/fileextractservices/v1/api/download/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv?privacy=Public"
    
    # Establish local file naming protocol
    os.makedirs(target_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"ContractOpportunitiesFull_{date_str}.csv"
    file_path = os.path.join(target_dir, filename)
    
    print(f"Initiating download from SAM.gov...")
    
    # Stream download to manage memory footprint
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
    print(f"Successfully archived: {file_path}")
    cleanup_old_exports(target_dir, file_path)
    return file_path

if __name__ == "__main__":
    download_sam_opportunities()