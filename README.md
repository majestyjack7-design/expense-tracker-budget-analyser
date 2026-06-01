# Expense Tracker & Budget Analyser

A web-based personal finance application built with Flask.  
The app helps users track income, expenses, budgets, spending categories, and financial analytics in one place.

## Project Overview

Expense Tracker & Budget Analyser is a full-stack web application designed to help users manage their personal finances more effectively.

Users can create an account, log in securely, record income and expenses, manage monthly budgets, view transaction history, analyse spending patterns, and export transaction records as CSV.

This project was built as a one-month practical software development project.

## Features

- User registration and login
- Secure password hashing
- Protected user dashboard
- Add income and expense transactions
- Edit and delete transactions
- View transaction history
- Filter transactions
- Monthly budget tracking
- Budget progress indicator
- Analytics dashboard
- Income vs expenses trend
- Expenses by category
- Spending overview
- Top spending categories
- CSV export
- Responsive user interface

## Technologies Used

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite
- HTML
- CSS
- JavaScript
- Chart.js
- Git
- GitHub

## Project Structure

```text
expense-tracker/
│
├── app.py
├── requirements.txt
├── README.md
├── static/
│   ├── css/
│   │   └── style.css
│   └── images/
│       └── login-hero.png
│
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── add_transaction.html
    ├── edit_transaction.html
    ├── transactions.html
    ├── budget.html
    └── reports.html