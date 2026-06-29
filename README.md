# 🍽️ CloudChef

> A Full-Stack Home-Cooked Food Delivery Platform built with Django, Docker, GitHub Actions, and AWS.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Django](https://img.shields.io/badge/Django-Framework-green?logo=django)
![Docker](https://img.shields.io/badge/Docker-Container-blue?logo=docker)
![GitHub Actions](https://img.shields.io/badge/CI/CD-GitHub%20Actions-black?logo=githubactions)
![AWS](https://img.shields.io/badge/AWS-EC2-orange?logo=amazonaws)
![SQLite](https://img.shields.io/badge/Database-SQLite-blue?logo=sqlite)

---

## 📖 About

CloudChef is a cloud-based food delivery platform that connects customers with talented home chefs. The platform enables customers to discover homemade meals, place orders, make secure payments, and track deliveries while empowering home chefs to manage menus and grow their business.

The project demonstrates Full-Stack Web Development along with modern DevOps practices including Docker containerization, CI/CD automation, and cloud deployment.

---

## ✨ Features

### 👤 Customer
- User Registration & Login
- Browse Home Chefs
- Search Food Items
- Add to Cart
- Place Orders
- Order Tracking
- Ratings & Reviews

### 👩‍🍳 Home Chef
- Manage Food Menu
- Add/Edit/Delete Dishes
- Accept Orders
- Update Order Status
- View Customer Feedback

### 🛠️ Admin
- Dashboard
- Manage Users
- Manage Home Chefs
- Manage Orders
- Platform Monitoring

---

## 🛠 Tech Stack

| Category | Technologies |
|----------|--------------|
| Backend | Python, Django |
| Frontend | HTML5, CSS3, JavaScript |
| Database | SQLite |
| Version Control | Git, GitHub |
| Containerization | Docker |
| CI/CD | GitHub Actions |
| Cloud | AWS EC2 |
| Web Server | Gunicorn |
| Operating System | Linux (Ubuntu) |

---

# 📂 Project Structure

```text
CloudChef/
│
├── customer/
├── chef/
├── admin_panel/
├── templates/
├── static/
├── media/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
└── README.md
```

---

# 🚀 Installation

## Clone Repository

```bash
git clone https://github.com/yourusername/cloudchef.git

cd cloudchef
```

## Create Virtual Environment

```bash
python -m venv venv
```

## Activate Virtual Environment

### Windows

```bash
venv\Scripts\activate
```

### Linux / Mac

```bash
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Run Migrations

```bash
python manage.py migrate
```

## Start Server

```bash
python manage.py runserver
```

---

# 🐳 Docker

Build Image

```bash
docker build -t cloudchef .
```

Run Container

```bash
docker run -p 8000:8000 cloudchef
```

Using Docker Compose

```bash
docker compose up --build
```

---

# ⚙️ CI/CD Pipeline

GitHub Actions automates the following steps:

- Checkout Repository
- Install Dependencies
- Run Tests
- Build Docker Image
- Push Image to Docker Hub
- Deploy to AWS EC2

---

# ☁️ Deployment

CloudChef is deployed using:

- AWS EC2
- Docker
- GitHub Actions
- Docker Hub

---

# 📸 Screenshots
<table>
<tr>
<td><<img width="1347" height="687" alt="WhatsApp Image 2026-06-29 at 3 28 15 PM" src="https://github.com/user-attachments/assets/336d4870-1edd-4655-ae1a-04b75073331a" />
</td>
<td><img width="339" height="568" alt="WhatsApp Image 2026-06-29 at 3 28 16 PM" src="https://github.com/user-attachments/assets/67f83d08-aa5a-4944-8dd2-84361a7f3d89" />
</td>
</tr>
<tr>
<td colspan="2" align="center">
<img width="1355" height="625" alt="WhatsApp Image 2026-06-29 at 3 28 16 PM" src="https://github.com/user-attachments/assets/3ad0e45a-5fd0-4ed2-8f37-6a13e958897a" />
</td>
</tr>
</table>

---

# 🔮 Future Enhancements

- Online Payment Gateway
- Email Notifications
- REST API
- JWT Authentication
- Redis Caching
- Recommendation System
- Live Order Tracking
- AI Food Recommendation

---


⭐ If you like this project, don't forget to star the repository.
