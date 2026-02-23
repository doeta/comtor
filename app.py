from flask import Flask, redirect, request, session, render_template, flash, Response, stream_with_context
import json
import requests
import os
from dotenv import load_dotenv
import logging
import base64
import time
from datetime import datetime

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "SUPER_SECRET_KEY")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    logger.error("CLIENT_ID atau CLIENT_SECRET tidak ditemukan.")



def create_or_get_repo(username, token, repo_name="commit-generator-storage"):
    """
    Checks if a repository exists, if not creates it.
    Returns the repository data.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    check_url = f"https://api.github.com/repos/{username}/{repo_name}"
    response = requests.get(check_url, headers=headers)
    
    if response.status_code == 200:
        logger.info(f"Using existing repository: {repo_name}")
        return response.json()
        
    elif response.status_code == 404:
        logger.info(f"Repository {repo_name} not found. Creating new one.")
        create_url = "https://api.github.com/user/repos"
        payload = {
            "name": repo_name,
            "private": True,
            "auto_init": True,
            "description": "Storage for generated commits"
        }
        create_response = requests.post(create_url, headers=headers, json=payload)
        create_response.raise_for_status()

        time.sleep(2)
        return create_response.json()
    else:
        response.raise_for_status()

def get_file_sha(username, repo_name, file_path, token):
    """Gets the SHA of a file if it exists."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("sha")
    return None

def generate_commits_generator(username, token, repo_name, count):
    """
    Generator function that yields progress updates.
    """
    yield json.dumps({"status": "init", "message": "Initializing process..."}) + "\n"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    file_path = "file.txt"
    current_sha = get_file_sha(username, repo_name, file_path, token)
    yield json.dumps({"status": "init", "message": "Repository validated..."}) + "\n"
    
    url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}"

    
    # Get default branch (safeguard)
    try:
        repo_info = requests.get(f"https://api.github.com/repos/{username}/{repo_name}", headers=headers).json()
        default_branch = repo_info.get("default_branch", "main")
    except Exception:
        default_branch = "main"

    success_count = 0
    current_sleep = 0.5 # Default speed

    for i in range(count):
        yield json.dumps({"status": "progress", "current": i+1, "total": count, "message": f"Creating commit {i+1} of {count}..."}) + "\n"
        
        try:
            commit_message = f"Commit {i+1} of {count} - Auto Generated {datetime.now().strftime('%H:%M:%S')}"
            content_str = f"Commit #{i+1} generated at {datetime.now().isoformat()}"
            content_b64 = base64.b64encode(content_str.encode()).decode()
            
            data = {
                "message": commit_message,
                "content": content_b64,
                "branch": default_branch
            }
            
            if current_sha:
                data["sha"] = current_sha
                
            response = requests.put(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            if "content" in result and "sha" in result["content"]:
                current_sha = result["content"]["sha"]
                success_count += 1
                logger.info(f"Commit {i+1}/{count} created successfully.")
            
            time.sleep(current_sleep)
            
        except requests.RequestException as e:
            logger.warning(f"Error on commit {i+1}: {e}")
            yield json.dumps({"status": "warning", "message": f"Error on commit {i+1}, retrying..."}) + "\n"
            
            if e.response is not None and e.response.status_code in [403, 409, 429, 500, 502, 503]:
                 if e.response.status_code in [403, 429]:
                      current_sleep = 2.0
                      yield json.dumps({"status": "warning", "message": f"Rate limit detected. Slowing down..."}) + "\n"
                 
                 time.sleep(5)
                 try:
                     if e.response.status_code == 409:
                         fresh_sha = get_file_sha(username, repo_name, file_path, token)
                         if fresh_sha:
                             data["sha"] = fresh_sha
                     
                     response = requests.put(url, headers=headers, json=data)
                     response.raise_for_status()
                     result = response.json()
                     
                     if "content" in result and "sha" in result["content"]:
                        current_sha = result["content"]["sha"]
                        success_count += 1
                 except Exception as retry_err:
                     logger.error(f"Retry failed: {retry_err}")
            else:
                break
    
    yield json.dumps({"status": "done", "total": success_count, "message": "All commits detailed!"}) + "\n"

# --- ROUTES --- #

# Home
@app.route("/")
def index():
    return render_template("index.html")

# Login GitHub
@app.route("/login")
def login():
    if not CLIENT_ID:
        flash("Client ID belum dikonfigurasi.", "error")
        return redirect("/")
    
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&scope=repo,user"
    return redirect(github_auth_url)

# Callback
@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error:
        flash(f"Login gagal: {error}", "error")
        return redirect("/")
        
    if not code:
        return redirect("/")

    try:
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
            },
        )
        token_response.raise_for_status()
        
        token_json = token_response.json()
        access_token = token_json.get("access_token")
        
        if not access_token:
            flash("Gagal mendapatkan access token", "error")
            return redirect("/")
            
        session["access_token"] = access_token
        
        # Get detailed user info
        user_resp = requests.get("https://api.github.com/user", headers={"Authorization": f"token {access_token}"})
        if user_resp.status_code == 200:
            user_data = user_resp.json()
            session["username"] = user_data.get("login")
            session["name"] = user_data.get("name")
            session["avatar_url"] = user_data.get("avatar_url")
            session["html_url"] = user_data.get("html_url")
        
        return redirect("/dashboard")

    except requests.RequestException as e:
        logger.error(f"Login Exception: {e}")
        flash("Terjadi kesalahan koneksi ke GitHub.", "error")
        return redirect("/")

# API for Streaming Commits
@app.route("/stream_commits", methods=["POST"])
def stream_commits():
    if "access_token" not in session:
        return Response(json.dumps({"error": "Unauthorized"}), status=401, mimetype='application/json')
    
    try:
        data = request.json
        jumlah = int(data.get("jumlah", 1))
        
        token = session["access_token"]
        username = session.get("username")
        REPO_NAME = "commit-generator-storage"
        
        def stream_wrapper():
            yield json.dumps({"status": "init", "message": "Connecting..."}) + "\n"
            time.sleep(0.05) 
            final_username = username
            if not final_username:
                 yield json.dumps({"status": "init", "message": "Verifying user..."}) + "\n"
                 try:
                     user_resp = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
                     if user_resp.status_code == 200:
                        final_username = user_resp.json().get("login")
                     else:
                        raise Exception("Failed to fetch user info")
                 except Exception as e:
                     yield json.dumps({"error": f"Auth Error: {str(e)}"}) + "\n"
                     return

            yield json.dumps({"status": "init", "message": "Checking repository..."}) + "\n"
            try:
                create_or_get_repo(final_username, token, REPO_NAME)
                gen = generate_commits_generator(final_username, token, REPO_NAME, jumlah)
                for item in gen:
                    yield item
                    
            except Exception as e:
                logger.error(f"Stream Wrapper Error: {e}")
                err_dict = {"error": str(e)}
                yield json.dumps(err_dict) + "\n"

        return Response(
            stream_with_context(stream_wrapper()),  
            mimetype='application/json',
            headers={"X-Accel-Buffering": "no"} 
        )
        
    except ValueError:
        return Response(json.dumps({"error": "Invalid number"}), status=400, mimetype='application/json')
    except Exception as e:
        logger.error(f"Stream Error: {e}")
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

# Dashboard
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "access_token" not in session:
        return redirect("/")

    message = ""
    error_message = ""

    if request.method == "POST":
        try:
            jumlah_input = request.form.get("jumlah", "0")
            if not jumlah_input.isdigit():
                 raise ValueError("Input harus angka")
                 
            jumlah = int(jumlah_input)
            if jumlah < 1:
                error_message = "Jumlah commit minimal 1"
            else:
                token = session["access_token"]
                username = session.get("username")
                

                if not username:
                     user_resp = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
                     if user_resp.status_code == 200:
                        username = user_resp.json().get("login")
                     else:
                        raise Exception("Gagal mendapatkan user info. Coba login ulang.")

                REPO_NAME = "commit-generator-storage"
                
                repo_data = create_or_get_repo(username, token, REPO_NAME)

                gen = generate_commits_generator(username, token, REPO_NAME, jumlah)
                for _ in gen:
                    pass 
                
                message = f"Berhasil membuat commit di repository '{REPO_NAME}'!"  

                
        except requests.RequestException as e:
            logger.error(f"GitHub API Error: {e}")
            error_message = f"GitHub Error: {str(e)}"
        except ValueError:
            error_message = "Input jumlah harus berupa angka valid."
        except Exception as e:
            logger.exception("Unexpected error")
            error_message = f"Terjadi kesalahan: {str(e)}"

    return render_template("dashboard.html", message=message, error_message=error_message)

if __name__ == "__main__":
    app.run(debug=True, threaded=True, host='127.0.0.1', port=5000)
