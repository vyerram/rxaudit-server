# 🧠 AllwinRx / AuditRx Backend

This is the **Django** backend API powering the AllwinRx and AuditRx applications.

---

## ✅ Prerequisites

Before setting up the project, make sure you have the following installed on your system:

- **Python 3.8+** – Recommended version: 3.10 or later
- **PostgreSQL** – Database for storing app data
- **pip** – Python package manager
- **Git** – To clone the repository
- **Access to AWS credentials** 

> 🔐 Ensure your PostgreSQL server is running and credentials (username/password) are configured correctly.

---

## 🚀 Setup Instructions

### 1. :🔁 Clone the Repository
Use git to download the project:
```bash
git clone https://github.com/allwinrx/allwinrx.git

```
### 2. 🛠️ Create and Activate Virtual Environment 
A virtual environment keeps dependencies isolated from your system Python.
```bash
python -m venv env
```
Activate the virtual environment:
```bash
# On Windows
env\Scripts\activate

# On macOS/Linux
source env/bin/activate

```
Once activated, your shell prompt should show (env) at the beginning.


### 3.📦 Install Dependencies
Install all required libraries using pip:
```bash
pip install -r requirements.txt
```
If you encounter any installation errors, ensure that you are using Python 3.10+ and that your virtual environment is active.

### 4.🔐 Configure Environment Variables
Create a .env file in the project root (same level as manage.py) and paste the following sample content, modifying as needed:
```bash
DATABASE_URL=''
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost

EMAIL_FAILURE_NOTIFICATION_LIST = "mailforfailure@gmail.com"

EMAIL_BACKEND = ""
EMAIL_HOST = ""
EMAIL_USE_TLS = True
EMAIL_PORT = 000
EMAIL_HOST_USER = "hostuser@mail.com"
EMAIL_HOST_PASSWORD = "abc def ghij"

AWS_SERVER_ACCESS_KEY=youraccesskey
AWS_SERVER_SECRET_KEY=yoursecretkey
AWS_SERVER_REGION = your-region-name
AWS_BUCKET=your-bucket-name

HOST_URL=http://your-site-url.com
```
✅ Tip: Do not commit your .env file to Git. Add it to .gitignore for security.

### 5.🔄 Run migrations
Run the following command to set up database schema:
```bash
python manage.py migrate
```
This will create all necessary tables based on the models in your Django apps.


### 6.👤 Create Superuser (Admin)
Create an admin account to access Django Admin:
```bash
python manage.py createsuperuser
```
You'll be prompted to enter a username, email, and password.

### 7.🌐 Run Development Server
Run the Django development server:
```bash
python manage.py runserver
````
Visit http://127.0.0.1:8000/admin/ in your browser and log in using the superuser credentials.

## 📁 Project Structure Overview
```bash

allwinrx/
│
├── app/                    # Core Django app functioning and calculations
├── users/                  # Authentication and user management
├── settings.py             # Main configuration file for the Django project
├── manage.py               # Django entry point
└── requirements.txt        # Python package dependencies
```
