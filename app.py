import os
import zipfile
import subprocess
import threading
import time
from flask import Flask, render_template, request, redirect, session, Response

app = Flask(__name__)
app.secret_key = "Sulav"

PROJECTS = "projects"
ADMIN = "67676767"

os.makedirs(PROJECTS, exist_ok=True)

process = None
logs = []

# ---------------- BUILTINS ----------------

BUILTINS = {
"os","sys","json","time","re","math","random","threading",
"subprocess","asyncio","datetime","socket","ssl","base64",
"binascii","traceback","multiprocessing","signal","pickle",
"concurrent","zoneinfo"
}

PACKAGE_MAP = {
"jwt":"PyJWT",
"Crypto":"pycryptodome",
"google":"protobuf",
"cv2":"opencv-python",
"PIL":"pillow",
"bs4":"beautifulsoup4"
}

# ---------------- LOG STREAM ----------------

@app.route("/logs")
def log_stream():
    def generate():
        last = 0
        while True:
            if len(logs) > last:
                for line in logs[last:]:
                    yield f"data:{line}\n\n"
                last = len(logs)
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


# ---------------- LOGIN ----------------

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")

        if password:
            session["user"] = True
            session["admin"] = password == ADMIN
            return redirect("/dashboard")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    projects = os.listdir(PROJECTS)
    return render_template("dashboard.html", projects=projects)


# ---------------- UPLOAD ----------------

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files["file"]

    name = f.filename.replace(".zip","")
    path = os.path.join(PROJECTS, name)

    os.makedirs(path, exist_ok=True)

    zip_ref = zipfile.ZipFile(f)
    zip_ref.extractall(path)

    py_files = []

    for root,_,files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                full = os.path.join(root,file)
                rel = os.path.relpath(full, path)
                py_files.append(rel)

    return render_template(
        "select.html",
        project=name,
        files=py_files
    )


# ---------------- AUTO INSTALL ----------------

def auto_install(main):

    imports = set()

    with open(main,"r",errors="ignore") as f:
        for line in f:

            if line.startswith("import "):
                parts=line.replace("import","").split(",")
                for p in parts:
                    imports.add(p.strip().split(" ")[0])

            elif line.startswith("from "):
                imports.add(line.split()[1].split(".")[0])

    for pkg in imports:

        if pkg in BUILTINS:
            continue

        pkg = PACKAGE_MAP.get(pkg, pkg)

        logs.append(f"Installing {pkg}...")

        try:
            p = subprocess.Popen(
                ["pip","install",pkg],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            for line in p.stdout:
                logs.append(line.strip())

        except:
            pass


# ---------------- RUN FILE ----------------

def run_file(main):
    global process

    logs.append("Scanning imports...")
    auto_install(main)

    logs.append("Starting "+main)

    process = subprocess.Popen(
        ["python", main],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in process.stdout:
        logs.append(line.strip())


# ---------------- RUN SELECTED ----------------

@app.route("/run", methods=["POST"])
def run_selected():

    project = request.form["project"]
    file = request.form["file"]

    full = os.path.join(PROJECTS, project, file)

    threading.Thread(
        target=run_file,
        args=(full,)
    ).start()

    return redirect("/dashboard")


# ---------------- STOP ----------------

@app.route("/stop")
def stop():
    global process

    if process:
        process.terminate()
        logs.append("Stopped")

    return redirect("/dashboard")


# ---------------- MAIN ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)