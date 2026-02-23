from flask import Flask, redirect, request, session, render_template, flash
import requests
import os
from dotenv import load_dotenv
import base64
import time
from datetime import datetime
import logging

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "SUPER_SECRET_KEY")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    logger.error("CLIENT_ID atau CLIENT_SECRET tidak ditemukan di file environment variables.")
    print("PERINGATAN: CLIENT_ID dan CLIENT_SECRET belum diset.")

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
        logger.error(f"Error pada callback login: {error}")
        return f"Error login: {error}", 400
        
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
        
        if "error" in token_json:
            logger.error(f"Error response token: {token_json}")
            return f"Gagal mendapatkan token: {token_json.get('error_description')}", 400

        access_token = token_json.get("access_token")
        if not access_token:
            logger.error("Access token tidak ditemukan dalam response.")
            return "Gagal mendapatkan access token", 400
            
        session["access_token"] = access_token
        

        user_resp = requests.get("https://api.github.com/user", headers={"Authorization": f"token {access_token}"})
        if user_resp.status_code == 200:
            session["username"] = user_resp.json().get("login")
        
        return redirect("/dashboard")
        
    except requests.RequestException as e:
        logger.error(f"Exception saat request token: {e}")
        return "Terjadi kesalahan saat menghubungi GitHub.", 500

# Dashboard
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "access_token" not in session:
        return redirect("/")

    message = ""
    error_message = ""

    if request.method == "POST":
        try:
            jumlah = int(request.form.get("jumlah", 0))
            if jumlah < 1:
                error_message = "Jumlah commit minimal 1"
            else:
                token = session["access_token"]
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                username = session.get("username")
                if not username:
                     user_resp = requests.get("https://api.github.com/user", headers=headers)
                     user_resp.raise_for_status()
                     username = user_resp.json().get("login")

                timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
                repo_name = f"commit-generator-{timestamp_str}"
                
                create_repo_response = requests.post(
                    "https://api.github.com/user/repos",
                    headers=headers,
                    json={"name": repo_name, "private": True, "auto_init": True}, 
                )
                
                create_repo_response.raise_for_status()
                repo_data = create_repo_response.json()
                logger.info(f"Repo {repo_name} berhasil dibuat.")

                time.sleep(2)
                

                file_path = "file.txt"
                current_sha = None
                
                for i in range(jumlah):
                    commit_message = f"Commit {i+1} dari {jumlah}"
                    content_str = f"Commit ke-{i+1} pada {datetime.now()}"
                    content_b64 = base64.b64encode(content_str.encode()).decode()
                    
                    data = {
                        "message": commit_message,
                        "content": content_b64,
                        "branch": repo_data.get("default_branch", "main")
                    }
                    
                    if current_sha:
                        data["sha"] = current_sha
                    

                    url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{file_path}"
                    
                    put_response = requests.put(url, headers=headers, json=data)
                    put_response.raise_for_status()
                    

                    result = put_response.json()
                    current_sha = result["content"]["sha"]
                    
                    logger.info(f"Commit {i+1} berhasil.")
                    time.sleep(0.5)

                message = f"Berhasil membuat repository '{repo_name}' dengan {jumlah} commit!"
                
        except requests.RequestException as e:
            logger.error(f"GitHub API Error: {e}")
            if e.response is not None:
                try:
                    err_detail = e.response.json()
                    error_message = f"GitHub Error: {err_detail.get('message', str(e))}"
                except:
                    error_message = f"GitHub Error: {str(e)}"
            else:
                error_message = f"Connection Error: {str(e)}"
        except ValueError:
            error_message = "Input jumlah harus berupa angka."
        except Exception as e:
            logger.exception("Unexpected error")
            error_message = f"Terjadi kesalahan internal: {str(e)}"

    return render_template("dashboard.html", message=message, error_message=error_message)

if __name__ == "__main__":
    app.run(debug=True)